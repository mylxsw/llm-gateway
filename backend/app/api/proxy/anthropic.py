"""
Anthropic 兼容代理接口

提供 Anthropic 风格的 API 代理端点。
"""

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse, Response

from app.api.deps import CurrentApiKey, ProxyServiceDep
from app.common.errors import AppError

router = APIRouter(tags=["Anthropic Proxy"])


@router.post("/v1/messages")
async def messages(
    request: Request,
    api_key: CurrentApiKey,
    proxy_service: ProxyServiceDep,
) -> Any:
    """
    Anthropic Messages 代理接口
    
    将请求转发到配置的上游供应商，仅修改 model 字段。
    支持普通请求和流式请求。
    """
    # 获取请求体
    body = await request.json()
    
    # 获取请求头
    headers = dict(request.headers)
    
    try:
        if body.get("stream", False):
            # 处理流式请求
            initial_response, stream_generator, log_info = await proxy_service.process_request_stream(
                api_key_id=api_key.id,
                api_key_name=api_key.key_name,
                request_protocol="anthropic",
                path="/v1/messages",
                method="POST",
                headers=headers,
                body=body,
            )
            
            if initial_response.is_success:
                return StreamingResponse(
                    stream_generator,
                    media_type="text/event-stream",
                    headers={
                        "X-Trace-ID": log_info.get("trace_id", ""),
                        "X-Target-Model": log_info.get("target_model", ""),
                        "X-Provider": log_info.get("provider_name", ""),
                    },
                    status_code=initial_response.status_code,
                )
            else:
                # 如果初始响应失败，收集错误信息并返回 JSON
                content = b""
                async for chunk in stream_generator:
                    content += chunk
                    
                try:
                    import json
                    content_data = json.loads(content)
                except Exception:
                    content_data = {"error": {"message": content.decode("utf-8", errors="ignore")}}
                
                return JSONResponse(
                    content=content_data,
                    status_code=initial_response.status_code,
                    headers={
                        "X-Trace-ID": log_info.get("trace_id", ""),
                        "X-Target-Model": log_info.get("target_model", ""),
                        "X-Provider": log_info.get("provider_name", ""),
                    },
                )

        # 处理普通请求
        response, log_info = await proxy_service.process_request(
            api_key_id=api_key.id,
            api_key_name=api_key.key_name,
            request_protocol="anthropic",
            path="/v1/messages",
            method="POST",
            headers=headers,
            body=body,
        )
        
        # 返回响应
        if response.is_success:
            if isinstance(response.body, (bytes, bytearray)):
                return Response(
                    content=response.body,
                    status_code=response.status_code,
                    media_type=response.headers.get("content-type", "application/json"),
                    headers={
                        "X-Trace-ID": log_info.get("trace_id", ""),
                        "X-Target-Model": log_info.get("target_model", ""),
                        "X-Provider": log_info.get("provider_name", ""),
                    },
                )
            return JSONResponse(
                content=response.body,
                status_code=response.status_code,
                headers={
                    "X-Trace-ID": log_info.get("trace_id", ""),
                    "X-Target-Model": log_info.get("target_model", ""),
                    "X-Provider": log_info.get("provider_name", ""),
                },
            )
        else:
            return JSONResponse(
                content=response.body or {"error": {"message": response.error}},
                status_code=response.status_code,
            )
    
    except AppError as e:
        return JSONResponse(
            content=e.to_dict(),
            status_code=e.status_code,
        )
