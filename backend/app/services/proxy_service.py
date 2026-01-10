"""
代理核心服务模块

实现请求代理的核心业务逻辑。
"""

import json
import asyncio
import time
from datetime import datetime
from typing import Any, Optional, AsyncGenerator

import anyio

from app.common.errors import NotFoundError, ServiceError
from app.common.sanitizer import sanitize_headers
from app.common.stream_usage import StreamUsageAccumulator
from app.common.token_counter import get_token_counter
from app.common.utils import generate_trace_id
from app.domain.log import RequestLogCreate
from app.domain.provider import Provider
from app.providers import get_provider_client, ProviderResponse
from app.repositories.model_repo import ModelRepository
from app.repositories.provider_repo import ProviderRepository
from app.repositories.log_repo import LogRepository
from app.rules import RuleEngine, RuleContext, TokenUsage, CandidateProvider
from app.services.retry_handler import RetryHandler
from app.services.strategy import RoundRobinStrategy


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
    ):
        """
        初始化服务
        
        Args:
            model_repo: 模型 Repository
            provider_repo: 供应商 Repository
            log_repo: 日志 Repository
        """
        self.model_repo = model_repo
        self.provider_repo = provider_repo
        self.log_repo = log_repo
        self.rule_engine = RuleEngine()
        self.strategy = RoundRobinStrategy()
        self.retry_handler = RetryHandler(self.strategy)
    
    async def process_request(
        self,
        api_key_id: int,
        api_key_name: str,
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
        
        # 3. 获取模型-供应商映射
        provider_mappings = await self.model_repo.get_provider_mappings(
            requested_model=requested_model,
            is_active=True,
        )
        
        if not provider_mappings:
            raise ServiceError(
                message=f"No providers configured for model '{requested_model}'",
                code="no_available_provider",
            )
        
        # 4. 获取供应商信息
        provider_ids = [pm.provider_id for pm in provider_mappings]
        providers: dict[int, Provider] = {}
        for pid in provider_ids:
            provider = await self.provider_repo.get_by_id(pid)
            if provider:
                providers[pid] = provider
        
        # 5. 计算输入 Token
        # 根据第一个供应商的协议确定 token 计数器
        first_provider = providers.get(provider_mappings[0].provider_id)
        protocol = first_provider.protocol if first_provider else "openai"
        token_counter = get_token_counter(protocol)
        
        messages = body.get("messages", [])
        input_tokens = token_counter.count_messages(messages, requested_model)
        
        # 6. 构建规则上下文
        context = RuleContext(
            current_model=requested_model,
            headers=headers,
            request_body=body,
            token_usage=TokenUsage(input_tokens=input_tokens),
        )
        
        # 7. 规则引擎匹配
        candidates = await self.rule_engine.evaluate(
            context=context,
            model_mapping=model_mapping,
            provider_mappings=provider_mappings,
            providers=providers,
        )
        
        if not candidates:
            raise ServiceError(
                message="No providers matched the rules",
                code="no_available_provider",
            )
        
        # 8. 执行请求（带重试）
        async def forward_fn(candidate: CandidateProvider) -> ProviderResponse:
            client = get_provider_client(candidate.protocol)
            return await client.forward(
                base_url=candidate.base_url,
                api_key=candidate.api_key,
                path=path,
                method=method,
                headers=headers,
                body=body,
                target_model=candidate.target_model,
            )
        
        result = await self.retry_handler.execute_with_retry(
            candidates=candidates,
            requested_model=requested_model,
            forward_fn=forward_fn,
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
                else result.response.body
            )
            if result.response.body is not None
            else None,
            error_info=result.response.error,
            trace_id=trace_id,
        )
        
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
            
        model_mapping = await self.model_repo.get_mapping(requested_model)
        if not model_mapping:
            raise NotFoundError(message=f"Model '{requested_model}' not found", code="model_not_found")
            
        if not model_mapping.is_active:
            raise ServiceError(message=f"Model '{requested_model}' disabled", code="model_disabled")
            
        provider_mappings = await self.model_repo.get_provider_mappings(requested_model, True)
        if not provider_mappings:
            raise ServiceError(message=f"No providers for '{requested_model}'", code="no_available_provider")
            
        provider_ids = [pm.provider_id for pm in provider_mappings]
        providers = {}
        for pid in provider_ids:
            p = await self.provider_repo.get_by_id(pid)
            if p:
                providers[pid] = p
                
        # 计算输入 token
        first_provider = providers.get(provider_mappings[0].provider_id)
        protocol = first_provider.protocol if first_provider else "openai"
        token_counter = get_token_counter(protocol)
        messages = body.get("messages", [])
        input_tokens = token_counter.count_messages(messages, requested_model)
        
        context = RuleContext(
            current_model=requested_model,
            headers=headers,
            request_body=body,
            token_usage=TokenUsage(input_tokens=input_tokens),
        )
        
        candidates = await self.rule_engine.evaluate(
            context, model_mapping, provider_mappings, providers
        )
        
        if not candidates:
            raise ServiceError(message="No matched providers", code="no_available_provider")
            
        # 8. 执行流式请求
        def forward_stream_fn(candidate: CandidateProvider):
            client = get_provider_client(candidate.protocol)
            return client.forward_stream(
                base_url=candidate.base_url,
                api_key=candidate.api_key,
                path=path,
                method=method,
                headers=headers,
                body=body,
                target_model=candidate.target_model,
            )
            
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
                )
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
