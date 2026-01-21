"""
Model Management Service Module

Provides business logic processing for Model Mappings and Model-Provider Mappings.
"""

from typing import Optional

from app.common.errors import ConflictError, NotFoundError, ValidationError
from app.domain.model import (
    ModelMapping,
    ModelMappingCreate,
    ModelMappingUpdate,
    ModelMappingResponse,
    ModelMappingProvider,
    ModelMappingProviderCreate,
    ModelMappingProviderUpdate,
    ModelMappingProviderResponse,
)
from app.repositories.model_repo import ModelRepository
from app.repositories.provider_repo import ProviderRepository


class ModelService:
    """
    Model Management Service
    
    Handles business logic related to Model Mappings and Model-Provider Mappings.
    """
    
    def __init__(
        self,
        model_repo: ModelRepository,
        provider_repo: ProviderRepository,
    ):
        """
        Initialize Service
        
        Args:
            model_repo: Model Repository
            provider_repo: Provider Repository
        """
        self.model_repo = model_repo
        self.provider_repo = provider_repo
    
    # ============ Model Mapping Operations ============
    
    async def create_mapping(self, data: ModelMappingCreate) -> ModelMappingResponse:
        """
        Create Model Mapping
        
        Args:
            data: Creation data
        
        Returns:
            ModelMappingResponse: Created model mapping
        
        Raises:
            ConflictError: Model already exists
        """
        # Check if model already exists
        existing = await self.model_repo.get_mapping(data.requested_model)
        if existing:
            raise ConflictError(
                message=f"Model '{data.requested_model}' already exists",
                code="duplicate_model",
            )
        
        mapping = await self.model_repo.create_mapping(data)
        return await self._to_mapping_response(mapping)
    
    async def get_mapping(self, requested_model: str) -> ModelMappingResponse:
        """
        Get Model Mapping details (including provider configuration)
        
        Args:
            requested_model: Requested model name
        
        Returns:
            ModelMappingResponse: Model mapping details
        
        Raises:
            NotFoundError: Model not found
        """
        mapping = await self.model_repo.get_mapping(requested_model)
        if not mapping:
            raise NotFoundError(
                message=f"Model '{requested_model}' not found",
                code="model_not_found",
            )
        
        return await self._to_mapping_response(mapping, include_providers=True)
    
    async def get_all_mappings(
        self,
        is_active: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
        requested_model: Optional[str] = None,
        model_type: Optional[str] = None,
        strategy: Optional[str] = None,
    ) -> tuple[list[ModelMappingResponse], int]:
        """
        Get Model Mapping List
        
        Args:
            is_active: Filter by active status
            page: Page number
            page_size: Items per page
            requested_model: Filter by model name (fuzzy)
            model_type: Filter by model type
            strategy: Filter by strategy
        
        Returns:
            tuple[list[ModelMappingResponse], int]: (Model mapping list, Total count)
        """
        mappings, total = await self.model_repo.get_all_mappings(
            is_active=is_active, 
            page=page, 
            page_size=page_size,
            requested_model=requested_model,
            model_type=model_type,
            strategy=strategy
        )
        
        responses = []
        for mapping in mappings:
            responses.append(await self._to_mapping_response(mapping))
        
        return responses, total
    
    async def update_mapping(
        self, requested_model: str, data: ModelMappingUpdate
    ) -> ModelMappingResponse:
        """
        Update Model Mapping
        
        Args:
            requested_model: Requested model name
            data: Update data
        
        Returns:
            ModelMappingResponse: Updated model mapping
        
        Raises:
            NotFoundError: Model not found
        """
        existing = await self.model_repo.get_mapping(requested_model)
        if not existing:
            raise NotFoundError(
                message=f"Model '{requested_model}' not found",
                code="model_not_found",
            )
        
        mapping = await self.model_repo.update_mapping(requested_model, data)
        return await self._to_mapping_response(mapping)  # type: ignore
    
    async def delete_mapping(self, requested_model: str) -> None:
        """
        Delete Model Mapping
        
        Args:
            requested_model: Requested model name
        
        Raises:
            NotFoundError: Model not found
        """
        existing = await self.model_repo.get_mapping(requested_model)
        if not existing:
            raise NotFoundError(
                message=f"Model '{requested_model}' not found",
                code="model_not_found",
            )
        
        await self.model_repo.delete_mapping(requested_model)
    
    # ============ Model-Provider Mapping Operations ============
    
    async def create_provider_mapping(
        self, data: ModelMappingProviderCreate
    ) -> ModelMappingProviderResponse:
        """
        Create Model-Provider Mapping
        
        Args:
            data: Creation data
        
        Returns:
            ModelMappingProviderResponse: Created mapping
        
        Raises:
            NotFoundError: Model or provider not found
            ConflictError: Mapping already exists
        """
        # Check if model exists
        model = await self.model_repo.get_mapping(data.requested_model)
        if not model:
            raise NotFoundError(
                message=f"Model '{data.requested_model}' not found",
                code="model_not_found",
            )
        
        # Check if provider exists
        provider = await self.provider_repo.get_by_id(data.provider_id)
        if not provider:
            raise NotFoundError(
                message=f"Provider with id {data.provider_id} not found",
                code="provider_not_found",
            )
        
        # Check if mapping already exists
        existing = await self.model_repo.get_all_provider_mappings(
            requested_model=data.requested_model,
            provider_id=data.provider_id,
        )
        if existing:
            raise ConflictError(
                message=f"Mapping for model '{data.requested_model}' and provider {data.provider_id} already exists",
                code="duplicate_mapping",
            )
        
        return await self.model_repo.add_provider_mapping(data)
    
    async def get_provider_mappings(
        self,
        requested_model: Optional[str] = None,
        provider_id: Optional[int] = None,
        is_active: Optional[bool] = None,
    ) -> list[ModelMappingProviderResponse]:
        """
        Get Model-Provider Mapping List
        
        Args:
            requested_model: Filter by model
            provider_id: Filter by provider
            is_active: Filter by active status
        
        Returns:
            list[ModelMappingProviderResponse]: Mapping list
        """
        return await self.model_repo.get_all_provider_mappings(
            requested_model=requested_model,
            provider_id=provider_id,
            is_active=is_active,
        )
    
    async def update_provider_mapping(
        self, id: int, data: ModelMappingProviderUpdate
    ) -> ModelMappingProviderResponse:
        """
        Update Model-Provider Mapping
        
        Args:
            id: Mapping ID
            data: Update data
        
        Returns:
            ModelMappingProviderResponse: Updated mapping
        
        Raises:
            NotFoundError: Mapping not found
        """
        existing = await self.model_repo.get_provider_mapping(id)
        if not existing:
            raise NotFoundError(
                message=f"Model-provider mapping with id {id} not found",
                code="mapping_not_found",
            )

        # Validate merged billing config to avoid persisting invalid combinations.
        from app.domain.model import ModelMappingProviderCreate

        update_data = data.model_dump(exclude_unset=True)
        merged = {
            "requested_model": existing.requested_model,
            "provider_id": existing.provider_id,
            "target_model_name": existing.target_model_name,
            "provider_rules": existing.provider_rules,
            "priority": existing.priority,
            "weight": existing.weight,
            "is_active": existing.is_active,
            "input_price": existing.input_price,
            "output_price": existing.output_price,
            "billing_mode": existing.billing_mode or "token_flat",
            "per_request_price": existing.per_request_price,
            "tiered_pricing": existing.tiered_pricing,
        }
        merged.update(update_data)
        ModelMappingProviderCreate(**merged)
        
        result = await self.model_repo.update_provider_mapping(id, data)
        return result  # type: ignore
    
    async def delete_provider_mapping(self, id: int) -> None:
        """
        Delete Model-Provider Mapping
        
        Args:
            id: Mapping ID
        
        Raises:
            NotFoundError: Mapping not found
        """
        existing = await self.model_repo.get_provider_mapping(id)
        if not existing:
            raise NotFoundError(
                message=f"Model-provider mapping with id {id} not found",
                code="mapping_not_found",
            )
        
        await self.model_repo.delete_provider_mapping(id)

    async def export_data(self) -> list["ModelExport"]:
        """
        Export all models with their provider mappings
        
        Returns:
            list[ModelExport]: List of models
        """
        from app.domain.model import ModelExport, ModelProviderExport

        # Get all model mappings
        mappings, _ = await self.model_repo.get_all_mappings(page=1, page_size=10000)
        
        export_list = []
        for m in mappings:
            # Get provider mappings for this model
            provider_mappings = await self.model_repo.get_provider_mappings(
                requested_model=m.requested_model
            )
            
            providers_export = []
            for pm in provider_mappings:
                providers_export.append(
                    ModelProviderExport(
                        provider_name=pm.provider_name,
                        target_model_name=pm.target_model_name,
                        provider_rules=pm.provider_rules,
                        input_price=pm.input_price,
                        output_price=pm.output_price,
                        billing_mode=pm.billing_mode,
                        per_request_price=pm.per_request_price,
                        tiered_pricing=pm.tiered_pricing,
                        priority=pm.priority,
                        weight=pm.weight,
                        is_active=pm.is_active
                    )
                )
            
            export_list.append(
                ModelExport(
                    requested_model=m.requested_model,
                    strategy=m.strategy,
                    model_type=m.model_type,
                    capabilities=m.capabilities,
                    is_active=m.is_active,
                    input_price=m.input_price,
                    output_price=m.output_price,
                    providers=providers_export
                )
            )
            
        return export_list

    async def import_data(self, data: list["ModelExport"]) -> dict:
        """
        Import models
        
        Args:
            data: List of models to import
            
        Returns:
            dict: Import summary
        """
        success = 0
        skipped = 0
        errors = []
        
        for item in data:
            # Check if model already exists
            existing = await self.model_repo.get_mapping(item.requested_model)
            if existing:
                skipped += 1
                continue
            
            # Create model mapping
            try:
                await self.model_repo.create_mapping(item)
                
                # Create provider mappings
                for p_item in item.providers:
                    provider = await self.provider_repo.get_by_name(p_item.provider_name)
                    if not provider:
                        errors.append(
                            f"Model '{item.requested_model}': Provider '{p_item.provider_name}' not found. Mapping skipped."
                        )
                        continue
                    
                    from app.domain.model import ModelMappingProviderCreate
                    billing_mode = p_item.billing_mode or "token_flat"
                    input_price = p_item.input_price
                    output_price = p_item.output_price
                    if billing_mode == "token_flat":
                        # Backward-compatible import: old exports may omit token prices.
                        if input_price is None:
                            input_price = item.input_price if item.input_price is not None else 0.0
                        if output_price is None:
                            output_price = item.output_price if item.output_price is not None else 0.0

                    await self.model_repo.add_provider_mapping(
                        ModelMappingProviderCreate(
                            requested_model=item.requested_model,
                            provider_id=provider.id,
                            target_model_name=p_item.target_model_name,
                            provider_rules=p_item.provider_rules,
                            input_price=input_price,
                            output_price=output_price,
                            billing_mode=billing_mode,
                            per_request_price=p_item.per_request_price,
                            tiered_pricing=p_item.tiered_pricing,
                            priority=p_item.priority,
                            weight=p_item.weight,
                            is_active=p_item.is_active
                        )
                    )
                
                success += 1
            except Exception as e:
                errors.append(f"Model '{item.requested_model}': {str(e)}")
        
        return {"success": success, "skipped": skipped, "errors": errors}
    
    async def _to_mapping_response(
        self, mapping: ModelMapping, include_providers: bool = False
    ) -> ModelMappingResponse:
        """
        Convert ModelMapping to Response Model
        
        Args:
            mapping: Model mapping
            include_providers: Whether to include provider list
        
        Returns:
            ModelMappingResponse: Response model
        """
        provider_count = await self.model_repo.get_provider_count(
            mapping.requested_model
        )
        
        providers = None
        if include_providers:
            providers = await self.model_repo.get_provider_mappings(
                requested_model=mapping.requested_model
            )
        
        return ModelMappingResponse(
            requested_model=mapping.requested_model,
            strategy=mapping.strategy,
            model_type=mapping.model_type,
            capabilities=mapping.capabilities,
            is_active=mapping.is_active,
            input_price=mapping.input_price,
            output_price=mapping.output_price,
            created_at=mapping.created_at,
            updated_at=mapping.updated_at,
            provider_count=provider_count,
            providers=providers,
        )
