"""
Model Management API

Provides CRUD endpoints for Model Mappings and Model-Provider Mappings.
"""

import json
import time
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.api.deps import (
    LogServiceDep,
    ModelServiceDep,
    ProxyServiceDep,
    require_admin_auth,
)
from app.common.errors import AppError
from app.common.provider_protocols import (
    ANTHROPIC_PROTOCOL,
    OPENAI_RESPONSES_PROTOCOL,
    resolve_implementation_protocol,
)
from app.common.stream_usage import SSEDecoder, StreamUsageAccumulator
from app.domain.log import ModelProviderStats, ModelStats
from app.domain.model import (
    ModelExport,
    ModelMappingCreate,
    ModelMappingProviderCreate,
    ModelMappingProviderResponse,
    ModelMappingProviderUpdate,
    ModelMappingResponse,
    ModelMappingUpdate,
    ModelMatchProviderResponse,
    ModelMatchRequest,
)

router = APIRouter(
    prefix="/admin",
    tags=["Admin - Models"],
    dependencies=[Depends(require_admin_auth)],
)


class PaginatedModelResponse(BaseModel):
    """Model Mapping Pagination Response"""

    items: list[ModelMappingResponse]
    total: int
    page: int
    page_size: int


class ModelProviderListResponse(BaseModel):
    """Model-Provider Mapping List Response"""

    items: list[ModelMappingProviderResponse]
    total: int


class ImportModelResponse(BaseModel):
    """Import Model Response"""

    success: int
    skipped: int
    errors: list[str]


class ModelTestRequest(BaseModel):
    """Model test request"""

    protocol: str
    stream: bool = False


class ModelTestResponse(BaseModel):
    """Model test response"""

    content: str
    response_status: int
    total_time_ms: Optional[int] = None
    first_byte_delay_ms: Optional[int] = None
    provider_name: Optional[str] = None
    target_model: Optional[str] = None


def _build_test_payload(
    requested_model: str,
    protocol: str,
    stream: bool,
) -> tuple[str, dict[str, Any], str]:
    implementation = resolve_implementation_protocol(protocol)
    if implementation == ANTHROPIC_PROTOCOL:
        return (
            "/v1/messages",
            {
                "model": requested_model,
                "messages": [{"role": "user", "content": "hello"}],
                "max_tokens": 1024,
                "stream": stream,
            },
            implementation,
        )

    if implementation == OPENAI_RESPONSES_PROTOCOL:
        return (
            "/v1/responses",
            {
                "model": requested_model,
                "input": "hello",
                "max_output_tokens": 1024,
                "stream": stream,
            },
            implementation,
        )

    return (
        "/v1/chat/completions",
        {
            "model": requested_model,
            "messages": [{"role": "user", "content": "hello"}],
            "max_tokens": 1024,
            "stream": stream,
        },
        implementation,
    )


def _normalize_response_body(body: Any) -> Any:
    if body is None:
        return None
    if isinstance(body, (bytes, bytearray)):
        try:
            decoded = body.decode("utf-8", errors="ignore")
        except Exception:
            return body
        try:
            return json.loads(decoded)
        except Exception:
            return decoded
    if isinstance(body, str):
        try:
            return json.loads(body)
        except Exception:
            return body
    return body


def _extract_text_from_response(body: Any, implementation: str) -> str:
    if not isinstance(body, dict):
        return "" if body is None else str(body)

    error = body.get("error")
    if isinstance(error, dict):
        message = error.get("message")
        if isinstance(message, str) and message:
            return message

    if implementation == ANTHROPIC_PROTOCOL:
        content = body.get("content")
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str) and text:
                        parts.append(text)
            if parts:
                return "".join(parts)
        text = body.get("text")
        if isinstance(text, str):
            return text

    if implementation == OPENAI_RESPONSES_PROTOCOL:
        output = body.get("output")
        if isinstance(output, list):
            parts: list[str] = []
            for item in output:
                if not isinstance(item, dict) or item.get("type") != "message":
                    continue
                content = item.get("content")
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict):
                            text = block.get("text")
                            if isinstance(text, str) and text:
                                parts.append(text)
            if parts:
                return "".join(parts)
        text = body.get("output_text")
        if isinstance(text, str):
            return text

    choices = body.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            message = first.get("message")
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, str):
                    return content
                if isinstance(content, list):
                    parts: list[str] = []
                    for block in content:
                        if isinstance(block, dict):
                            text = block.get("text")
                            if isinstance(text, str) and text:
                                parts.append(text)
                    if parts:
                        return "".join(parts)
            text = first.get("text")
            if isinstance(text, str):
                return text

    return json.dumps(body, ensure_ascii=False)


async def _collect_stream_text(
    stream,
    implementation: str,
    requested_model: str,
) -> str:
    if implementation == OPENAI_RESPONSES_PROTOCOL:
        decoder = SSEDecoder()
        parts: list[str] = []
        completed_text: Optional[str] = None

        async for chunk in stream:
            for payload in decoder.feed(chunk):
                stripped = payload.strip()
                if not stripped or stripped == "[DONE]":
                    continue
                try:
                    data = json.loads(payload)
                except Exception:
                    continue
                event_type = data.get("type")
                if event_type == "response.output_text.delta":
                    delta = data.get("delta")
                    if isinstance(delta, str) and delta:
                        parts.append(delta)
                elif event_type == "response.completed":
                    response = data.get("response")
                    if isinstance(response, dict):
                        completed_text = _extract_text_from_response(
                            response, implementation
                        )

        if parts:
            return "".join(parts)
        return completed_text or ""

    usage_acc = StreamUsageAccumulator(protocol=implementation, model=requested_model)
    async for chunk in stream:
        usage_acc.feed(chunk)
    return usage_acc.finalize().output_text


# ============ Model Mapping Endpoints ============


@router.get("/models/export", response_model=list[ModelExport])
async def export_models(
    service: ModelServiceDep,
):
    """
    Export all models
    """
    try:
        return await service.export_data()
    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)


@router.post("/models/import", response_model=ImportModelResponse)
async def import_models(
    data: list[ModelExport],
    service: ModelServiceDep,
):
    """
    Import models
    """
    try:
        result = await service.import_data(data)
        return ImportModelResponse(**result)
    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)


@router.get("/models", response_model=PaginatedModelResponse)
async def list_models(
    service: ModelServiceDep,
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    requested_model: Optional[str] = Query(None, description="Filter by model name"),
    model_type: Optional[str] = Query(None, description="Filter by model type"),
    strategy: Optional[str] = Query(None, description="Filter by strategy"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=1000, description="Items per page"),
):
    """
    Get Model Mapping List
    """
    try:
        items, total = await service.get_all_mappings(
            is_active=is_active,
            page=page,
            page_size=page_size,
            requested_model=requested_model,
            model_type=model_type,
            strategy=strategy,
        )
        return PaginatedModelResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )
    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)


@router.get("/models/stats", response_model=list[ModelStats])
async def list_model_stats(
    service: LogServiceDep,
    requested_model: Optional[str] = Query(None, description="Filter by model name"),
):
    """
    Get model stats based on logs for the last 7 days
    """
    try:
        return await service.get_model_stats(requested_model=requested_model)
    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)


@router.get("/models/provider-stats", response_model=list[ModelProviderStats])
async def list_model_provider_stats(
    service: LogServiceDep,
    requested_model: Optional[str] = Query(None, description="Filter by model name"),
):
    """
    Get model-provider stats based on logs for the last 7 days
    """
    try:
        return await service.get_model_provider_stats(requested_model=requested_model)
    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)


@router.get("/models/{requested_model:path}", response_model=ModelMappingResponse)
async def get_model(
    requested_model: str,
    service: ModelServiceDep,
):
    """
    Get single Model Mapping details (including provider configuration)
    """
    try:
        return await service.get_mapping(requested_model)
    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)


@router.post(
    "/models/{requested_model:path}/match",
    response_model=list[ModelMatchProviderResponse],
)
async def match_model_providers(
    requested_model: str,
    data: ModelMatchRequest,
    service: ModelServiceDep,
):
    """
    Match model providers based on input tokens and headers.
    """
    try:
        return await service.match_providers(requested_model, data)
    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)


@router.post("/models/{requested_model:path}/test", response_model=ModelTestResponse)
async def test_model(
    requested_model: str,
    data: ModelTestRequest,
    service: ProxyServiceDep,
):
    """
    Simulate a chat request for the specified model and protocol.
    """
    try:
        path, body, implementation = _build_test_payload(
            requested_model=requested_model,
            protocol=data.protocol,
            stream=data.stream,
        )
        headers: dict[str, str] = {}

        if data.stream:
            start = time.monotonic()
            (
                initial_response,
                stream_gen,
                _log_info,
            ) = await service.process_request_stream(
                api_key_id=None,
                api_key_name=None,
                request_protocol=data.protocol,
                path=path,
                method="POST",
                headers=headers,
                body=body,
            )
            content = await _collect_stream_text(
                stream=stream_gen,
                implementation=implementation,
                requested_model=requested_model,
            )
            elapsed_ms = int((time.monotonic() - start) * 1000)
            if not content and initial_response.error:
                content = initial_response.error

            return ModelTestResponse(
                content=content,
                response_status=initial_response.status_code,
                total_time_ms=initial_response.total_time_ms or elapsed_ms,
                first_byte_delay_ms=initial_response.first_byte_delay_ms,
                provider_name=_log_info.get("provider_name") if _log_info else None,
                target_model=_log_info.get("target_model") if _log_info else None,
            )

        start = time.monotonic()
        response, _log_info = await service.process_request(
            api_key_id=None,
            api_key_name=None,
            request_protocol=data.protocol,
            path=path,
            method="POST",
            headers=headers,
            body=body,
            force_parse_response=True,
        )
        elapsed_ms = int((time.monotonic() - start) * 1000)
        normalized = _normalize_response_body(response.body)
        content = _extract_text_from_response(normalized, implementation)
        if not content and response.error:
            content = response.error

        return ModelTestResponse(
            content=content,
            response_status=response.status_code,
            total_time_ms=response.total_time_ms or elapsed_ms,
            first_byte_delay_ms=response.first_byte_delay_ms,
            provider_name=_log_info.get("provider_name") if _log_info else None,
            target_model=_log_info.get("target_model") if _log_info else None,
        )
    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)


@router.post(
    "/models", response_model=ModelMappingResponse, status_code=status.HTTP_201_CREATED
)
async def create_model(
    data: ModelMappingCreate,
    service: ModelServiceDep,
):
    """
    Create Model Mapping
    """
    try:
        return await service.create_mapping(data)
    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)


@router.put("/models/{requested_model:path}", response_model=ModelMappingResponse)
async def update_model(
    requested_model: str,
    data: ModelMappingUpdate,
    service: ModelServiceDep,
):
    """
    Update Model Mapping
    """
    try:
        return await service.update_mapping(requested_model, data)
    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)


@router.delete("/models/{requested_model:path}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model(
    requested_model: str,
    service: ModelServiceDep,
):
    """
    Delete Model Mapping (Simultaneously deletes associated provider configurations)
    """
    try:
        await service.delete_mapping(requested_model)
    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)


# ============ Model-Provider Mapping Endpoints ============


@router.get("/model-providers", response_model=ModelProviderListResponse)
async def list_model_providers(
    service: ModelServiceDep,
    requested_model: Optional[str] = Query(None, description="Filter by model"),
    provider_id: Optional[int] = Query(None, description="Filter by provider"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
):
    """
    Get Model-Provider Mapping List
    """
    try:
        items = await service.get_provider_mappings(
            requested_model, provider_id, is_active
        )
        return ModelProviderListResponse(
            items=items,
            total=len(items),
        )
    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)


@router.post(
    "/model-providers",
    response_model=ModelMappingProviderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_model_provider(
    data: ModelMappingProviderCreate,
    service: ModelServiceDep,
):
    """
    Create Model-Provider Mapping
    """
    try:
        return await service.create_provider_mapping(data)
    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)


@router.put(
    "/model-providers/{mapping_id}", response_model=ModelMappingProviderResponse
)
async def update_model_provider(
    mapping_id: int,
    data: ModelMappingProviderUpdate,
    service: ModelServiceDep,
):
    """
    Update Model-Provider Mapping
    """
    try:
        return await service.update_provider_mapping(mapping_id, data)
    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)


@router.delete("/model-providers/{mapping_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model_provider(
    mapping_id: int,
    service: ModelServiceDep,
):
    """
    Delete Model-Provider Mapping
    """
    try:
        await service.delete_provider_mapping(mapping_id)
    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)
