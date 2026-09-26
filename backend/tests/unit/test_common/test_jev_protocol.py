"""
Tests for Jev protocol registration, identity conversion and token counting.
"""

import pytest

from app.common.errors import ServiceError
from app.common.protocol import Protocol
from app.common.protocol_conversion import (
    convert_request_for_supplier,
    convert_response_for_user,
    normalize_protocol,
)
from app.common.provider_protocols import (
    IMPLEMENTATION_PROTOCOLS,
    JEV_PROTOCOL,
    get_frontend_protocol_config,
    resolve_implementation_protocol,
)
from app.common.token_counter import JevTokenCounter, get_token_counter
from app.common.usage_extractor import extract_output_tokens, extract_usage_details


def _jev_body(**overrides):
    body = {
        "model": "jev-latest",
        "state": "Help! My payouts have been failing for 3 days.",
        "questions": {
            "is_urgent": {
                "type": "noul",
                "instructions": "Does this convey urgency?",
                "criteria": {"true": "Explicitly time-sensitive", "false": "No urgency"},
            }
        },
    }
    body.update(overrides)
    return body


class TestJevProtocolRegistration:
    def test_jev_is_an_implementation_protocol(self):
        assert JEV_PROTOCOL == "jev"
        assert JEV_PROTOCOL in IMPLEMENTATION_PROTOCOLS

    def test_frontend_config_defaults(self):
        config = get_frontend_protocol_config("jev")
        assert config.frontend == "jev"
        assert config.implementation == "jev"
        assert config.base_url == "https://api.typesafe.ai/v1"
        assert config.label == "TypeSafe Jev"

    def test_resolve_implementation_protocol(self):
        assert resolve_implementation_protocol("jev") == "jev"
        assert resolve_implementation_protocol("JEV") == "jev"

    def test_normalize_protocol(self):
        assert normalize_protocol("jev") == "jev"

    def test_protocol_enum_roundtrip(self):
        assert Protocol.from_string("jev") is Protocol.JEV
        assert Protocol.JEV.value == "jev"


class TestJevIdentityConversion:
    def test_only_model_is_rewritten(self):
        body = _jev_body()
        path, converted = convert_request_for_supplier(
            request_protocol="jev",
            supplier_protocol="jev",
            path="/v1/systemone",
            body=body,
            target_model="jev-1.13.0",
        )

        assert path == "/v1/systemone"
        assert converted["model"] == "jev-1.13.0"
        assert converted["state"] == body["state"]
        assert converted["questions"] == body["questions"]
        # The original body must not be mutated.
        assert body["model"] == "jev-latest"

    def test_default_parameters_are_not_injected(self):
        """Jev rejects unknown fields with 422, so chat-style defaults must not leak."""
        _path, converted = convert_request_for_supplier(
            request_protocol="jev",
            supplier_protocol="jev",
            path="/v1/systemone",
            body=_jev_body(),
            target_model="jev-1.13.0",
            options={
                "default_parameters": {
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "top_k": 5,
                    "max_tokens": 4096,
                }
            },
        )

        for leaked in ("temperature", "top_p", "top_k", "max_tokens", "max_completion_tokens"):
            assert leaked not in converted
        assert set(converted) == {"model", "state", "questions"}

    def test_structured_state_and_instructions_survive(self):
        body = {
            "model": "jev-latest",
            "state": [{"role": "user", "text": "hi"}],
            "questions": {
                "dup": {
                    "type": "noul",
                    "instructions": {
                        "potential_duplicate": {"name": "John Smith"},
                        "question": "Same person as `potential_duplicate`?",
                    },
                },
                "dept": {
                    "type": "choice",
                    "instructions": "Which team?",
                    "criteria": {"billing": "Payments", "technical": None},
                },
                "mood": {
                    "type": "score",
                    "instructions": "How frustrated?",
                    "criteria": ["Calm", "Frustrated", "Very angry"],
                },
            },
        }
        _path, converted = convert_request_for_supplier(
            request_protocol="jev",
            supplier_protocol="jev",
            path="/v1/systemone",
            body=body,
            target_model="jev-1.13.0",
        )
        assert converted["state"] == body["state"]
        assert converted["questions"] == body["questions"]

    def test_response_passthrough_is_identity(self):
        response = {
            "model": "jev-1.13.0",
            "answers": {"is_urgent": {"type": "noul", "noul": 0.95}},
            "usage": {"input_tokens": 296, "output_tokens": 20},
        }
        assert (
            convert_response_for_user(
                request_protocol="jev",
                supplier_protocol="jev",
                body=response,
                target_model="jev-1.13.0",
            )
            is response
        )

    @pytest.mark.parametrize(
        "request_protocol,supplier_protocol",
        [
            ("openai", "jev"),
            ("jev", "openai"),
            ("anthropic", "jev"),
            ("jev", "anthropic"),
            ("openai_responses", "jev"),
            ("jev", "gemini"),
        ],
    )
    def test_cross_protocol_conversion_is_rejected(
        self, request_protocol, supplier_protocol
    ):
        with pytest.raises(ServiceError) as excinfo:
            convert_request_for_supplier(
                request_protocol=request_protocol,
                supplier_protocol=supplier_protocol,
                path="/v1/systemone",
                body=_jev_body(),
                target_model="target",
            )
        assert excinfo.value.code == "unsupported_protocol_conversion"


class TestJevTokenCounter:
    def test_get_token_counter_returns_jev_counter(self):
        assert isinstance(get_token_counter("jev"), JevTokenCounter)
        assert isinstance(get_token_counter("JEV"), JevTokenCounter)

    def test_counts_state_and_questions(self):
        counter = JevTokenCounter()
        total = counter.count_request(_jev_body())
        assert total > 0

        # Adding another question increases the estimate.
        body = _jev_body()
        body["questions"]["dept"] = {
            "type": "choice",
            "instructions": "Which team should handle this?",
            "criteria": {"billing": "Payments, invoicing, refunds"},
        }
        assert counter.count_request(body) > total

    def test_longer_state_increases_estimate(self):
        counter = JevTokenCounter()
        short = counter.count_request(_jev_body(state="hi"))
        long = counter.count_request(_jev_body(state="word " * 500))
        assert long > short

    def test_structured_instructions_are_counted(self):
        counter = JevTokenCounter()
        plain = counter.count_request(
            {
                "model": "m",
                "state": "s",
                "questions": {"q": {"type": "noul", "instructions": "short"}},
            }
        )
        structured = counter.count_request(
            {
                "model": "m",
                "state": "s",
                "questions": {
                    "q": {
                        "type": "noul",
                        "instructions": {
                            "reference": {"name": "John Smith", "city": "Oakland"},
                            "question": "Is this the same person as `reference`?",
                        },
                    }
                },
            }
        )
        assert structured > plain

    def test_missing_and_malformed_fields_are_safe(self):
        counter = JevTokenCounter()
        assert counter.count_request({}) == 0
        assert counter.count_request({"model": "m"}) == 0
        assert counter.count_request("not a dict") == 0
        # questions as a non-dict must not raise
        assert counter.count_request({"state": "s", "questions": ["x"]}) > 0
        assert counter.count_request({"state": "s", "questions": {"q": "raw"}}) > 0

    def test_count_output_body_from_answers(self):
        counter = JevTokenCounter()
        assert (
            counter.count_output_body(
                {"answers": {"is_urgent": {"type": "noul", "noul": 0.95}}}
            )
            > 0
        )
        assert counter.count_output_body(None) == 0
        assert counter.count_output_body({}) == 0
        assert counter.count_output_body({"model": "jev-1.13.0"}) == 0

    def test_count_output_body_accepts_bytes_and_str(self):
        counter = JevTokenCounter()
        payload = '{"answers": {"a": {"type": "noul", "noul": 0.5}}}'
        assert counter.count_output_body(payload.encode("utf-8")) > 0
        assert counter.count_output_body(payload) > 0
        assert counter.count_output_body(b"\xff\xfe not json") == 0


class TestJevUsageExtraction:
    def test_usage_is_extracted_without_cache_inflation(self):
        details = extract_usage_details(
            {
                "model": "jev-1.13.0",
                "answers": {},
                "usage": {"input_tokens": 296, "output_tokens": 20},
            }
        )
        assert details is not None
        assert details.input_tokens == 296
        assert details.output_tokens == 20
        assert details.total_tokens == 316
        assert details.source == "upstream"
        assert details.cache_creation_input_tokens is None

    def test_usage_extracted_from_raw_bytes(self):
        raw = b'{"model":"jev-1.13.0","answers":{},"usage":{"input_tokens":10,"output_tokens":2}}'
        details = extract_usage_details(raw)
        assert details.input_tokens == 10
        assert extract_output_tokens(raw) == 2


class TestJevTokenCounterFallbacks:
    def test_falls_back_to_char_estimate_without_tiktoken(self, monkeypatch):
        import app.common.token_counter as tc

        monkeypatch.setattr(tc, "TIKTOKEN_AVAILABLE", False)
        counter = tc.JevTokenCounter()
        assert counter._get_encoding("jev-latest") is None
        # 40 chars // 4 == 10
        assert counter.count_tokens("x" * 40) == 10
        assert counter.count_tokens("") == 0

    def test_falls_back_when_encoding_lookup_raises(self, monkeypatch):
        import app.common.token_counter as tc

        class Boom:
            def get_encoding(self, name):
                raise RuntimeError("no encoding")

        monkeypatch.setattr(tc, "TIKTOKEN_AVAILABLE", True)
        monkeypatch.setattr(tc, "tiktoken", Boom())
        counter = tc.JevTokenCounter()
        assert counter._get_encoding("jev-latest") is None
        assert counter.count_tokens("abcd" * 10) > 0

    def test_falls_back_when_encoding_raises(self, monkeypatch):
        import app.common.token_counter as tc

        class BadEncoding:
            def encode(self, text, disallowed_special=()):
                raise RuntimeError("bad encode")

        counter = tc.JevTokenCounter()
        monkeypatch.setattr(counter, "_get_encoding", lambda model: BadEncoding())
        assert counter.count_tokens("x" * 40) == 10

    def test_count_messages_shim_counts_text(self):
        """Jev has no message list, but the abstract base requires the method."""
        counter = JevTokenCounter()
        with_text = counter.count_messages([{"role": "user", "content": "hello"}])
        empty = counter.count_messages([])
        assert with_text > empty

    def test_count_output_body_non_json_string(self):
        counter = JevTokenCounter()
        assert counter.count_output_body("plain text answer") > 0

    def test_non_serializable_payload_falls_back_to_str(self):
        """A state value json.dumps cannot handle must not break estimation."""

        class Opaque:
            def __repr__(self):
                return "opaque-state-value"

        counter = JevTokenCounter()
        assert counter.count_request({"state": Opaque(), "questions": {}}) > 0
