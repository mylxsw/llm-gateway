"""Recover rejected structured output formats without changing the caller's contract."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from functools import cached_property
from typing import Any

import jsonschema_rs

from app.common.errors import ServiceError
from app.common.openai_responses import _extract_assistant_text_from_responses
from app.common.protocol_conversion import convert_response_for_user
from app.common.stream_usage import SSEDecoder
from app.providers.base import ProviderResponse
from app.rules.models import CandidateProvider
from app.services.model_turn_repair import (
    CandidateKey,
    ModelTurnRepair,
    _error_messages,
)

logger = logging.getLogger(__name__)

_FORMAT_FIELD = re.compile(
    r"response[ _.-]?format|text\.format|output_config[ .]format|"
    r"response_?(?:json_?)?schema|response_?mime_?type|json_schema|json mode|structured output"
)
_REJECTION = re.compile(
    r"not (?:\w+ )?(?:supported|available|allowed|permitted|enabled)|"
    r"unavailable|unsupported|does not support|do not support|unknown format|"
    r"unrecognized|unknown (?:field|parameter|argument)|invalid enum|"
    r"extra inputs|must be one of|expected one of|only supports?|only accepts?|accepts? only|"
    r"only allowed|only available|only works|cannot be used|input should be|"
    r"must be true|requires? strict"
)
_MAX_BUFFERED_STREAM_BYTES = 16 * 1024 * 1024


def _json_object(raw: Any) -> dict[str, Any]:
    if isinstance(raw, (bytes, str)):
        raw = json.loads(raw)
    if not isinstance(raw, dict):
        raise TypeError("Expected a JSON object")
    return raw


def _format_rejection(response: ProviderResponse) -> str | None:
    if response.status_code not in (400, 422):
        return None
    messages = [*_error_messages(response.body), *_error_messages(response.error)]
    try:
        payload = _json_object(response.body)
    except (TypeError, ValueError):
        payload = {}
    error = payload.get("error")
    if isinstance(error, dict) and isinstance(error.get("param"), str):
        messages.append(
            f"{error['param']} {error.get('code', '')} {error.get('message', '')}"
        )
    detail = payload.get("detail")
    if isinstance(detail, list):
        for issue in detail:
            if isinstance(issue, dict):
                location = issue.get("loc")
                path = (
                    ".".join(str(part) for part in location)
                    if isinstance(location, list)
                    else ""
                )
                messages.append(f"{path} {issue.get('msg', '')}")
    for message in messages:
        normalized = " ".join(
            message.casefold().replace("unsupported_value", "unsupported value").split()
        )
        if _FORMAT_FIELD.search(normalized) and _REJECTION.search(normalized):
            return normalized
    return None


def _invalid_output(response: ProviderResponse) -> ProviderResponse:
    message = "The upstream response did not match the requested JSON format."
    return ProviderResponse(
        status_code=502,
        error=message,
        body={
            "error": {
                "message": message,
                "type": "upstream_error",
                "code": "invalid_structured_output",
            }
        },
        first_byte_delay_ms=response.first_byte_delay_ms,
        total_time_ms=response.total_time_ms,
    )


def _reject_external_schema(_uri: str) -> None:
    # A schema supplied by a caller can only reference definitions it contains.
    raise ValueError("External schema references are unavailable")


def _reject_json_constant(_value: str) -> None:
    raise ValueError("Invalid JSON constant")


@dataclass(frozen=True)
class _Format:
    kind: str
    schema: dict[str, Any] | None = None
    name: str | None = None
    strict: bool = False

    @cached_property
    def validator(self) -> jsonschema_rs.Validator | None:
        if self.schema is None:
            return None
        return jsonschema_rs.validator_for(
            self.schema,
            retriever=_reject_external_schema,
            pattern_options=jsonschema_rs.FancyRegexOptions(backtrack_limit=100_000),
        )

    def accepts(self, text: str) -> bool:
        try:
            value = json.loads(text, parse_constant=_reject_json_constant)
            if self.kind == "json_object":
                return isinstance(value, dict)
            return self.validator is not None and self.validator.is_valid(value)
        except (
            TypeError,
            ValueError,
            OverflowError,
            RecursionError,
            jsonschema_rs.ValidationError,
        ):
            return False


def _request_format(path: str, body: dict[str, Any]) -> _Format | None:
    if path == "/v1/chat/completions":
        config = body.get("response_format")
        schema = config.get("json_schema") if isinstance(config, dict) else None
    elif path == "/v1/responses":
        text = body.get("text")
        config = text.get("format") if isinstance(text, dict) else None
        schema = config
    else:
        return None
    kind = config.get("type") if isinstance(config, dict) else None
    if kind in ("text", "json_object"):
        return _Format(kind)
    if (
        kind == "json_schema"
        and isinstance(schema, dict)
        and isinstance(schema.get("schema"), dict)
    ):
        return _Format(
            kind, schema["schema"], schema.get("name"), schema.get("strict") is True
        )
    return None


def _with_instruction(body: dict[str, Any], protocol: str, instruction: str) -> None:
    if protocol == "openai":
        body["messages"] = [
            {"role": "system", "content": instruction},
            *body["messages"],
        ]
    elif protocol == "openai_responses":
        body["instructions"] = "\n\n".join(
            filter(None, (body.get("instructions"), instruction))
        )
    elif protocol == "anthropic":
        system = body.get("system")
        if isinstance(system, str):
            system = [{"type": "text", "text": system}]
        body["system"] = [*(system or []), {"type": "text", "text": instruction}]
    elif protocol == "gemini":
        system = dict(body.get("systemInstruction") or {})
        system["parts"] = [*(system.get("parts") or []), {"text": instruction}]
        body["systemInstruction"] = system


@dataclass(frozen=True)
class _Attempt:
    protocol: str
    mode: str
    validate_output: bool = False


class ResponseFormatRecovery:
    """Track format changes for each candidate until it succeeds or fails over."""

    def __init__(self, path: str, body: dict[str, Any], request_protocol: str) -> None:
        self._format = _request_format(path, body)
        self._request_protocol = request_protocol
        self._next_modes: dict[CandidateKey, str] = {}
        self._attempts: dict[CandidateKey, _Attempt] = {}

    def prepare(
        self, candidate: CandidateProvider, protocol: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        requested = self._format
        if requested is None or protocol not in (
            "openai",
            "openai_responses",
            "anthropic",
            "gemini",
        ):
            return body

        key = ModelTurnRepair._key(candidate)
        mode = self._next_modes.get(key, requested.kind)
        # Native Anthropic has no free-form JSON-object mode.
        if protocol == "anthropic" and mode in ("text", "json_object"):
            mode = "omit"
        validate = (
            requested.kind != "text"
            and mode in ("json_object", "omit")
            and (mode != requested.kind or key in self._next_modes)
        )
        self._attempts[key] = _Attempt(protocol, mode, validate)

        if mode == requested.kind and protocol in ("openai", "openai_responses"):
            return body

        out = dict(body)
        format_config = {"type": "json_object"} if mode == "json_object" else None
        if mode == "strict_schema":
            schema = {
                "name": requested.name,
                "schema": requested.schema,
                "strict": True,
            }
            format_config = {"type": "json_schema", "json_schema": schema}
            if protocol == "openai_responses":
                format_config = {"type": "json_schema", **schema}

        if protocol == "openai":
            if format_config is None:
                out.pop("response_format", None)
            else:
                out["response_format"] = format_config
        elif protocol == "openai_responses":
            text = dict(out.get("text") or {})
            text.pop("format", None)
            if format_config is not None:
                text["format"] = format_config
            if text:
                out["text"] = text
            else:
                out.pop("text", None)
        elif protocol == "anthropic":
            config = dict(out.get("output_config") or {})
            config.pop("format", None)
            if mode == "json_schema":
                config["format"] = {"type": "json_schema", "schema": requested.schema}
            if config:
                out["output_config"] = config
            else:
                out.pop("output_config", None)
        else:
            config = dict(out.get("generationConfig") or {})
            config.pop("responseSchema", None)
            config.pop("responseJsonSchema", None)
            if mode in ("json_schema", "json_object"):
                config["responseMimeType"] = "application/json"
            else:
                config.pop("responseMimeType", None)
            if mode == "json_schema":
                config["responseJsonSchema"] = requested.schema
            if config:
                out["generationConfig"] = config
            else:
                out.pop("generationConfig", None)

        if validate:
            instruction = (
                "Return only valid JSON. Do not use Markdown or surrounding commentary."
            )
            if requested.schema is None:
                instruction += " Return a JSON object."
            else:
                instruction += (
                    " The JSON must conform to this JSON Schema:\n"
                    + json.dumps(requested.schema, ensure_ascii=False)
                )
            _with_instruction(out, protocol, instruction)
        return out

    def try_repair(
        self, candidate: CandidateProvider, response: ProviderResponse
    ) -> bool:
        key = ModelTurnRepair._key(candidate)
        attempted = self._attempts.get(key)
        if attempted is None or attempted.mode == "omit" or self._format is None:
            return False
        rejection = _format_rejection(response)
        if rejection is None:
            return False

        if (
            attempted.mode == "json_schema"
            and not self._format.strict
            and attempted.protocol in ("openai", "openai_responses")
            and "strict" in rejection
        ):
            next_mode = "strict_schema"
        elif (
            attempted.mode in ("json_schema", "strict_schema")
            and attempted.protocol != "anthropic"
        ):
            # An object-only mode cannot fulfill an array or scalar schema.
            schema_type = (self._format.schema or {}).get("type")
            schema_types = (
                [schema_type] if isinstance(schema_type, str) else schema_type
            )
            next_mode = (
                "omit"
                if isinstance(schema_types, list) and "object" not in schema_types
                else "json_object"
            )
        else:
            next_mode = "omit"
        self._next_modes[key] = next_mode
        logger.info(
            "Response format recovery: provider_id=%s model=%s %s -> %s",
            candidate.provider_id,
            candidate.target_model,
            attempted.mode,
            next_mode,
        )
        return True

    def validate_response(
        self, candidate: CandidateProvider, response: ProviderResponse
    ) -> ProviderResponse:
        attempt = self._attempts.get(ModelTurnRepair._key(candidate))
        requested = self._format
        if (
            not response.is_success
            or attempt is None
            or not attempt.validate_output
            or requested is None
        ):
            return response
        try:
            reply = convert_response_for_user(
                request_protocol=self._request_protocol,
                supplier_protocol=attempt.protocol,
                body=_json_object(response.body),
                target_model=candidate.target_model,
            )
            if self._request_protocol == "openai_responses":
                if any(
                    item.get("type") == "function_call"
                    for item in reply.get("output", [])
                ):
                    return response
                valid = requested.accepts(_extract_assistant_text_from_responses(reply))
            else:
                choices = reply.get("choices") or []
                valid = bool(choices) and all(
                    choice.get("finish_reason")
                    in ("tool_calls", "function_call", "content_filter")
                    or choice["message"].get("refusal")
                    or requested.accepts(choice["message"]["content"])
                    for choice in choices
                )
            if valid:
                return response
        except (KeyError, TypeError, ValueError, ServiceError):
            pass
        return _invalid_output(response)

    async def validate_stream(
        self,
        candidate: CandidateProvider,
        stream: AsyncGenerator[tuple[bytes, ProviderResponse], None],
    ) -> AsyncGenerator[tuple[bytes, ProviderResponse], None]:
        attempt = self._attempts.get(ModelTurnRepair._key(candidate))
        requested = self._format
        if attempt is None or not attempt.validate_output or requested is None:
            async for item in stream:
                yield item
            return

        decoder = SSEDecoder()
        chunks: list[bytes] = []
        size = 0
        text: dict[int, list[str]] = {}
        finish: dict[int, str] = {}
        completed = False
        response: ProviderResponse | None = None
        async for chunk, response in stream:
            if not response.is_success:
                yield chunk, response
                return
            size += len(chunk)
            if size > _MAX_BUFFERED_STREAM_BYTES:
                yield b"", _invalid_output(response)
                return
            chunks.append(chunk)
            for payload in decoder.feed(chunk):
                if payload.strip() == "[DONE]":
                    completed = True
                    continue
                event = _json_object(payload)
                event_type = event.get("type")
                if "error" in event or event_type in (
                    "error",
                    "response.failed",
                    "response.incomplete",
                ):
                    yield b"", _invalid_output(response)
                    return
                if event_type == "response.completed":
                    completed = True
                    if any(
                        item.get("type") == "function_call"
                        for item in event.get("response", {}).get("output", [])
                    ):
                        finish[0] = "tool_calls"
                elif event_type == "response.output_text.delta":
                    text.setdefault(0, []).append(event.get("delta") or "")
                for choice in event.get("choices", []):
                    index = choice.get("index", 0)
                    text.setdefault(index, []).append(
                        choice.get("delta", {}).get("content") or ""
                    )
                    if choice.get("finish_reason"):
                        finish[index] = choice["finish_reason"]

        if response is None:
            return
        indices = text.keys() | finish.keys()
        if (
            not completed
            or not indices
            or any(
                finish.get(index)
                not in ("tool_calls", "function_call", "content_filter")
                and not requested.accepts("".join(text.get(index, [])))
                for index in indices
            )
        ):
            yield b"", _invalid_output(response)
            return
        for chunk in chunks:
            yield chunk, response
