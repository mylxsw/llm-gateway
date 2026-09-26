"""
Tests for the admin-facing Jev surfaces: model test payload, response
rendering and the log playground path/stream resolution.
"""

import pytest

from app.api.admin.logs import (
    _build_playground_request_path,
    _is_playground_stream,
)
from app.api.admin.models import (
    _build_test_payload,
    _extract_text_from_response,
)
from app.common.provider_protocols import list_frontend_protocol_configs


class TestJevTestPayload:
    def test_builds_systemone_payload(self):
        path, body, implementation = _build_test_payload(
            requested_model="jev-latest", protocol="jev", stream=False
        )
        assert path == "/v1/systemone"
        assert implementation == "jev"
        assert body["model"] == "jev-latest"
        assert body["state"]
        assert body["questions"]["is_greeting"]["type"] == "noul"
        # Jev has no stream flag in its request schema.
        assert "stream" not in body

    def test_stream_flag_is_ignored(self):
        _path, body, _impl = _build_test_payload(
            requested_model="jev-latest", protocol="jev", stream=True
        )
        assert "stream" not in body

    def test_other_protocols_are_unaffected(self):
        path, body, implementation = _build_test_payload(
            requested_model="gpt-4o-mini", protocol="openai", stream=False
        )
        assert path == "/v1/chat/completions"
        assert implementation == "openai"
        assert body["messages"]


class TestJevResponseRendering:
    def test_answers_are_rendered(self):
        text = _extract_text_from_response(
            {
                "model": "jev-1.13.0",
                "answers": {"is_greeting": {"type": "noul", "noul": 0.9}},
            },
            "jev",
        )
        assert "is_greeting" in text
        assert "0.9" in text

    def test_error_message_wins_over_answers(self):
        text = _extract_text_from_response(
            {"error": {"message": "unprocessable"}}, "jev"
        )
        assert text == "unprocessable"

    def test_missing_answers_falls_back_to_raw_body(self):
        """Without answers the shared fallback dumps the body, which is what the
        test dialog needs in order to show an unexpected upstream payload."""
        assert (
            _extract_text_from_response({"model": "jev-1.13.0"}, "jev")
            == '{"model": "jev-1.13.0"}'
        )


class TestJevPlayground:
    def test_playground_path_is_systemone(self):
        assert (
            _build_playground_request_path(
                protocol="jev", request_body={"model": "jev-latest"}, fallback_path=None
            )
            == "/v1/systemone"
        )

    @pytest.mark.parametrize(
        "body",
        [
            {"model": "jev-latest"},
            {"model": "jev-latest", "stream": True},
            {"model": "jev-latest", "stream": "yes"},
        ],
    )
    def test_playground_never_streams(self, body):
        assert (
            _is_playground_stream(
                protocol="jev", request_body=body, request_path="/v1/systemone"
            )
            is False
        )

    def test_openai_playground_still_streams(self):
        assert (
            _is_playground_stream(
                protocol="openai",
                request_body={"stream": True},
                request_path="/v1/chat/completions",
            )
            is True
        )


class TestJevProtocolIsExposedToAdminUI:
    def test_jev_appears_in_protocol_configs(self):
        configs = {c.frontend: c for c in list_frontend_protocol_configs()}
        assert "jev" in configs
        assert configs["jev"].implementation == "jev"
        assert configs["jev"].label == "TypeSafe Jev"
