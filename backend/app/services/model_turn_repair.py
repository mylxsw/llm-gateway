"""Request-scoped recovery for upstreams that reject a trailing model turn."""

import copy
import json
from typing import Any, Iterator

from app.providers.base import ProviderResponse
from app.rules.models import CandidateProvider

CandidateKey = tuple[int | None, int, str, str]


def _error_messages(value: Any, depth: int = 0) -> Iterator[str]:
    """Read current error fields only, never request echoes or previous_errors."""
    if depth > 8:
        return
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except (ValueError, RecursionError):
            yield value
        else:
            yield from _error_messages(decoded, depth + 1)
    elif isinstance(value, dict):
        for key in ("error", "message"):
            if key in value:
                yield from _error_messages(value[key], depth + 1)
        metadata = value.get("metadata")
        if isinstance(metadata, dict) and "raw" in metadata:
            yield from _error_messages(metadata["raw"], depth + 1)


def is_model_turn_error(response: ProviderResponse) -> bool:
    if response.status_code != 400:
        return False
    for source in (response.body, response.error):
        for message in _error_messages(source):
            normalized = " ".join(message.casefold().split())
            if "model turn" in normalized and "ending with" in normalized:
                return True
    return False


def append_user_turn(body: dict[str, Any]) -> dict[str, Any] | None:
    """Copy a supported conversation without bypassing pending tool results."""
    native = "contents" in body
    field = "contents" if native else "messages"
    messages = body.get(field)
    if not isinstance(messages, list) or not messages:
        return None
    if any(not isinstance(message, dict) for message in messages):
        return None
    if messages[-1].get("role") != ("model" if native else "assistant"):
        return None

    pending: list[Any] = []
    for message in messages:
        # OpenAI tool calls (including the legacy function-call format).
        calls = message.get("tool_calls") or []
        if not isinstance(calls, list):
            return None
        for call in calls:
            if not isinstance(call, dict) or not call.get("id"):
                return None
            pending.append(call["id"])
        if message.get("function_call"):
            call = message["function_call"]
            if not isinstance(call, dict) or not call.get("name"):
                return None
            pending.append(call["name"])
        result_id = message.get("tool_call_id")
        if message.get("role") == "function":
            result_id = message.get("name")
        if result_id in pending:
            pending.remove(result_id)

        # Gemini parts and Anthropic content blocks use different tool shapes.
        parts = message.get("parts" if native else "content")
        if not isinstance(parts, list):
            continue
        for part in parts:
            if not isinstance(part, dict):
                return None
            if "functionCall" in part:
                call = part["functionCall"]
                if not isinstance(call, dict) or not call.get("name"):
                    return None
                pending.append(call["name"])
            if part.get("type") == "tool_use":
                if not part.get("id"):
                    return None
                pending.append(part["id"])
            result = part.get("functionResponse")
            result_id = result.get("name") if isinstance(result, dict) else None
            if part.get("type") == "tool_result":
                result_id = part.get("tool_use_id")
            if result_id in pending:
                pending.remove(result_id)
    if pending:
        return None

    repaired = copy.deepcopy(body)
    continuation = {"text": "Please continue."}
    repaired[field].append(
        {"role": "user", "parts": [continuation]}
        if native
        else {"role": "user", "content": continuation["text"]}
    )
    return repaired


class ModelTurnRepair:
    """Keep repaired supplier bodies local to one request and candidate."""

    def __init__(self) -> None:
        self._bodies: dict[CandidateKey, dict[str, Any]] = {}
        self._repaired: set[CandidateKey] = set()

    @staticmethod
    def _key(candidate: CandidateProvider) -> CandidateKey:
        return (
            candidate.provider_mapping_id,
            candidate.provider_id,
            candidate.target_model,
            candidate.protocol,
        )

    def prepare(
        self, candidate: CandidateProvider, body: dict[str, Any]
    ) -> dict[str, Any]:
        key = self._key(candidate)
        if key not in self._repaired:
            self._bodies[key] = body
        return self._bodies[key]

    def try_repair(
        self, candidate: CandidateProvider, response: ProviderResponse
    ) -> bool:
        key = self._key(candidate)
        if key in self._repaired or not is_model_turn_error(response):
            return False
        repaired = append_user_turn(self._bodies.get(key, {}))
        if repaired is None:
            return False
        self._bodies[key] = repaired
        self._repaired.add(key)
        return True
