"""
OpenAI 兼容代理接口

提供 OpenAI 风格的 API 代理端点。
"""

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse, Response

from app.api.deps import CurrentApiKey, ProxyServiceDep, ModelServiceDep
from app.common.errors import AppError

router = APIRouter(tags=["OpenAI Proxy"])


@router.get("/v1/models")
async def list_models(
    api_key: CurrentApiKey,
    model_service: ModelServiceDep,
) -> Any:
    """
    OpenAI List Models 代理接口
    
    返回配置的可用模型列表。
    """
    mappings, _ = await model_service.get_all_mappings(
        is_active=True,
        page=1,
        page_size=1000
    )
    
    data = []
    for mapping in mappings:
        data.append({
            "id": mapping.requested_model,
            "object": "model",
            "created": int(mapping.created_at.timestamp()),
            "owned_by": "system",
        })
        
    return {
        "object": "list",
        "data": data
    }


@router.post("/v1/chat/completions")
async def chat_completions(
    request: Request,
    api_key: CurrentApiKey,
    proxy_service: ProxyServiceDep,
) -> Any:
    """
    OpenAI Chat Completions 代理接口
    
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
                request_protocol="openai",
                path="/v1/chat/completions",
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
            request_protocol="openai",
            path="/v1/chat/completions",
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


@router.post("/v1/completions")
async def completions(
    request: Request,
    api_key: CurrentApiKey,
    proxy_service: ProxyServiceDep,
) -> Any:
    """
    OpenAI Text Completions 代理接口
    """
    body = await request.json()
    headers = dict(request.headers)
    
    try:
        response, log_info = await proxy_service.process_request(
            api_key_id=api_key.id,
            api_key_name=api_key.key_name,
            request_protocol="openai",
            path="/v1/completions",
            method="POST",
            headers=headers,
            body=body,
        )
        
        if response.is_success:
            if isinstance(response.body, (bytes, bytearray)):
                return Response(
                    content=response.body,
                    status_code=response.status_code,
                    media_type=response.headers.get("content-type", "application/json"),
                )
            return JSONResponse(
                content=response.body,
                status_code=response.status_code,
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


@router.post("/v1/embeddings")
async def embeddings(
    request: Request,
    api_key: CurrentApiKey,
    proxy_service: ProxyServiceDep,
) -> Any:
    """
    OpenAI Embeddings 代理接口
    """
    body = await request.json()
    headers = dict(request.headers)
    
    try:
        response, log_info = await proxy_service.process_request(
            api_key_id=api_key.id,
            api_key_name=api_key.key_name,
            request_protocol="openai",
            path="/v1/embeddings",
            method="POST",
            headers=headers,
            body=body,
        )
        
        if response.is_success:
            if isinstance(response.body, (bytes, bytearray)):
                return Response(
                    content=response.body,
                    status_code=response.status_code,
                    media_type=response.headers.get("content-type", "application/json"),
                )
            return JSONResponse(
                content=response.body,
                status_code=response.status_code,
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
