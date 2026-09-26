"""
Jev Proxy API

Provides TypeSafe Jev-compatible API endpoints.

Jev has no streaming mode, so requests always go through the non-streaming
proxy path. The gateway forwards the body untouched apart from the model field.
"""

from typing import Any

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse, Response

from app.api.deps import CurrentApiKey, ProxyServiceDep
from app.common.errors import AppError
from app.common.proxy_headers import sanitize_upstream_response_headers

router = APIRouter(tags=["Proxy - Jev"])

JEV_PROTOCOL_NAME = "jev"


def _with_trace_id_header(
    headers: dict[str, str],
    trace_id: str | None,
) -> dict[str, str]:
    merged = dict(headers)
    if trace_id:
        merged["x-lgw-trace-id"] = trace_id
    return merged


@router.post("/v1/systemone")
async def systemone(
    request: Request,
    api_key: CurrentApiKey,
    service: ProxyServiceDep,
):
    """
    Jev Evaluation API Proxy

    Forwards the request to a Jev-protocol provider and returns its response
    unchanged. Logging and billing are handled by the shared proxy service.
    """
    try:
        body: dict[str, Any] = await request.json()
        headers = dict(request.headers)

        response, log_info = await service.process_request(
            api_key_id=api_key.id,
            api_key_name=api_key.key_name,
            record_details=api_key.record_details,
            request_protocol=JEV_PROTOCOL_NAME,
            path="/v1/systemone",
            request_url=str(request.url),
            method=request.method,
            headers=headers,
            body=body,
        )

        content = response.body
        if isinstance(content, (dict, list)):
            return JSONResponse(
                content=content,
                status_code=response.status_code,
                headers=_with_trace_id_header(
                    sanitize_upstream_response_headers(response.headers),
                    log_info.get("trace_id") if log_info else None,
                ),
            )
        return Response(
            content=content,
            status_code=response.status_code,
            headers=_with_trace_id_header(
                sanitize_upstream_response_headers(response.headers),
                log_info.get("trace_id") if log_info else None,
            ),
        )

    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)
    except Exception as e:
        import logging

        logging.getLogger(__name__).error(f"Unexpected error: {str(e)}", exc_info=True)
        return JSONResponse(
            content={
                "error": {
                    "message": "Internal server error",
                    "type": "internal_error",
                    "code": "internal_error",
                }
            },
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
