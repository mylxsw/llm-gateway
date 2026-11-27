"""Bounded, request-local recovery for Chat tools/reasoning incompatibility."""

import copy
import logging
from typing import Any

from app.common.protocol_conversion import convert_request_for_supplier
from app.providers.base import ProviderResponse
from app.rules.models import CandidateProvider
from app.services.model_turn_repair import CandidateKey, ModelTurnRepair, _error_messages

logger = logging.getLogger(__name__)


def is_tool_reasoning_error(response: ProviderResponse) -> bool:
    if response.status_code != 400:
        return False
    for source in (response.body, response.error):
        for message in _error_messages(source):
            message = " ".join(message.casefold().replace("\\_", "_").split())
            if all(token in message for token in (
                "function tools", "reasoning_effort", "not supported",
                "/v1/chat/completions", "/v1/responses", "none",
            )):
                return True
    return False


class ToolReasoningRecovery:
    def __init__(self) -> None:
        self._stages: dict[CandidateKey, str] = {}
        self._originals: dict[CandidateKey, tuple[str, dict[str, Any]]] = {}

    def protocol(self, candidate: CandidateProvider, default: str) -> str:
        if self._stages.get(ModelTurnRepair._key(candidate)) == "responses":
            return "openai_responses"
        return default

    def prepare(
        self, candidate: CandidateProvider, path: str,
        body: dict[str, Any], protocol: str, *, no_suffix: bool = False,
    ) -> tuple[str, dict[str, Any], str]:
        key = ModelTurnRepair._key(candidate)
        stage = self._stages.get(key)
        if stage is None:
            tools = body.get("tools")
            if (protocol == "openai" and path == "/v1/chat/completions"
                    and isinstance(tools, list)
                    and any(isinstance(tool, dict) and tool.get("type") == "function" for tool in tools)):
                self._originals[key] = ("" if no_suffix else path, copy.deepcopy(body))
            return path, body, protocol
        original_path, original_body = self._originals[key]
        repaired = copy.deepcopy(original_body)
        if stage == "responses":
            path, repaired = convert_request_for_supplier(
                request_protocol="openai", supplier_protocol="openai_responses",
                path="/v1/chat/completions", body=repaired,
                target_model=candidate.target_model,
            )
            return path, repaired, "openai_responses"
        repaired["reasoning_effort"] = "none"
        return original_path, repaired, "openai"

    def try_repair(self, candidate: CandidateProvider, response: ProviderResponse) -> bool:
        key = ModelTurnRepair._key(candidate)
        if response.is_success or key not in self._originals:
            return False
        stage = self._stages.get(key)
        if stage == "responses":
            next_stage = "none"
        elif stage is None and is_tool_reasoning_error(response):
            next_stage = "responses" if self._originals[key][0] else "none"
        else:
            return False
        self._stages[key] = next_stage
        logger.info("Tool/reasoning recovery: provider_id=%s model=%s stage=%s",
                    candidate.provider_id, candidate.target_model, next_stage)
        return True

    def repair(self, model_turn_repair: ModelTurnRepair):
        def callback(candidate: CandidateProvider, response: ProviderResponse) -> bool:
            if self.try_repair(candidate, response):
                return True
            # Never apply a different repair to a Responses body or restart this chain.
            if ModelTurnRepair._key(candidate) in self._stages:
                return False
            return model_turn_repair.try_repair(candidate, response)
        return callback
