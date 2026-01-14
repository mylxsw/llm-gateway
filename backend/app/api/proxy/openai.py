"""
OpenAI Proxy API

Provides OpenAI-compatible API endpoints.
"""

from typing import Any

from fastapi import APIRouter, Header, Request, status
from fastapi.responses import JSONResponse, Response, StreamingResponse

from app.api.deps import CurrentApiKey, ModelServiceDep, ProxyServiceDep
from app.common.errors import AppError

router = APIRouter(tags=["Proxy - OpenAI"])


@router.get("/v1/models")
async def list_models(
    api_key: CurrentApiKey,
    service: ModelServiceDep,
):
    """
    OpenAI Models API (List)

    Returns active requested models configured in the gateway.
    """
    try:
        items, _total = await service.get_all_mappings(is_active=True, page=1, page_size=1000)
        return {
            "object": "list",
            "data": [
                {
                    "id": item.requested_model,
                    "object": "model",
                    "owned_by": "system",
                }
                for item in items
            ],
        }
    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)


async def _handle_proxy_request(
    request: Request,
    api_key: CurrentApiKey,
    service: ProxyServiceDep,
    path: str,
):
    """
    Handle generic proxy request logic
    """
    try:
        body = await request.json()
        headers = dict(request.headers)
        
        # Determine if it's a streaming request
        is_stream = body.get("stream", False)
        
        if is_stream:
            initial_response, stream_gen, log_info = await service.process_request_stream(
                api_key_id=api_key.id,
                api_key_name=api_key.key_name,
                request_protocol="openai",
                path=path,
                method=request.method,
                headers=headers,
                body=body,
            )
            
            # If initial response is error, return directly
            if not initial_response.is_success:
                content = initial_response.body
                if isinstance(content, (dict, list)):
                    return JSONResponse(
                        content=content,
                        status_code=initial_response.status_code,
                        headers=initial_response.headers,
                    )
                return Response(
                    content=content,
                    status_code=initial_response.status_code,
                    headers=initial_response.headers,
                )
            
            return StreamingResponse(
                stream_gen,
                status_code=initial_response.status_code,
                headers=initial_response.headers,
                media_type="text/event-stream",
            )
        else:
            response, log_info = await service.process_request(
                api_key_id=api_key.id,
                api_key_name=api_key.key_name,
                request_protocol="openai",
                path=path,
                method=request.method,
                headers=headers,
                body=body,
            )
            
            content = response.body
            if isinstance(content, (dict, list)):
                return JSONResponse(
                    content=content,
                    status_code=response.status_code,
                    headers=response.headers,
                )
            return Response(
                content=content,
                status_code=response.status_code,
                headers=response.headers,
            )
            
    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)
    except Exception as e:
        # Unexpected errors return 500
        import logging
        logging.getLogger(__name__).error(f"Unexpected error: {str(e)}", exc_info=True)
        return JSONResponse(
            content={
                "error": {
                    "message": "Internal server error",
                    "type": "internal_error",
                    "code": "internal_error"
                }
            },
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@router.post("/v1/chat/completions")
async def chat_completions(
    request: Request,
    api_key: CurrentApiKey,
    service: ProxyServiceDep,
):
    """
    OpenAI Chat Completions API Proxy
    """
    return await _handle_proxy_request(request, api_key, service, "/v1/chat/completions")


@router.post("/v1/completions")
async def completions(
    request: Request,
    api_key: CurrentApiKey,
    service: ProxyServiceDep,
):
    """
    OpenAI Completions API Proxy
    """
    return await _handle_proxy_request(request, api_key, service, "/v1/completions")


@router.post("/v1/embeddings")
async def embeddings(
    request: Request,
    api_key: CurrentApiKey,
    service: ProxyServiceDep,
):
    """
    OpenAI Embeddings API Proxy
    """
    return await _handle_proxy_request(request, api_key, service, "/v1/embeddings")
