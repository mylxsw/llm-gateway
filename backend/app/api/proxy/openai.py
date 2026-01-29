"""
OpenAI Proxy API

Provides OpenAI-compatible API endpoints.
"""

import json
from typing import Any

from fastapi import APIRouter, Header, Request, status
from fastapi.responses import JSONResponse, Response, StreamingResponse
from starlette.datastructures import UploadFile

from app.api.deps import CurrentApiKey, ModelServiceDep, ProxyServiceDep
from app.common.errors import AppError
from app.common.proxy_headers import sanitize_upstream_response_headers

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
        items, _total = await service.get_all_mappings(
            is_active=True, page=1, page_size=1000
        )
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


async def _handle_proxy_request_with_body(
    request: Request,
    api_key: CurrentApiKey,
    service: ProxyServiceDep,
    path: str,
    body: dict[str, Any],
):
    """
    Handle generic proxy request logic with an already parsed body.
    """
    try:
        headers = dict(request.headers)

        # Determine if it's a streaming request
        is_stream = body.get("stream", False)

        if is_stream:
            (
                initial_response,
                stream_gen,
                log_info,
            ) = await service.process_request_stream(
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
                        headers=sanitize_upstream_response_headers(
                            initial_response.headers
                        ),
                    )
                return Response(
                    content=content,
                    status_code=initial_response.status_code,
                    headers=sanitize_upstream_response_headers(
                        initial_response.headers
                    ),
                )

            return StreamingResponse(
                stream_gen,
                status_code=initial_response.status_code,
                headers=sanitize_upstream_response_headers(initial_response.headers),
                media_type="text/event-stream",
            )

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
                    "code": "internal_error",
                }
            },
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


async def _handle_proxy_request(
    request: Request,
    api_key: CurrentApiKey,
    service: ProxyServiceDep,
    path: str,
):
    """
    Handle generic proxy request logic
    """
    body = await request.json()
    return await _handle_proxy_request_with_body(request, api_key, service, path, body)


async def _parse_multipart_body(request: Request) -> dict[str, Any]:
    form = await request.form()
    fields: dict[str, list[Any]] = {}
    files: list[dict[str, Any]] = []

    for key, value in form.multi_items():
        if isinstance(value, UploadFile):
            data = await value.read()
            files.append(
                {
                    "field": key,
                    "filename": value.filename or "file",
                    "content_type": value.content_type,
                    "data": data,
                }
            )
        else:
            fields.setdefault(key, []).append(value)

    body: dict[str, Any] = {}
    for key, values in fields.items():
        body[key] = values[0] if len(values) == 1 else values
    if files:
        body["_files"] = files
    return body


async def _handle_proxy_request_multipart(
    request: Request,
    api_key: CurrentApiKey,
    service: ProxyServiceDep,
    path: str,
):
    body = await _parse_multipart_body(request)
    return await _handle_proxy_request_with_body(request, api_key, service, path, body)


@router.post("/v1/chat/completions")
async def chat_completions(
    request: Request,
    api_key: CurrentApiKey,
    service: ProxyServiceDep,
):
    """
    OpenAI Chat Completions API Proxy
    """
    return await _handle_proxy_request(
        request, api_key, service, "/v1/chat/completions"
    )


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


@router.post("/v1/audio/speech")
async def audio_speech(
    request: Request,
    api_key: CurrentApiKey,
    service: ProxyServiceDep,
):
    """
    OpenAI Audio Speech API Proxy
    """
    return await _handle_proxy_request(request, api_key, service, "/v1/audio/speech")


@router.post("/v1/audio/transcriptions")
async def audio_transcriptions(
    request: Request,
    api_key: CurrentApiKey,
    service: ProxyServiceDep,
):
    """
    OpenAI Audio Transcriptions API Proxy
    """
    return await _handle_proxy_request_multipart(
        request, api_key, service, "/v1/audio/transcriptions"
    )


@router.post("/v1/audio/translations")
async def audio_translations(
    request: Request,
    api_key: CurrentApiKey,
    service: ProxyServiceDep,
):
    """
    OpenAI Audio Translations API Proxy
    """
    return await _handle_proxy_request_multipart(
        request, api_key, service, "/v1/audio/translations"
    )


@router.post("/v1/images/generations")
async def images_generations(
    request: Request,
    api_key: CurrentApiKey,
    service: ProxyServiceDep,
):
    """
    OpenAI Images Generations API Proxy
    """
    return await _handle_proxy_request(
        request, api_key, service, "/v1/images/generations"
    )


@router.post("/v1/responses")
async def responses(
    request: Request,
    api_key: CurrentApiKey,
    service: ProxyServiceDep,
):
    """
    OpenAI Responses API Proxy

    Uses openai_responses protocol directly, letting the protocol conversion
    system handle any necessary transformations based on the target provider.
    """
    return await _handle_proxy_request_openai_responses(
        request, api_key, service, "/v1/responses"
    )


async def _handle_proxy_request_openai_responses(
    request: Request,
    api_key: CurrentApiKey,
    service: ProxyServiceDep,
    path: str,
):
    """
    Handle proxy request with openai_responses protocol.
    """
    try:
        body = await request.json()
        headers = dict(request.headers)

        is_stream = body.get("stream", False)

        if is_stream:
            (
                initial_response,
                stream_gen,
                log_info,
            ) = await service.process_request_stream(
                api_key_id=api_key.id,
                api_key_name=api_key.key_name,
                request_protocol="openai_responses",
                path=path,
                method=request.method,
                headers=headers,
                body=body,
            )

            if not initial_response.is_success:
                content = initial_response.body
                if isinstance(content, (dict, list)):
                    return JSONResponse(
                        content=content,
                        status_code=initial_response.status_code,
                        headers=sanitize_upstream_response_headers(
                            initial_response.headers
                        ),
                    )
                return Response(
                    content=content,
                    status_code=initial_response.status_code,
                    headers=sanitize_upstream_response_headers(
                        initial_response.headers
                    ),
                )

            return StreamingResponse(
                stream_gen,
                status_code=initial_response.status_code,
                headers=sanitize_upstream_response_headers(initial_response.headers),
                media_type="text/event-stream",
            )

        response, log_info = await service.process_request(
            api_key_id=api_key.id,
            api_key_name=api_key.key_name,
            request_protocol="openai_responses",
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
