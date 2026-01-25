"""
Provider Management Service Module

Provides business logic processing for Providers.
"""

import json
from typing import Any, Optional

from app.common.errors import ConflictError, NotFoundError
from app.common.proxy import build_proxy_config
from app.common.provider_protocols import resolve_implementation_protocol
from app.common.sanitizer import sanitize_api_key_display, sanitize_proxy_url
from app.domain.provider import Provider, ProviderCreate, ProviderUpdate, ProviderResponse
from app.providers import get_provider_client
from app.repositories.provider_repo import ProviderRepository


class ProviderService:
    """
    Provider Management Service
    
    Handles business logic related to providers, including CRUD operations and business rule validation.
    """
    
    def __init__(self, repo: ProviderRepository):
        """
        Initialize Service
        
        Args:
            repo: Provider Repository
        """
        self.repo = repo
    
    async def create(self, data: ProviderCreate) -> ProviderResponse:
        """
        Create Provider
        
        Args:
            data: Creation data
        
        Returns:
            ProviderResponse: Created provider (API Key sanitized)
        
        Raises:
            ConflictError: Name already exists
        """
        # Check if name already exists
        existing = await self.repo.get_by_name(data.name)
        if existing:
            raise ConflictError(
                message=f"Provider with name '{data.name}' already exists",
                code="duplicate_name",
            )
        
        provider = await self.repo.create(data)
        return self._to_response(provider)
    
    async def get_by_id(self, id: int) -> ProviderResponse:
        """
        Get Provider by ID
        
        Args:
            id: Provider ID
        
        Returns:
            ProviderResponse: Provider info (API Key sanitized)
        
        Raises:
            NotFoundError: Provider not found
        """
        provider = await self.repo.get_by_id(id)
        if not provider:
            raise NotFoundError(
                message=f"Provider with id {id} not found",
                code="provider_not_found",
            )
        return self._to_response(provider)
    
    async def get_all(
        self,
        is_active: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
        name: Optional[str] = None,
        protocol: Optional[str] = None,
    ) -> tuple[list[ProviderResponse], int]:
        """
        Get Provider List
        
        Args:
            is_active: Filter by active status
            page: Page number
            page_size: Items per page
            name: Filter by name (fuzzy)
            protocol: Filter by protocol
        
        Returns:
            tuple[list[ProviderResponse], int]: (Provider list, Total count)
        """
        providers, total = await self.repo.get_all(
            is_active=is_active, 
            page=page, 
            page_size=page_size,
            name=name,
            protocol=protocol
        )
        return [self._to_response(p) for p in providers], total
    
    async def update(self, id: int, data: ProviderUpdate) -> ProviderResponse:
        """
        Update Provider
        
        Args:
            id: Provider ID
            data: Update data
        
        Returns:
            ProviderResponse: Updated provider
        
        Raises:
            NotFoundError: Provider not found
            ConflictError: Name already used by another provider
        """
        # Check if provider exists
        existing = await self.repo.get_by_id(id)
        if not existing:
            raise NotFoundError(
                message=f"Provider with id {id} not found",
                code="provider_not_found",
            )
        
        # If updating name, check for conflict with other providers
        if data.name and data.name != existing.name:
            name_conflict = await self.repo.get_by_name(data.name)
            if name_conflict:
                raise ConflictError(
                    message=f"Provider with name '{data.name}' already exists",
                    code="duplicate_name",
                )
        
        provider = await self.repo.update(id, data)
        return self._to_response(provider)  # type: ignore
    
    async def delete(self, id: int) -> None:
        """
        Delete Provider
        
        Args:
            id: Provider ID
        
        Raises:
            NotFoundError: Provider not found
            ConflictError: Provider referenced by model mappings
        """
        # Check if provider exists
        existing = await self.repo.get_by_id(id)
        if not existing:
            raise NotFoundError(
                message=f"Provider with id {id} not found",
                code="provider_not_found",
            )
        
        # Check if referenced
        if await self.repo.has_model_mappings(id):
            raise ConflictError(
                message="Provider is referenced by model mappings",
                code="provider_in_use",
            )
        
        await self.repo.delete(id)

    async def export_data(self) -> list[ProviderCreate]:
        """
        Export all providers
        
        Returns:
            list[ProviderCreate]: List of providers with full details
        """
        # Get all providers without pagination (using a large limit)
        providers, _ = await self.repo.get_all(page=1, page_size=10000)
        
        export_list = []
        for p in providers:
            export_list.append(
                ProviderCreate(
                    name=p.name,
                    base_url=p.base_url,
                    protocol=p.protocol,
                    api_type=p.api_type,
                    extra_headers=p.extra_headers,
                    api_key=p.api_key,
                    is_active=p.is_active,
                    proxy_enabled=p.proxy_enabled,
                    proxy_url=p.proxy_url,
                )
            )
        return export_list

    async def import_data(self, data: list[ProviderCreate]) -> dict[str, int]:
        """
        Import providers
        
        Args:
            data: List of providers to import
            
        Returns:
            dict: Import summary (success, skipped)
        """
        success = 0
        skipped = 0
        
        for item in data:
            # Check if name already exists
            existing = await self.repo.get_by_name(item.name)
            if existing:
                skipped += 1
                continue
            
            await self.repo.create(item)
            success += 1
            
        return {"success": success, "skipped": skipped}

    async def list_upstream_models(
        self, id: int
    ) -> tuple[Provider, list[str], Optional[dict[str, Any]]]:
        """
        List upstream models for the given provider

        Args:
            id: Provider ID

        Returns:
            tuple[Provider, list[str], Optional[dict[str, Any]]]: Provider info, model list, and error info
        """
        provider = await self.repo.get_by_id(id)
        if not provider:
            raise NotFoundError(
                message=f"Provider with id {id} not found",
                code="provider_not_found",
            )

        implementation_protocol = resolve_implementation_protocol(provider.protocol)
        client = get_provider_client(implementation_protocol)
        proxy_config = build_proxy_config(provider.proxy_enabled, provider.proxy_url)
        response = await client.list_models(
            base_url=provider.base_url,
            api_key=provider.api_key,
            extra_headers=provider.extra_headers,
            proxy_config=proxy_config,
        )

        if not response.is_success:
            details: dict[str, Any] = {
                "provider_id": provider.id,
                "status_code": response.status_code,
            }
            if response.error:
                details["error"] = response.error
            if response.body is not None:
                details["body"] = response.body
            error = {
                "message": "Upstream model list request failed",
                "code": "upstream_model_list_failed",
                "details": details,
            }
            return provider, [], error

        models = self._extract_model_ids(response.body)
        return provider, models, None

    @staticmethod
    def _extract_model_ids(body: Any) -> list[str]:
        if isinstance(body, str):
            try:
                body = json.loads(body)
            except json.JSONDecodeError:
                return []

        candidates: Any = None
        if isinstance(body, dict):
            if isinstance(body.get("data"), list):
                candidates = body["data"]
            elif isinstance(body.get("models"), list):
                candidates = body["models"]
            elif isinstance(body.get("items"), list):
                candidates = body["items"]
        elif isinstance(body, list):
            candidates = body

        if not isinstance(candidates, list):
            return []

        seen = set()
        results: list[str] = []
        for item in candidates:
            model_id = None
            if isinstance(item, dict):
                for key in ("id", "model", "name"):
                    value = item.get(key)
                    if isinstance(value, str) and value:
                        model_id = value
                        break
            elif isinstance(item, str):
                model_id = item

            if model_id and model_id not in seen:
                seen.add(model_id)
                results.append(model_id)

        return results
    
    def _to_response(self, provider: Provider) -> ProviderResponse:
        """
        Convert Provider to response model (API Key sanitized)
        
        Args:
            provider: Provider model
        
        Returns:
            ProviderResponse: Response model
        """
        return ProviderResponse(
            id=provider.id,
            name=provider.name,
            base_url=provider.base_url,
            protocol=provider.protocol,
            api_type=provider.api_type,
            api_key=sanitize_api_key_display(provider.api_key) if provider.api_key else None,
            extra_headers=provider.extra_headers,
            proxy_enabled=provider.proxy_enabled,
            proxy_url=sanitize_proxy_url(provider.proxy_url) if provider.proxy_url else None,
            is_active=provider.is_active,
            created_at=provider.created_at,
            updated_at=provider.updated_at,
        )
