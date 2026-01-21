"""
Anthropic Proxy API

Provides Anthropic-compatible API endpoints.
"""

from typing import Any

from fastapi import APIRouter, Header, Request, status
from fastapi.responses import JSONResponse, Response, StreamingResponse

from app.api.deps import CurrentApiKey, ProxyServiceDep
from app.common.errors import AppError
from app.common.proxy_headers import sanitize_upstream_response_headers

router = APIRouter(tags=["Proxy - Anthropic"])


@router.post("/v1/messages")
async def create_message(
    request: Request,
    api_key: CurrentApiKey,
    service: ProxyServiceDep,
    x_api_key: str = Header(None, description="Anthropic API Key", alias="x-api-key"),
    anthropic_version: str = Header(None, description="Anthropic Version"),
):
    """
    Anthropic Messages API Proxy
    
    Forward requests to configured upstream providers.
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
                request_protocol="anthropic",
                path="/v1/messages",
                method="POST",
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
                        headers=sanitize_upstream_response_headers(initial_response.headers),
                    )
                return Response(
                    content=content,
                    status_code=initial_response.status_code,
                    headers=sanitize_upstream_response_headers(initial_response.headers),
                )
            
            return StreamingResponse(
                stream_gen,
                status_code=initial_response.status_code,
                headers=sanitize_upstream_response_headers(initial_response.headers),
                media_type="text/event-stream",
            )
        else:
            response, log_info = await service.process_request(
                api_key_id=api_key.id,
                api_key_name=api_key.key_name,
                request_protocol="anthropic",
                path="/v1/messages",
                method="POST",
                headers=headers,
                body=body,
            )
            
            content = response.body
            if isinstance(content, (dict, list)):
                return JSONResponse(
                    content=content,
                    status_code=response.status_code,
                    headers=sanitize_upstream_response_headers(response.headers),
                )
            return Response(
                content=content,
                status_code=response.status_code,
                headers=sanitize_upstream_response_headers(response.headers),
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
