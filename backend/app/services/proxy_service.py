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
from app.common.costs import calculate_cost, resolve_price
from app.common.utils import generate_trace_id
from app.common.time import utc_now
from app.domain.log import RequestLogCreate
from app.domain.model import ModelMapping, ModelMappingProviderResponse
from app.domain.provider import Provider
from app.providers import get_provider_client, ProviderResponse
from app.repositories.model_repo import ModelRepository
from app.repositories.provider_repo import ProviderRepository
from app.repositories.log_repo import LogRepository
from app.rules import RuleEngine, RuleContext, TokenUsage, CandidateProvider
from app.services.retry_handler import RetryHandler
from app.services.strategy import RoundRobinStrategy, SelectionStrategy

logger = logging.getLogger(__name__)


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
        strategy: Optional[SelectionStrategy] = None,
    ):
        """
        Initialize Service
        
        Args:
            model_repo: Model Repository
            provider_repo: Provider Repository
            log_repo: Log Repository
            strategy: Provider Selection Strategy (Optional, defaults to RoundRobinStrategy)
        """
        self.model_repo = model_repo
        self.provider_repo = provider_repo
        self.log_repo = log_repo
        self.rule_engine = RuleEngine()
        self.strategy = strategy or RoundRobinStrategy()
        self.retry_handler = RetryHandler(self.strategy)

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

        result = await self.retry_handler.execute_with_retry(
            candidates=candidates,
            requested_model=requested_model,
            forward_fn=forward_fn,
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
                # OpenAI format
                if isinstance(result.response.body, dict):
                    usage = result.response.body.get("usage", {})
                    output_tokens = usage.get("completion_tokens", 0)
                    if not output_tokens:
                        # Anthropic format
                        output_tokens = usage.get("output_tokens", 0)
            except Exception:
                pass
        
        # 10. Record log
        final_provider_id = result.final_provider.provider_id if result.final_provider else None
        provider_mapping = (
            provider_mapping_by_id.get(final_provider_id) if final_provider_id is not None else None
        )
        resolved_price = resolve_price(
            model_input_price=model_mapping.input_price,
            model_output_price=model_mapping.output_price,
            provider_input_price=provider_mapping.input_price if provider_mapping else None,
            provider_output_price=provider_mapping.output_price if provider_mapping else None,
        )
        cost = calculate_cost(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            input_price=resolved_price.input_price,
            output_price=resolved_price.output_price,
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
            price_source=resolved_price.price_source,
            request_headers=sanitize_headers(headers),
            request_body=body,

            response_status=result.response.status_code,
            response_body=(
                json.dumps(result.response.body, ensure_ascii=False)
                if isinstance(result.response.body, (dict, list))
                else (
                    result.response.body.decode("utf-8", errors="ignore")
                    if isinstance(result.response.body, (bytes, bytearray))
                    else result.response.body
                )
            )
            if result.response.body is not None
            else None,
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

            upstream_gen = client.forward_stream(
                base_url=candidate.base_url,
                api_key=candidate.api_key,
                path=supplier_path,
                method=method,
                headers=headers,
                body=supplier_body,
                target_model=candidate.target_model,
                extra_headers=candidate.extra_headers,
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
            
        stream_gen = self.retry_handler.execute_with_retry_stream(
            candidates, requested_model, forward_stream_fn
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
            stream_error: Optional[str] = None
            try:
                usage_acc.feed(first_chunk)
                yield first_chunk
                async for chunk, _, _, _ in stream_gen:
                    usage_acc.feed(chunk)
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
                # Note: Streaming requests cannot stably obtain the full response body, here only record output preview (truncated)
                final_provider_id = final_provider.provider_id if final_provider else None
                provider_mapping = (
                    provider_mapping_by_id.get(final_provider_id) if final_provider_id is not None else None
                )
                resolved_price = resolve_price(
                    model_input_price=model_mapping.input_price,
                    model_output_price=model_mapping.output_price,
                    provider_input_price=provider_mapping.input_price if provider_mapping else None,
                    provider_output_price=provider_mapping.output_price if provider_mapping else None,
                )
                cost = calculate_cost(
                    input_tokens=input_tokens,
                    output_tokens=usage_result.output_tokens,
                    input_price=resolved_price.input_price,
                    output_price=resolved_price.output_price,
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
                    price_source=resolved_price.price_source,
                    request_headers=sanitize_headers(headers),
                    request_body=body,

                    response_status=initial_response.status_code,
                    response_body=json.dumps(
                        {
                            "type": "stream",
                            "protocol": protocol,
                            "output_preview": usage_result.output_preview,
                            "output_preview_truncated": usage_result.output_preview_truncated,
                            "upstream_reported_output_tokens": usage_result.upstream_reported_output_tokens,
                        },
                        ensure_ascii=False,
                    ),
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
