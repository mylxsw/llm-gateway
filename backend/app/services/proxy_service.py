"代理核心服务模块\n\n实现请求代理的核心业务逻辑。\n"

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
from app.common.utils import generate_trace_id
from app.domain.log import RequestLogCreate
from app.domain.model import ModelMapping
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
    代理核心服务
    
    处理代理请求的完整流程：
    1. 解析请求，提取 requested_model
    2. 计算输入 Token
    3. 规则引擎匹配，获取候选供应商
    4. 轮询策略选择供应商
    5. 替换 model 字段，转发请求
    6. 处理重试和故障切换
    7. 计算输出 Token
    8. 记录日志
    9. 返回响应
    """
    
    def __init__(
        self,
        model_repo: ModelRepository,
        provider_repo: ProviderRepository,
        log_repo: LogRepository,
        strategy: Optional[SelectionStrategy] = None,
    ):
        """
        初始化服务
        
        Args:
            model_repo: 模型 Repository
            provider_repo: 供应商 Repository
            log_repo: 日志 Repository
            strategy: 供应商选择策略 (可选，默认使用 RoundRobinStrategy)
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
    ) -> tuple[ModelMapping, list[CandidateProvider], int, str]:
        """
        解析模型与供应商候选列表

        Returns:
            tuple: (model_mapping, candidates, input_tokens, protocol)
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

        return model_mapping, candidates, input_tokens, request_protocol
    
    async def process_request(
        self,
        api_key_id: int,
        api_key_name: str,
        request_protocol: str,
        path: str,
        method: str,
        headers: dict[str, str],
        body: dict[str, Any],
    ) -> tuple[ProviderResponse, dict[str, Any]]:
        """
        处理代理请求
        
        Args:
            api_key_id: API Key ID
            api_key_name: API Key 名称
            path: 请求路径
            method: HTTP 方法
            headers: 请求头
            body: 请求体
        
        Returns:
            tuple[ProviderResponse, dict]: (供应商响应, 日志信息)
        
        Raises:
            NotFoundError: 模型未配置
            ServiceError: 无可用供应商
        """
        trace_id = generate_trace_id()
        request_time = datetime.utcnow()
        
        # 1. 提取 requested_model
        requested_model = body.get("model")
        if not requested_model:
            raise ServiceError(
                message="Model is required in request body",
                code="missing_model",
            )
        
        # 2. 获取模型映射
        model_mapping, candidates, input_tokens, protocol = await self._resolve_candidates(
            requested_model=requested_model,
            request_protocol=request_protocol,
            headers=headers,
            body=body,
        )

        # DEBUG: Print matched providers
        candidates_info = [
            {
                "id": c.provider_id,
                "name": c.provider_name,
                "priority": c.priority,
                "weight": c.weight
            }
            for c in candidates
        ]
        print(f"[DEBUG] Matched Providers: {json.dumps(candidates_info, ensure_ascii=False)}")
        
        # 8. 执行请求（带重试）
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
                    response_mode="raw" if same_protocol else "parsed",
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
                print(
                    f"[ERROR] Request Forwarding Error: provider_id={candidate.provider_id}, "
                    f"provider_name={candidate.provider_name}, request_protocol={request_protocol}, "
                    f"supplier_protocol={candidate.protocol}, error={error_msg}"
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
                print(
                    f"[ERROR] Response Conversion Error: provider_id={result.final_provider.provider_id}, "
                    f"provider_name={result.final_provider.provider_name}, request_protocol={request_protocol}, "
                    f"supplier_protocol={result.final_provider.protocol}, error={error_msg}"
                )
                result.response = ProviderResponse(
                    status_code=502,
                    headers=result.response.headers,
                    error=error_msg,
                    first_byte_delay_ms=result.response.first_byte_delay_ms,
                    total_time_ms=result.response.total_time_ms,
                )
        
        # 9. 计算输出 Token
        output_tokens = 0
        if result.success and result.response.body:
            try:
                # OpenAI 格式
                if isinstance(result.response.body, dict):
                    usage = result.response.body.get("usage", {})
                    output_tokens = usage.get("completion_tokens", 0)
                    if not output_tokens:
                        # Anthropic 格式
                        output_tokens = usage.get("output_tokens", 0)
            except Exception:
                pass
        
        # 10. 记录日志
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
        
        # DEBUG: Print log as JSON
        try:
            print(f"[DEBUG] Request Log: {log_data.model_dump_json()}")
        except AttributeError:
            # Fallback for Pydantic v1
            print(f"[DEBUG] Request Log: {log_data.json()}")

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
        处理流式代理请求
        
        Args:
            api_key_id: API Key ID
            api_key_name: API Key 名称
            path: 请求路径
            method: HTTP 方法
            headers: 请求头
            body: 请求体
        
        Returns:
            tuple: (初始响应, 流生成器, 日志信息)
        """
        trace_id = generate_trace_id()
        request_time = datetime.utcnow()
        start_monotonic = time.monotonic()
        
        # 1-7. 同样的模型解析和规则匹配逻辑
        requested_model = body.get("model")
        if not requested_model:
            raise ServiceError(message="Model is required", code="missing_model")

        model_mapping, candidates, input_tokens, protocol = await self._resolve_candidates(
            requested_model=requested_model,
            request_protocol=request_protocol,
            headers=headers,
            body=body,
        )

        # DEBUG: Print matched providers
        candidates_info = [
            {
                "id": c.provider_id,
                "name": c.provider_name,
                "priority": c.priority,
                "weight": c.weight
            }
            for c in candidates
        ]
        print(f"[DEBUG] Matched Providers: {json.dumps(candidates_info, ensure_ascii=False)}")
            
        # 8. 执行流式请求
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
                print(
                    f"[ERROR] Stream Request Conversion Error: provider_id={candidate.provider_id}, "
                    f"provider_name={candidate.provider_name}, request_protocol={request_protocol}, "
                    f"supplier_protocol={candidate.protocol}, error={error_msg}"
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
                    print(
                        f"[ERROR] Stream Response Conversion Error: provider_id={candidate.provider_id}, "
                        f"provider_name={candidate.provider_name}, request_protocol={request_protocol}, "
                        f"supplier_protocol={candidate.protocol}, error={err}"
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
        
        # 获取第一个块以确定状态
        try:
            first_chunk, initial_response, final_provider, retry_count = await anext(stream_gen)
        except StopAsyncIteration:
            raise ServiceError(message="Stream ended unexpectedly", code="stream_error")
        except Exception as e:
            raise ServiceError(message=f"Stream connection error: {str(e)}", code="stream_error")

        # 封装生成器以处理日志
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
                # 记录流中断异常，但不向上抛出，避免污染 StreamingResponse 日志
                stream_error = str(e)
                return
            finally:
                usage_result = usage_acc.finalize()
                total_time_ms = initial_response.total_time_ms
                if total_time_ms is None:
                    total_time_ms = int((time.monotonic() - start_monotonic) * 1000)

                # 10. 记录日志 (流结束后)
                # 注意：流式请求无法稳定获取完整响应体，这里仅记录输出预览（截断）
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
                
                # DEBUG: Print log as JSON
                try:
                    print(f"[DEBUG] Request Log: {log_data.model_dump_json()}")
                except AttributeError:
                    # Fallback for Pydantic v1
                    print(f"[DEBUG] Request Log: {log_data.json()}")

                # client disconnect 会触发取消，使用 shield 确保日志仍能写入 DB
                try:
                    with anyio.CancelScope(shield=True):
                        await self.log_repo.create(log_data)
                except Exception:
                    # 日志写入失败不影响主流程
                    pass

        return initial_response, wrapped_generator(), {
            "trace_id": trace_id,
            "retry_count": retry_count,
            "target_model": final_provider.target_model if final_provider else None,
            "provider_name": final_provider.provider_name if final_provider else None,
        }