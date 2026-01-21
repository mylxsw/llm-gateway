"""Proxy Core Service Module

Implements core business logic for request proxying."""

import json
import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Optional, AsyncGenerator

import anyio

from app.common.errors import NotFoundError, ServiceError
from app.common.sanitizer import sanitize_headers
from app.common.stream_usage import StreamUsageAccumulator
from app.common.protocol_conversion import (
    convert_request_for_supplier,
    convert_response_for_user,
    convert_stream_for_user,
    normalize_protocol,
)
from app.common.token_counter import get_token_counter
from app.common.costs import calculate_cost_from_billing, resolve_billing
from app.common.utils import generate_trace_id
from app.common.time import utc_now
from app.common.usage_extractor import extract_output_tokens
from app.common.proxy import build_proxy_config
from app.domain.log import RequestLogCreate
from app.domain.model import ModelMapping, ModelMappingProviderResponse
from app.domain.provider import Provider
from app.providers import get_provider_client, ProviderResponse
from app.repositories.model_repo import ModelRepository
from app.repositories.provider_repo import ProviderRepository
from app.repositories.log_repo import LogRepository
from app.rules import RuleEngine, RuleContext, TokenUsage, CandidateProvider
from app.services.retry_handler import RetryHandler, AttemptRecord
from app.services.strategy import RoundRobinStrategy, CostFirstStrategy, SelectionStrategy

logger = logging.getLogger(__name__)

MAX_LOG_TEXT_LENGTH = 10000


def _truncate_log_text(text: str) -> str:
    if len(text) <= MAX_LOG_TEXT_LENGTH:
        return text
    return f"{text[:MAX_LOG_TEXT_LENGTH]}...[truncated]"


def _smart_truncate(data: Any, max_list: int = 20, max_str: int = 1000) -> Any:
    """
    Recursively truncate data structures for logging.
    """
    if isinstance(data, dict):
        return {k: _smart_truncate(v, max_list, max_str) for k, v in data.items()}
    
    if isinstance(data, list):
        if len(data) > max_list:
            # Check if it's a list of numbers (likely embedding vector)
            if data and isinstance(data[0], (int, float)):
                 return data[:5] + [f"...({len(data)-5} items)..."]
            
            truncated = [_smart_truncate(x, max_list, max_str) for x in data[:max_list]]
            truncated.append(f"...({len(data)-max_list} more items)...")
            return truncated
        return [_smart_truncate(x, max_list, max_str) for x in data]
    
    if isinstance(data, str) and len(data) > max_str:
        return data[:max_str] + "...[truncated]"
    
    return data


class ProxyService:
    """
    Proxy Core Service
    
    Handles the complete flow of proxy requests:
    1. Parse request, extract requested_model
    2. Calculate input Token
    3. Rule engine match, get candidate providers
    4. Round-robin strategy selects provider
    5. Replace model field, forward request
    6. Handle retry and failover
    7. Calculate output Token
    8. Record log
    9. Return response
    """
    
    def __init__(
        self,
        model_repo: ModelRepository,
        provider_repo: ProviderRepository,
        log_repo: LogRepository,
    ):
        """
        Initialize Service

        Args:
            model_repo: Model Repository
            provider_repo: Provider Repository
            log_repo: Log Repository
        """
        self.model_repo = model_repo
        self.provider_repo = provider_repo
        self.log_repo = log_repo
        self.rule_engine = RuleEngine()
        # Strategy selection instances (reused for performance)
        self._round_robin_strategy = RoundRobinStrategy()
        self._cost_first_strategy = CostFirstStrategy()

    def _get_strategy(self, strategy_name: str) -> SelectionStrategy:
        """
        Get strategy instance based on strategy name

        Args:
            strategy_name: Strategy name ("round_robin" or "cost_first")

        Returns:
            SelectionStrategy: Strategy instance
        """
        if strategy_name == "cost_first":
            return self._cost_first_strategy
        else:
            # Default to round_robin for unknown strategies
            return self._round_robin_strategy

    @staticmethod
    def _serialize_response_body(body: Any) -> str | None:
        if body is None:
            return None
            
        data = body
        if isinstance(body, (bytes, bytearray)):
            if b"\x00" in body:
                return f"[binary data: {len(body)} bytes]"
            try:
                decoded = body.decode("utf-8")
                # Try to parse as JSON first
                try:
                    data = json.loads(decoded)
                except json.JSONDecodeError:
                    return _truncate_log_text(decoded)
            except UnicodeDecodeError:
                return f"[binary data: {len(body)} bytes]"

        # If it's already a dict/list or successfully parsed
        if isinstance(data, (dict, list)):
            try:
                truncated_data = _smart_truncate(data)
                return json.dumps(truncated_data, ensure_ascii=False)
            except Exception:
                # Fallback
                return _truncate_log_text(str(data))
        
        return _truncate_log_text(str(data))

    @staticmethod
    def _sanitize_request_body_for_log(body: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(body, dict) or "_files" not in body:
            return body

        safe_files = []
        for item in body.get("_files", []):
            if not isinstance(item, dict):
                continue
            data = item.get("data")
            safe_files.append(
                {
                    "field": item.get("field"),
                    "filename": item.get("filename"),
                    "content_type": item.get("content_type"),
                    "size": len(data) if isinstance(data, (bytes, bytearray)) else None,
                }
            )
        sanitized = dict(body)
        sanitized["_files"] = safe_files
        return sanitized

    async def _resolve_candidates(
        self,
        requested_model: str,
        request_protocol: str,
        headers: dict[str, str],
        body: dict[str, Any],
    ) -> tuple[ModelMapping, list[CandidateProvider], int, str, dict[int, ModelMappingProviderResponse]]:
        """
        Resolve model and provider candidate list

        Returns:
            tuple: (model_mapping, candidates, input_tokens, protocol, provider_mapping_by_id)
        """
        request_protocol = (request_protocol or "openai").lower()
        model_mapping = await self.model_repo.get_mapping(requested_model)
        if not model_mapping:
            raise NotFoundError(
                message=f"Model '{requested_model}' is not configured",
                code="model_not_found",
            )

        if not model_mapping.is_active:
            raise ServiceError(
                message=f"Model '{requested_model}' is disabled",
                code="model_disabled",
            )

        provider_mappings = await self.model_repo.get_provider_mappings(
            requested_model=requested_model,
            is_active=True,
        )

        if not provider_mappings:
            raise ServiceError(
                message=f"No providers configured for model '{requested_model}'",
                code="no_available_provider",
            )

        provider_ids = [pm.provider_id for pm in provider_mappings]
        providers: dict[int, Provider] = {}
        for pid in provider_ids:
            provider = await self.provider_repo.get_by_id(pid)
            if provider:
                providers[pid] = provider

        eligible_provider_mappings = [
            pm for pm in provider_mappings if providers.get(pm.provider_id) is not None
        ]
        eligible_providers = {pid: p for pid, p in providers.items()}

        if not eligible_provider_mappings:
            raise ServiceError(message="No available providers", code="no_available_provider")

        provider_mapping_by_id = {pm.provider_id: pm for pm in eligible_provider_mappings}

        token_counter = get_token_counter(request_protocol)
        if "input" in body:
            input_tokens = token_counter.count_input(body["input"], requested_model)
        else:
            messages = body.get("messages", [])
            input_tokens = token_counter.count_messages(messages, requested_model)

        context = RuleContext(
            current_model=requested_model,
            headers=headers,
            request_body=body,
            token_usage=TokenUsage(input_tokens=input_tokens),
        )

        candidates = await self.rule_engine.evaluate(
            context=context,
            model_mapping=model_mapping,
            provider_mappings=eligible_provider_mappings,
            providers=eligible_providers,
        )

        if not candidates:
            raise ServiceError(
                message="No providers matched the rules",
                code="no_available_provider",
            )

        return model_mapping, candidates, input_tokens, request_protocol, provider_mapping_by_id
    
    async def process_request(
        self,
        api_key_id: int,
        api_key_name: str,
        request_protocol: str,
        path: str,
        method: str,
        headers: dict[str, str],
        body: dict[str, Any],
        *,
        force_parse_response: bool = False,
    ) -> tuple[ProviderResponse, dict[str, Any]]:
        """
        Process Proxy Request
        
        Args:
            api_key_id: API Key ID
            api_key_name: API Key Name
            path: Request path
            method: HTTP method
            headers: Request headers
            body: Request body
        
        Returns:
            tuple[ProviderResponse, dict]: (Provider response, Log info)
        
        Raises:
            NotFoundError: Model not configured
            ServiceError: No available provider
        """
        trace_id = generate_trace_id()
        request_time = utc_now()
        sanitized_body = self._sanitize_request_body_for_log(body)
        
        # 1. Extract requested_model
        requested_model = body.get("model")
        if not requested_model:
            raise ServiceError(
                message="Model is required in request body",
                code="missing_model",
            )
        
        # 2. Get model mapping
        model_mapping, candidates, input_tokens, protocol, provider_mapping_by_id = await self._resolve_candidates(
            requested_model=requested_model,
            request_protocol=request_protocol,
            headers=headers,
            body=body,
        )

        # DEBUG: Log matched providers
        candidates_info = [
            {
                "id": c.provider_id,
                "name": c.provider_name,
                "priority": c.priority,
                "weight": c.weight
            }
            for c in candidates
        ]
        logger.debug(f"Matched Providers: {json.dumps(candidates_info, ensure_ascii=False)}")

        # Select strategy based on model configuration
        strategy = self._get_strategy(model_mapping.strategy)
        retry_handler = RetryHandler(strategy)

        failed_attempt_logged = False

        async def log_failed_attempt(attempt: AttemptRecord) -> None:
            nonlocal failed_attempt_logged
            provider_mapping = provider_mapping_by_id.get(attempt.provider.provider_id)
            billing = resolve_billing(
                input_tokens=input_tokens,
                model_input_price=model_mapping.input_price,
                model_output_price=model_mapping.output_price,
                provider_billing_mode=provider_mapping.billing_mode if provider_mapping else None,
                provider_per_request_price=provider_mapping.per_request_price if provider_mapping else None,
                provider_tiered_pricing=provider_mapping.tiered_pricing if provider_mapping else None,
                provider_input_price=provider_mapping.input_price if provider_mapping else None,
                provider_output_price=provider_mapping.output_price if provider_mapping else None,
            )
            attempt_log = RequestLogCreate(
                request_time=attempt.request_time,
                api_key_id=api_key_id,
                api_key_name=api_key_name,
                requested_model=requested_model,
                target_model=attempt.provider.target_model,
                provider_id=attempt.provider.provider_id,
                provider_name=attempt.provider.provider_name,
                retry_count=attempt.attempt_index + 1,
                matched_provider_count=len(candidates),
                first_byte_delay_ms=attempt.response.first_byte_delay_ms,
                total_time_ms=attempt.response.total_time_ms,
                input_tokens=input_tokens,
                output_tokens=None,
                total_cost=None,
                input_cost=None,
                output_cost=None,
                price_source=billing.price_source,
                request_headers=sanitize_headers(headers),
                request_body=sanitized_body,
                response_status=attempt.response.status_code,
                response_body=self._serialize_response_body(attempt.response.body),
                error_info=attempt.response.error,
                trace_id=trace_id,
                is_stream=False,
            )
            try:
                await self.log_repo.create(attempt_log)
                failed_attempt_logged = True
            except Exception:
                logger.exception(
                    "Failed to write attempt log: trace_id=%s provider_id=%s attempt_index=%s",
                    trace_id,
                    attempt.provider.provider_id,
                    attempt.attempt_index,
                )

        # 8. Execute request (with retry)
        async def forward_fn(candidate: CandidateProvider) -> ProviderResponse:
            try:
                client = get_provider_client(candidate.protocol)
                supplier_path, supplier_body = convert_request_for_supplier(
                    request_protocol=request_protocol,
                    supplier_protocol=candidate.protocol,
                    path=path,
                    body=body,
                    target_model=candidate.target_model,
                )
                same_protocol = normalize_protocol(request_protocol) == normalize_protocol(candidate.protocol)
                proxy_config = build_proxy_config(
                    candidate.proxy_enabled,
                    candidate.proxy_url,
                )
                return await client.forward(
                    base_url=candidate.base_url,
                    api_key=candidate.api_key,
                    path=supplier_path,
                    method=method,
                    headers=headers,
                    body=supplier_body,
                    target_model=candidate.target_model,
                    response_mode="parsed" if force_parse_response else ("raw" if same_protocol else "parsed"),
                    extra_headers=candidate.extra_headers,
                    proxy_config=proxy_config,
                )
            except Exception as e:
                error_msg = str(e)
                logger.error(
                    "Error during request forwarding: provider_id=%s, provider_name=%s, "
                    "request_protocol=%s, supplier_protocol=%s, error=%s",
                    candidate.provider_id,
                    candidate.provider_name,
                    request_protocol,
                    candidate.protocol,
                    error_msg,
                )
                return ProviderResponse(status_code=400, error=error_msg)

        result = await retry_handler.execute_with_retry(
            candidates=candidates,
            requested_model=requested_model,
            forward_fn=forward_fn,
            input_tokens=input_tokens,
            on_failure_attempt=log_failed_attempt,
        )

        if result.response.body is not None and result.final_provider is not None:
            try:
                same_protocol = normalize_protocol(request_protocol) == normalize_protocol(result.final_provider.protocol)
                if not same_protocol:
                    result.response.body = convert_response_for_user(
                        request_protocol=request_protocol,
                        supplier_protocol=result.final_provider.protocol,
                        body=result.response.body,
                        target_model=result.final_provider.target_model,
                    )
            except Exception as e:
                error_msg = str(e)
                logger.error(
                    "Error during response conversion: provider_id=%s, provider_name=%s, "
                    "request_protocol=%s, supplier_protocol=%s, error=%s",
                    result.final_provider.provider_id,
                    result.final_provider.provider_name,
                    request_protocol,
                    result.final_provider.protocol,
                    error_msg,
                )
                result.response = ProviderResponse(
                    status_code=502,
                    headers=result.response.headers,
                    error=error_msg,
                    first_byte_delay_ms=result.response.first_byte_delay_ms,
                    total_time_ms=result.response.total_time_ms,
                )
        
        # 9. Calculate Output Token
        output_tokens = 0
        if result.success and result.response.body:
            try:
                extracted = extract_output_tokens(result.response.body)
                if extracted is not None:
                    output_tokens = extracted
            except Exception:
                pass
        
        # 10. Record log
        final_provider_id = result.final_provider.provider_id if result.final_provider else None
        provider_mapping = (
            provider_mapping_by_id.get(final_provider_id) if final_provider_id is not None else None
        )
        billing = resolve_billing(
            input_tokens=input_tokens,
            model_input_price=model_mapping.input_price,
            model_output_price=model_mapping.output_price,
            provider_billing_mode=provider_mapping.billing_mode if provider_mapping else None,
            provider_per_request_price=provider_mapping.per_request_price if provider_mapping else None,
            provider_tiered_pricing=provider_mapping.tiered_pricing if provider_mapping else None,
            provider_input_price=provider_mapping.input_price if provider_mapping else None,
            provider_output_price=provider_mapping.output_price if provider_mapping else None,
        )
        cost = calculate_cost_from_billing(
            billing=billing,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        log_data = RequestLogCreate(
            request_time=request_time,
            api_key_id=api_key_id,
            api_key_name=api_key_name,
            requested_model=requested_model,
            target_model=result.final_provider.target_model if result.final_provider else None,
            provider_id=result.final_provider.provider_id if result.final_provider else None,
            provider_name=result.final_provider.provider_name if result.final_provider else None,
            retry_count=result.retry_count,
            matched_provider_count=len(candidates),
            first_byte_delay_ms=result.response.first_byte_delay_ms,
            total_time_ms=result.response.total_time_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_cost=cost.total_cost,
            input_cost=cost.input_cost,
            output_cost=cost.output_cost,
            price_source=billing.price_source,
            request_headers=sanitize_headers(headers),
            request_body=sanitized_body,

            response_status=result.response.status_code,
            response_body=self._serialize_response_body(result.response.body),
            error_info=result.response.error,
            trace_id=trace_id,
            is_stream=False,
        )
        
        # DEBUG: Log request details
        try:
            logger.debug(f"Request Log: {log_data.model_dump_json()}")
        except AttributeError:
            # Fallback for Pydantic v1
            logger.debug(f"Request Log: {log_data.json()}")

        if result.success or not failed_attempt_logged:
            await self.log_repo.create(log_data)
        
        return result.response, {
            "trace_id": trace_id,
            "retry_count": result.retry_count,
            "target_model": result.final_provider.target_model if result.final_provider else None,
            "provider_name": result.final_provider.provider_name if result.final_provider else None,
        }

    async def process_request_stream(
        self,
        api_key_id: int,
        api_key_name: str,
        request_protocol: str,
        path: str,
        method: str,
        headers: dict[str, str],
        body: dict[str, Any],
    ) -> tuple[ProviderResponse, AsyncGenerator[bytes, None], dict[str, Any]]:
        """
        Process Streaming Proxy Request
        
        Args:
            api_key_id: API Key ID
            api_key_name: API Key Name
            path: Request path
            method: HTTP method
            headers: Request headers
            body: Request body
        
        Returns:
            tuple: (Initial response, Stream generator, Log info)
        """
        trace_id = generate_trace_id()
        request_time = utc_now()
        start_monotonic = time.monotonic()
        sanitized_body = self._sanitize_request_body_for_log(body)
        
        # 1-7. Same model resolution and rule matching logic
        requested_model = body.get("model")
        if not requested_model:
            raise ServiceError(message="Model is required", code="missing_model")

        model_mapping, candidates, input_tokens, protocol, provider_mapping_by_id = await self._resolve_candidates(
            requested_model=requested_model,
            request_protocol=request_protocol,
            headers=headers,
            body=body,
        )

        # DEBUG: Log matched providers
        candidates_info = [
            {
                "id": c.provider_id,
                "name": c.provider_name,
                "priority": c.priority,
                "weight": c.weight
            }
            for c in candidates
        ]
        logger.debug(f"Matched Providers: {json.dumps(candidates_info, ensure_ascii=False)}")

        # Select strategy based on model configuration
        strategy = self._get_strategy(model_mapping.strategy)
        retry_handler = RetryHandler(strategy)

        # 8. Execute streaming request
        def forward_stream_fn(candidate: CandidateProvider):
            async def error_gen(msg: str):
                yield b"", ProviderResponse(status_code=400, error=msg)

            try:
                client = get_provider_client(candidate.protocol)
                supplier_path, supplier_body = convert_request_for_supplier(
                    request_protocol=request_protocol,
                    supplier_protocol=candidate.protocol,
                    path=path,
                    body=body,
                    target_model=candidate.target_model,
                )
            except Exception as e:
                error_msg = str(e)
                logger.error(
                    "Error during stream request conversion: provider_id=%s, provider_name=%s, "
                    "request_protocol=%s, supplier_protocol=%s, error=%s",
                    candidate.provider_id,
                    candidate.provider_name,
                    request_protocol,
                    candidate.protocol,
                    error_msg,
                )
                return error_gen(error_msg)

            proxy_config = build_proxy_config(
                candidate.proxy_enabled,
                candidate.proxy_url,
            )
            upstream_gen = client.forward_stream(
                base_url=candidate.base_url,
                api_key=candidate.api_key,
                path=supplier_path,
                method=method,
                headers=headers,
                body=supplier_body,
                target_model=candidate.target_model,
                extra_headers=candidate.extra_headers,
                proxy_config=proxy_config,
            )

            async def wrapped() -> AsyncGenerator[tuple[bytes, ProviderResponse], None]:
                try:
                    first_chunk, first_resp = await anext(upstream_gen)
                except StopAsyncIteration:
                    return

                if not first_resp.is_success:
                    yield first_chunk, first_resp
                    async for chunk, resp in upstream_gen:
                        yield chunk, resp
                    return

                async def upstream_bytes() -> AsyncGenerator[bytes, None]:
                    yield first_chunk
                    async for chunk, _ in upstream_gen:
                        yield chunk

                try:
                    same_protocol = normalize_protocol(request_protocol) == normalize_protocol(candidate.protocol)
                    if same_protocol:
                        async for chunk in upstream_bytes():
                            yield chunk, first_resp
                    else:
                        async for out_chunk in convert_stream_for_user(
                            request_protocol=request_protocol,
                            supplier_protocol=candidate.protocol,
                            upstream=upstream_bytes(),
                            model=candidate.target_model,
                        ):
                            yield out_chunk, first_resp
                except Exception as e:
                    err = str(e)
                    logger.error(
                        "Error during stream response conversion: provider_id=%s, provider_name=%s, "
                        "request_protocol=%s, supplier_protocol=%s, error=%s",
                        candidate.provider_id,
                        candidate.provider_name,
                        request_protocol,
                        candidate.protocol,
                        err,
                    )
                    if (request_protocol or "openai").lower() == "anthropic":
                        yield (
                            f"data: {json.dumps({'type': 'error', 'error': {'message': err}}, ensure_ascii=False)}\n\n".encode(
                                "utf-8"
                            ),
                            first_resp,
                        )
                        yield (
                            f"data: {json.dumps({'type': 'message_stop'}, ensure_ascii=False)}\n\n".encode(
                                "utf-8"
                            ),
                            first_resp,
                        )
                    else:
                        yield (
                            f"data: {json.dumps({'error': {'message': err}}, ensure_ascii=False)}\n\n".encode(
                                "utf-8"
                            ),
                            first_resp,
                        )
                        yield (b"data: [DONE]\n\n", first_resp)
                    return

            return wrapped()
            
        async def log_failed_attempt(attempt: AttemptRecord) -> None:
            provider_mapping = provider_mapping_by_id.get(attempt.provider.provider_id)
            billing = resolve_billing(
                input_tokens=input_tokens,
                model_input_price=model_mapping.input_price,
                model_output_price=model_mapping.output_price,
                provider_billing_mode=provider_mapping.billing_mode if provider_mapping else None,
                provider_per_request_price=provider_mapping.per_request_price if provider_mapping else None,
                provider_tiered_pricing=provider_mapping.tiered_pricing if provider_mapping else None,
                provider_input_price=provider_mapping.input_price if provider_mapping else None,
                provider_output_price=provider_mapping.output_price if provider_mapping else None,
            )
            attempt_log = RequestLogCreate(
                request_time=attempt.request_time,
                api_key_id=api_key_id,
                api_key_name=api_key_name,
                requested_model=requested_model,
                target_model=attempt.provider.target_model,
                provider_id=attempt.provider.provider_id,
                provider_name=attempt.provider.provider_name,
                retry_count=attempt.attempt_index + 1,
                matched_provider_count=len(candidates),
                first_byte_delay_ms=attempt.response.first_byte_delay_ms,
                total_time_ms=attempt.response.total_time_ms,
                input_tokens=input_tokens,
                output_tokens=None,
                total_cost=None,
                input_cost=None,
                output_cost=None,
                price_source=billing.price_source,
                request_headers=sanitize_headers(headers),
                request_body=sanitized_body,
                response_status=attempt.response.status_code,
                response_body=self._serialize_response_body(attempt.response.body),
                error_info=attempt.response.error,
                trace_id=trace_id,
                is_stream=True,
            )
            try:
                with anyio.CancelScope(shield=True):
                    await self.log_repo.create(attempt_log)
            except Exception:
                pass

        stream_gen = retry_handler.execute_with_retry_stream(
            candidates,
            requested_model,
            forward_stream_fn,
            input_tokens=input_tokens,
            on_failure_attempt=log_failed_attempt,
        )
        
        # Get first chunk to determine status
        try:
            first_chunk, initial_response, final_provider, retry_count = await anext(stream_gen)
        except StopAsyncIteration:
            raise ServiceError(message="Stream ended unexpectedly", code="stream_error")
        except Exception as e:
            raise ServiceError(message=f"Stream connection error: {str(e)}", code="stream_error")

        # Wrap generator to handle logging
        async def wrapped_generator():
            usage_acc = StreamUsageAccumulator(
                protocol=protocol,
                model=requested_model,
            )
            raw_stream_chunks: list[bytes] = []
            stream_error: Optional[str] = None

            def record_stream_chunk(chunk: Any) -> None:
                if not chunk:
                    return
                if isinstance(chunk, (bytes, bytearray)):
                    raw_stream_chunks.append(bytes(chunk))
                    return
                raw_stream_chunks.append(str(chunk).encode("utf-8"))

            try:
                usage_acc.feed(first_chunk)
                record_stream_chunk(first_chunk)
                yield first_chunk
                async for chunk, _, _, _ in stream_gen:
                    usage_acc.feed(chunk)
                    record_stream_chunk(chunk)
                    yield chunk
            except asyncio.CancelledError:
                stream_error = "client_disconnected"
                raise
            except Exception as e:
                # Log stream interruption exception, but do not throw upwards to avoid polluting StreamingResponse logs
                stream_error = str(e)
                return
            finally:
                usage_result = usage_acc.finalize()
                total_time_ms = initial_response.total_time_ms
                if total_time_ms is None:
                    total_time_ms = int((time.monotonic() - start_monotonic) * 1000)

                # 10. Record log (after stream ends)
                # Record the raw stream response (SSE) plus a reconstructed summary in one field.
                final_provider_id = final_provider.provider_id if final_provider else None
                provider_mapping = (
                    provider_mapping_by_id.get(final_provider_id) if final_provider_id is not None else None
                )
                billing = resolve_billing(
                    input_tokens=input_tokens,
                    model_input_price=model_mapping.input_price,
                    model_output_price=model_mapping.output_price,
                    provider_billing_mode=provider_mapping.billing_mode if provider_mapping else None,
                    provider_per_request_price=provider_mapping.per_request_price if provider_mapping else None,
                    provider_tiered_pricing=provider_mapping.tiered_pricing if provider_mapping else None,
                    provider_input_price=provider_mapping.input_price if provider_mapping else None,
                    provider_output_price=provider_mapping.output_price if provider_mapping else None,
                )
                cost = calculate_cost_from_billing(
                    billing=billing,
                    input_tokens=input_tokens,
                    output_tokens=usage_result.output_tokens,
                )
                raw_stream_text = (
                    b"".join(raw_stream_chunks).decode("utf-8", errors="replace")
                    if raw_stream_chunks
                    else ""
                )
                reconstructed_body = json.dumps(
                    {
                        "type": "stream_reconstruction",
                        "protocol": protocol,
                        "output_text": usage_result.output_text,
                        "upstream_reported_output_tokens": usage_result.upstream_reported_output_tokens,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                combined_body = (
                    "Original:\n---\n"
                    + raw_stream_text
                    + "\n---\n\nFinal Response (After reconstruction):\n---\n"
                    + reconstructed_body
                    + "\n---"
                )
                log_data = RequestLogCreate(
                    request_time=request_time,
                    api_key_id=api_key_id,
                    api_key_name=api_key_name,
                    requested_model=requested_model,
                    target_model=final_provider.target_model if final_provider else None,
                    provider_id=final_provider.provider_id if final_provider else None,
                    provider_name=final_provider.provider_name if final_provider else None,
                    retry_count=retry_count,
                    matched_provider_count=len(candidates),
                    first_byte_delay_ms=initial_response.first_byte_delay_ms,
                    total_time_ms=total_time_ms,
                    input_tokens=input_tokens,
                    output_tokens=usage_result.output_tokens,
                    total_cost=cost.total_cost,
                    input_cost=cost.input_cost,
                    output_cost=cost.output_cost,
                    price_source=billing.price_source,
                    request_headers=sanitize_headers(headers),
                    request_body=sanitized_body,
                    response_body=combined_body if raw_stream_text or reconstructed_body else None,
                    response_status=initial_response.status_code,
                    error_info=initial_response.error or stream_error,
                    trace_id=trace_id,
                    is_stream=True,
                )
                
                # DEBUG: Log request details
                try:
                    logger.debug(f"Request Log: {log_data.model_dump_json()}")
                except AttributeError:
                    # Fallback for Pydantic v1
                    logger.debug(f"Request Log: {log_data.json()}")

                # client disconnect triggers cancellation, use shield to ensure logs are written to DB
                try:
                    with anyio.CancelScope(shield=True):
                        await self.log_repo.create(log_data)
                except Exception:
                    # Log writing failure does not affect main flow
                    pass

        return initial_response, wrapped_generator(), {
            "trace_id": trace_id,
            "retry_count": retry_count,
            "target_model": final_provider.target_model if final_provider else None,
            "provider_name": final_provider.provider_name if final_provider else None,
        }
