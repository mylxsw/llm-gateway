"""
Tests for inherit_model_default validation in domain models.

- Provider-level DTOs should accept inherit_model_default without pricing fields.
- Model-level DTO should reject inherit_model_default.
"""

import pytest
from pydantic import ValidationError

from app.domain.model import (
    ModelMappingCreate,
    ModelMappingProviderCreate,
    ModelProviderBulkUpgradeRequest,
)


class TestProviderCreateAcceptsInherit:
    """ModelMappingProviderCreate accepts inherit_model_default."""

    def test_provider_create_accepts_inherit(self):
        data = ModelMappingProviderCreate(
            requested_model="test-model",
            provider_id=1,
            target_model_name="gpt-4",
            billing_mode="inherit_model_default",
        )
        assert data.billing_mode == "inherit_model_default"

    def test_provider_create_inherit_no_prices_needed(self):
        """Should succeed without any pricing fields."""
        data = ModelMappingProviderCreate(
            requested_model="test-model",
            provider_id=1,
            target_model_name="gpt-4",
            billing_mode="inherit_model_default",
            input_price=None,
            output_price=None,
            per_request_price=None,
            per_image_price=None,
            tiered_pricing=None,
        )
        assert data.billing_mode == "inherit_model_default"
        assert data.input_price is None
        assert data.output_price is None


class TestBulkUpgradeAcceptsInherit:
    """ModelProviderBulkUpgradeRequest accepts inherit_model_default."""

    def test_bulk_upgrade_accepts_inherit(self):
        data = ModelProviderBulkUpgradeRequest(
            provider_id=1,
            current_target_model_name="gpt-4",
            new_target_model_name="gpt-4-turbo",
            billing_mode="inherit_model_default",
        )
        assert data.billing_mode == "inherit_model_default"


class TestModelCreateRejectsInherit:
    """ModelMappingCreate should NOT accept inherit_model_default."""

    def test_model_create_rejects_inherit(self):
        with pytest.raises(ValidationError, match="inherit_model_default"):
            ModelMappingCreate(
                requested_model="test-model",
                billing_mode="inherit_model_default",
            )
