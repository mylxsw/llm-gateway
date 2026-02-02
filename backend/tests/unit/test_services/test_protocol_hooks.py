import json
from unittest.mock import AsyncMock, patch

import pytest

from app.common.time import utc_now
from app.domain.model import ModelMapping
from app.providers.base import ProviderResponse
from app.rules.models import CandidateProvider
from app.domain.kv_store import KeyValueModel
from app.services.protocol_hooks import ProtocolConversionHooks
from app.services.proxy_service import ProxyService


class RecordingHooks(ProtocolConversionHooks):
    async def before_request_conversion(self, body, request_protocol, supplier_protocol):
        return {**body, "before": True}

    async def after_request_conversion(self, supplier_body, request_protocol, supplier_protocol):
        return {**supplier_body, "after": True}

    async def before_response_conversion(self, supplier_body, request_protocol, supplier_protocol):
        return {"wrapped": supplier_body}

    async def after_response_conversion(self, response_body, request_protocol, supplier_protocol):
        return {"after_response": response_body}


class StreamHooks(ProtocolConversionHooks):
    async def before_stream_chunk_conversion(self, chunk, request_protocol, supplier_protocol):
        return chunk.replace(b"message_start", b"message_start_hooked")

    async def after_stream_chunk_conversion(self, chunk, request_protocol, supplier_protocol):
        return chunk.replace(b"hi", b"hi!")


@pytest.mark.asyncio
async def test_protocol_hooks_apply_to_non_stream_flow():
    now = utc_now()
    model_mapping = ModelMapping(
        requested_model="test-model",
        strategy="round_robin",
        matching_rules=None,
        capabilities=None,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    candidate = CandidateProvider(
        provider_id=1,
        provider_name="p-anthropic",
        base_url="https://example.com",
        protocol="anthropic",
        api_key="sk-test",
        target_model="claude-3-sonnet",
        priority=0,
        weight=1,
    )

    service = ProxyService(
        model_repo=AsyncMock(),
        provider_repo=AsyncMock(),
        log_repo=AsyncMock(),
        protocol_hooks=RecordingHooks(),
    )
    service._resolve_candidates = AsyncMock(
        return_value=(model_mapping, [candidate], 0, "openai", {})
    )  # type: ignore[method-assign]

    async def forward(*, body: dict, **kwargs):
        assert body["after"] is True
        return ProviderResponse(
            status_code=200,
            headers={"content-type": "application/json"},
            body={"upstream": "ok"},
        )

    fake_client = AsyncMock()
    fake_client.forward = AsyncMock(side_effect=forward)

    def fake_convert_request_for_supplier(*, body, **kwargs):
        assert body["before"] is True
        return "/v1/messages", {"converted": True}

    def fake_convert_response_for_user(*, body, **kwargs):
        assert body == {"wrapped": {"upstream": "ok"}}
        return {"converted_response": True}

    with patch(
        "app.services.proxy_service.convert_request_for_supplier",
        side_effect=fake_convert_request_for_supplier,
    ):
        with patch(
            "app.services.proxy_service.convert_response_for_user",
            side_effect=fake_convert_response_for_user,
        ):
            with patch(
                "app.services.proxy_service.get_provider_client",
                return_value=fake_client,
            ):
                response, _ = await service.process_request(
                    api_key_id=1,
                    api_key_name="k",
                    request_protocol="openai",
                    path="/v1/chat/completions",
                    method="POST",
                    headers={},
                    body={"model": "test-model", "messages": []},
                )

    assert response.body == {"after_response": {"converted_response": True}}
    service.log_repo.create.assert_awaited()


@pytest.mark.asyncio
async def test_protocol_hooks_apply_to_stream_chunks():
    now = utc_now()
    model_mapping = ModelMapping(
        requested_model="test-model",
        strategy="round_robin",
        matching_rules=None,
        capabilities=None,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    candidate = CandidateProvider(
        provider_id=1,
        provider_name="p-anthropic",
        base_url="https://example.com",
        protocol="anthropic",
        api_key="sk-test",
        target_model="claude-3-sonnet",
        priority=0,
        weight=1,
    )

    service = ProxyService(
        model_repo=AsyncMock(),
        provider_repo=AsyncMock(),
        log_repo=AsyncMock(),
        protocol_hooks=StreamHooks(),
    )
    service._resolve_candidates = AsyncMock(
        return_value=(model_mapping, [candidate], 0, "openai", {})
    )  # type: ignore[method-assign]

    def forward_stream(**kwargs):
        async def gen():
            response = ProviderResponse(status_code=200, headers={})
            yield b'data: {"type":"message_start"}\n\n', response

        return gen()

    fake_client = AsyncMock()
    fake_client.forward_stream = forward_stream

    async def fake_convert_stream_for_user(*, upstream, **kwargs):
        chunks = []
        async for chunk in upstream:
            chunks.append(chunk)
        assert chunks == [b'data: {"type":"message_start_hooked"}\n\n']
        for _ in chunks:
            yield b'data: {"choices":[{"delta":{"content":"hi"}}]}\n\n'

    with patch(
        "app.services.proxy_service.convert_request_for_supplier",
        return_value=("/v1/messages", {"converted": True}),
    ):
        with patch(
            "app.services.proxy_service.convert_stream_for_user",
            side_effect=fake_convert_stream_for_user,
        ):
            with patch(
                "app.services.proxy_service.get_provider_client",
                return_value=fake_client,
            ):
                initial_response, stream_gen, _ = await service.process_request_stream(
                    api_key_id=1,
                    api_key_name="k",
                    request_protocol="openai",
                    path="/v1/chat/completions",
                    method="POST",
                    headers={},
                    body={"model": "test-model", "stream": True, "messages": []},
                )

    assert initial_response.status_code == 200

    chunks = []
    async for chunk in stream_gen:
        chunks.append(chunk)

    assert chunks == [b'data: {"choices":[{"delta":{"content":"hi!"}}]}\n\n']
    service.log_repo.create.assert_awaited()


def _create_kv_model(value: str) -> KeyValueModel:
    """Helper to create a KeyValueModel for testing."""
    now = utc_now()
    return KeyValueModel(
        key="test_key",
        value=value,
        expires_at=None,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_inject_tool_call_extra_content_for_openai_protocol():
    """Test that extra_content is injected from KV store for openai protocol."""
    mock_kv_repo = AsyncMock()
    extra_content_data = {"google": {"thought_signature": "<Signature_A>"}}
    mock_kv_repo.get.return_value = _create_kv_model(json.dumps(extra_content_data))

    hooks = ProtocolConversionHooks(kv_repo=mock_kv_repo)

    supplier_body = {
        "messages": [
            {"role": "user", "content": "Check the weather in Paris and London."},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "function-call-f3b9ecb3-d55f-4076-98c8-b13e9d1c0e01",
                        "type": "function",
                        "function": {
                            "name": "get_current_temperature",
                            "arguments": '{"location":"Paris"}',
                        },
                    },
                    {
                        "id": "function-call-335673ad-913e-42d1-bbf5-387c8ab80f44",
                        "type": "function",
                        "function": {
                            "name": "get_current_temperature",
                            "arguments": '{"location":"London"}',
                        },
                    },
                ],
            },
            {
                "role": "tool",
                "name": "get_current_temperature",
                "tool_call_id": "function-call-f3b9ecb3-d55f-4076-98c8-b13e9d1c0e01",
                "content": '{"temp":"15C"}',
            },
        ],
    }

    result = await hooks.after_request_conversion(
        supplier_body=supplier_body,
        request_protocol="openai",
        supplier_protocol="openai",
    )

    assert mock_kv_repo.get.call_count == 2
    mock_kv_repo.get.assert_any_call(
        "tool_call_extra:function-call-f3b9ecb3-d55f-4076-98c8-b13e9d1c0e01"
    )
    mock_kv_repo.get.assert_any_call(
        "tool_call_extra:function-call-335673ad-913e-42d1-bbf5-387c8ab80f44"
    )

    assistant_message = result["messages"][1]
    assert assistant_message["tool_calls"][0]["extra_content"] == extra_content_data
    assert assistant_message["tool_calls"][1]["extra_content"] == extra_content_data


@pytest.mark.asyncio
async def test_inject_tool_call_extra_content_skipped_for_non_openai_protocol():
    """Test that extra_content injection is skipped for non-openai protocols."""
    mock_kv_repo = AsyncMock()
    hooks = ProtocolConversionHooks(kv_repo=mock_kv_repo)

    supplier_body = {
        "messages": [
            {
                "role": "assistant",
                "tool_calls": [
                    {"id": "call-123", "type": "function", "function": {"name": "test"}},
                ],
            },
        ],
    }

    result = await hooks.after_request_conversion(
        supplier_body=supplier_body,
        request_protocol="openai",
        supplier_protocol="anthropic",
    )

    mock_kv_repo.get.assert_not_called()
    assert "extra_content" not in result["messages"][0]["tool_calls"][0]


@pytest.mark.asyncio
async def test_inject_tool_call_extra_content_skipped_without_kv_repo():
    """Test that extra_content injection is skipped when kv_repo is None."""
    hooks = ProtocolConversionHooks(kv_repo=None)

    supplier_body = {
        "messages": [
            {
                "role": "assistant",
                "tool_calls": [
                    {"id": "call-123", "type": "function", "function": {"name": "test"}},
                ],
            },
        ],
    }

    result = await hooks.after_request_conversion(
        supplier_body=supplier_body,
        request_protocol="openai",
        supplier_protocol="openai",
    )

    assert "extra_content" not in result["messages"][0]["tool_calls"][0]


@pytest.mark.asyncio
async def test_inject_tool_call_extra_content_handles_missing_cache():
    """Test that missing cache entries are handled gracefully."""
    mock_kv_repo = AsyncMock()
    mock_kv_repo.get.return_value = None

    hooks = ProtocolConversionHooks(kv_repo=mock_kv_repo)

    supplier_body = {
        "messages": [
            {
                "role": "assistant",
                "tool_calls": [
                    {"id": "call-123", "type": "function", "function": {"name": "test"}},
                ],
            },
        ],
    }

    result = await hooks.after_request_conversion(
        supplier_body=supplier_body,
        request_protocol="openai",
        supplier_protocol="openai",
    )

    mock_kv_repo.get.assert_called_once_with("tool_call_extra:call-123")
    assert "extra_content" not in result["messages"][0]["tool_calls"][0]


@pytest.mark.asyncio
async def test_inject_tool_call_extra_content_handles_kv_error():
    """Test that KV store errors are handled gracefully."""
    mock_kv_repo = AsyncMock()
    mock_kv_repo.get.side_effect = Exception("KV store error")

    hooks = ProtocolConversionHooks(kv_repo=mock_kv_repo)

    supplier_body = {
        "messages": [
            {
                "role": "assistant",
                "tool_calls": [
                    {"id": "call-123", "type": "function", "function": {"name": "test"}},
                ],
            },
        ],
    }

    result = await hooks.after_request_conversion(
        supplier_body=supplier_body,
        request_protocol="openai",
        supplier_protocol="openai",
    )

    assert "extra_content" not in result["messages"][0]["tool_calls"][0]


@pytest.mark.asyncio
async def test_inject_tool_call_extra_content_skips_tool_call_without_id():
    """Test that tool_calls without id are skipped."""
    mock_kv_repo = AsyncMock()
    hooks = ProtocolConversionHooks(kv_repo=mock_kv_repo)

    supplier_body = {
        "messages": [
            {
                "role": "assistant",
                "tool_calls": [
                    {"type": "function", "function": {"name": "test"}},
                ],
            },
        ],
    }

    result = await hooks.after_request_conversion(
        supplier_body=supplier_body,
        request_protocol="openai",
        supplier_protocol="openai",
    )

    mock_kv_repo.get.assert_not_called()
    assert "extra_content" not in result["messages"][0]["tool_calls"][0]


@pytest.mark.asyncio
async def test_cache_tool_call_extra_content_from_stream():
    """Test that extra_content is cached from stream chunks."""
    mock_kv_repo = AsyncMock()
    hooks = ProtocolConversionHooks(kv_repo=mock_kv_repo)

    extra_content = {"google": {"thought_signature": "<Signature_A>"}}
    chunk_data = {
        "choices": [
            {
                "delta": {
                    "tool_calls": [
                        {
                            "id": "call-abc-123",
                            "type": "function",
                            "function": {"name": "get_weather"},
                            "extra_content": extra_content,
                        }
                    ]
                }
            }
        ]
    }
    chunk = f"data: {json.dumps(chunk_data)}\n\n".encode("utf-8")

    result = await hooks.before_stream_chunk_conversion(
        chunk=chunk,
        request_protocol="openai",
        supplier_protocol="gemini",
    )

    mock_kv_repo.set.assert_called_once()
    call_args = mock_kv_repo.set.call_args
    assert call_args[0][0] == "tool_call_extra:call-abc-123"
    assert json.loads(call_args[0][1]) == extra_content
    assert result == chunk


@pytest.mark.asyncio
async def test_cache_tool_call_extra_content_skipped_without_kv_repo():
    """Test that caching is skipped when kv_repo is None."""
    hooks = ProtocolConversionHooks(kv_repo=None)

    extra_content = {"google": {"thought_signature": "<Signature_A>"}}
    chunk_data = {
        "choices": [
            {
                "delta": {
                    "tool_calls": [
                        {
                            "id": "call-abc-123",
                            "extra_content": extra_content,
                        }
                    ]
                }
            }
        ]
    }
    chunk = f"data: {json.dumps(chunk_data)}\n\n".encode("utf-8")

    result = await hooks.before_stream_chunk_conversion(
        chunk=chunk,
        request_protocol="openai",
        supplier_protocol="gemini",
    )

    assert result == chunk


@pytest.mark.asyncio
async def test_cache_tool_call_extra_content_from_non_stream_response():
    """Test that extra_content is cached from non-streaming response."""
    mock_kv_repo = AsyncMock()
    hooks = ProtocolConversionHooks(kv_repo=mock_kv_repo)

    extra_content = {"google": {"thought_signature": "xxxxxxxxxxxxxxxxxxxxx"}}
    supplier_body = {
        "choices": [
            {
                "finish_reason": "tool_calls",
                "index": 0,
                "message": {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "extra_content": extra_content,
                            "function": {
                                "arguments": '{"content":"test","path":"test.md"}',
                                "name": "write",
                            },
                            "id": "function-call-8949365993964308019",
                            "type": "function",
                        },
                        {
                            "function": {
                                "arguments": '{"content":"test2","path":"test2.md"}',
                                "name": "write",
                            },
                            "id": "function-call-8949365993964308086",
                            "type": "function",
                        },
                    ],
                },
            }
        ],
        "created": 1769939894,
        "id": "tiN_abDiFcDcqtsP9Yvq2Qc",
        "model": "gemini-3-pro-preview",
        "object": "chat.completion",
        "usage": {
            "completion_tokens": 177,
            "prompt_tokens": 13146,
            "total_tokens": 13617,
        },
    }

    result = await hooks.before_response_conversion(
        supplier_body=supplier_body,
        request_protocol="openai",
        supplier_protocol="gemini",
    )

    mock_kv_repo.set.assert_called_once()
    call_args = mock_kv_repo.set.call_args
    assert call_args[0][0] == "tool_call_extra:function-call-8949365993964308019"
    assert json.loads(call_args[0][1]) == extra_content
    assert result == supplier_body


@pytest.mark.asyncio
async def test_cache_tool_call_extra_content_from_non_stream_response_multiple_tool_calls():
    """Test that extra_content is cached for multiple tool_calls with extra_content."""
    mock_kv_repo = AsyncMock()
    hooks = ProtocolConversionHooks(kv_repo=mock_kv_repo)

    extra_content_1 = {"google": {"thought_signature": "signature_1"}}
    extra_content_2 = {"google": {"thought_signature": "signature_2"}}
    supplier_body = {
        "choices": [
            {
                "finish_reason": "tool_calls",
                "index": 0,
                "message": {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "extra_content": extra_content_1,
                            "function": {"arguments": "{}", "name": "func1"},
                            "id": "call-id-001",
                            "type": "function",
                        },
                        {
                            "extra_content": extra_content_2,
                            "function": {"arguments": "{}", "name": "func2"},
                            "id": "call-id-002",
                            "type": "function",
                        },
                    ],
                },
            }
        ],
    }

    result = await hooks.before_response_conversion(
        supplier_body=supplier_body,
        request_protocol="openai",
        supplier_protocol="gemini",
    )

    assert mock_kv_repo.set.call_count == 2
    calls = mock_kv_repo.set.call_args_list
    assert calls[0][0][0] == "tool_call_extra:call-id-001"
    assert json.loads(calls[0][0][1]) == extra_content_1
    assert calls[1][0][0] == "tool_call_extra:call-id-002"
    assert json.loads(calls[1][0][1]) == extra_content_2
    assert result == supplier_body


@pytest.mark.asyncio
async def test_cache_non_stream_response_skipped_without_kv_repo():
    """Test that caching is skipped for non-streaming response when kv_repo is None."""
    hooks = ProtocolConversionHooks(kv_repo=None)

    supplier_body = {
        "choices": [
            {
                "message": {
                    "tool_calls": [
                        {
                            "extra_content": {"google": {"thought_signature": "sig"}},
                            "id": "call-123",
                        }
                    ]
                }
            }
        ]
    }

    result = await hooks.before_response_conversion(
        supplier_body=supplier_body,
        request_protocol="openai",
        supplier_protocol="gemini",
    )

    assert result == supplier_body


@pytest.mark.asyncio
async def test_cache_non_stream_response_skipped_for_non_dict_body():
    """Test that caching is skipped when supplier_body is not a dict."""
    mock_kv_repo = AsyncMock()
    hooks = ProtocolConversionHooks(kv_repo=mock_kv_repo)

    supplier_body = "not a dict"

    result = await hooks.before_response_conversion(
        supplier_body=supplier_body,
        request_protocol="openai",
        supplier_protocol="gemini",
    )

    mock_kv_repo.set.assert_not_called()
    assert result == supplier_body


@pytest.mark.asyncio
async def test_cache_non_stream_response_skips_tool_call_without_id():
    """Test that tool_calls without id are skipped in non-streaming response."""
    mock_kv_repo = AsyncMock()
    hooks = ProtocolConversionHooks(kv_repo=mock_kv_repo)

    supplier_body = {
        "choices": [
            {
                "message": {
                    "tool_calls": [
                        {
                            "extra_content": {"google": {"thought_signature": "sig"}},
                            "type": "function",
                        }
                    ]
                }
            }
        ]
    }

    result = await hooks.before_response_conversion(
        supplier_body=supplier_body,
        request_protocol="openai",
        supplier_protocol="gemini",
    )

    mock_kv_repo.set.assert_not_called()
    assert result == supplier_body


@pytest.mark.asyncio
async def test_cache_non_stream_response_skips_tool_call_without_extra_content():
    """Test that tool_calls without extra_content are skipped."""
    mock_kv_repo = AsyncMock()
    hooks = ProtocolConversionHooks(kv_repo=mock_kv_repo)

    supplier_body = {
        "choices": [
            {
                "message": {
                    "tool_calls": [
                        {
                            "id": "call-123",
                            "function": {"name": "test"},
                            "type": "function",
                        }
                    ]
                }
            }
        ]
    }

    result = await hooks.before_response_conversion(
        supplier_body=supplier_body,
        request_protocol="openai",
        supplier_protocol="gemini",
    )

    mock_kv_repo.set.assert_not_called()
    assert result == supplier_body


@pytest.mark.asyncio
async def test_cache_non_stream_response_handles_kv_error():
    """Test that KV store errors are handled gracefully in non-streaming response."""
    mock_kv_repo = AsyncMock()
    mock_kv_repo.set.side_effect = Exception("KV store error")

    hooks = ProtocolConversionHooks(kv_repo=mock_kv_repo)

    supplier_body = {
        "choices": [
            {
                "message": {
                    "tool_calls": [
                        {
                            "extra_content": {"google": {"thought_signature": "sig"}},
                            "id": "call-123",
                        }
                    ]
                }
            }
        ]
    }

    result = await hooks.before_response_conversion(
        supplier_body=supplier_body,
        request_protocol="openai",
        supplier_protocol="gemini",
    )

    mock_kv_repo.set.assert_called_once()
    assert result == supplier_body
