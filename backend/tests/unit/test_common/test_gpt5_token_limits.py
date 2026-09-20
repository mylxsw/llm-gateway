"""Regression coverage for GPT-5 chat completion token limits."""

from copy import deepcopy

import pytest

from app.common.protocol_conversion import convert_request_for_supplier


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("target_model", ["gpt-5", "gpt-5-mini", "gpt-5.6-luna"])
@pytest.mark.parametrize(
    "limits,options,expected",
    [
        ({"max_tokens": 1024}, None, {"max_completion_tokens": 1024}),
        ({"max_tokens": 1024, "max_completion_tokens": 2048}, None,
         {"max_completion_tokens": 2048}),
        ({"max_tokens": 1024, "max_completion_tokens": None}, None,
         {"max_completion_tokens": 1024}),
        ({"max_tokens": 1024, "max_completion_tokens": 0}, None,
         {"max_completion_tokens": 0}),
        ({"max_completion_tokens": 512}, None, {"max_completion_tokens": 512}),
        ({}, None, {}),
        ({}, {"default_parameters": {"max_tokens": 4096}},
         {"max_completion_tokens": 4096}),
        ({"max_tokens": 1024}, {"default_parameters": {"max_tokens": 4096}},
         {"max_completion_tokens": 1024}),
        ({"max_completion_tokens": 512}, {"default_parameters": {"max_tokens": 4096}},
         {"max_completion_tokens": 512}),
    ],
)
def test_gpt5_token_limits(stream, target_model, limits, options, expected):
    body = {
        "model": "public-alias",
        "messages": [{"role": "user", "content": "hello"}],
        "stream": stream,
        **limits,
    }
    original = deepcopy(body)

    path, converted = convert_request_for_supplier(
        request_protocol="openai",
        supplier_protocol="openai",
        path="/v1/chat/completions",
        body=body,
        target_model=target_model,
        options=options,
    )

    assert path == "/v1/chat/completions"
    expected_body = {
        key: value for key, value in original.items()
        if key not in ("max_tokens", "max_completion_tokens")
    }
    assert converted == {
        **expected_body,
        "model": target_model,
        **expected,
    }
    assert body == original
    assert "max_tokens" not in converted


@pytest.mark.parametrize(
    "protocol,path,target_model",
    [
        ("openai", "/v1/chat/completions", "gpt-4o"),
        ("openai", "/v1/chat/completions", "deepseek-chat"),
        ("openai", "/v1/chat/completions", "gpt-50"),
        ("openai", "/v1/completions", "gpt-5"),
        ("openai", "/v1/embeddings", "gpt-5"),
        ("openai_responses", "/v1/responses", "gpt-5"),
        ("anthropic", "/v1/messages", "gpt-5"),
    ],
)
def test_other_targets_preserve_legacy_limit(protocol, path, target_model):
    body = {
        "model": "gpt-5.6-luna",
        "messages": [{"role": "user", "content": "hello"}],
        "max_tokens": 1024,
    }
    _, converted = convert_request_for_supplier(
        request_protocol=protocol,
        supplier_protocol=protocol,
        path=path,
        body=body,
        target_model=target_model,
    )

    assert converted["max_tokens"] == 1024
    assert "max_completion_tokens" not in converted


def test_anthropic_request_to_gpt5_uses_completion_limit():
    path, converted = convert_request_for_supplier(
        request_protocol="anthropic",
        supplier_protocol="openai",
        path="/v1/messages",
        body={"messages": [{"role": "user", "content": "hello"}], "max_tokens": 1024},
        target_model="gpt-5.6-luna",
    )

    assert path == "/v1/chat/completions"
    assert converted["max_completion_tokens"] == 1024
    assert "max_tokens" not in converted
