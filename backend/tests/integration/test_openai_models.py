import pytest
from httpx import AsyncClient, ASGITransport
from datetime import datetime
from app.main import app
from app.api.deps import get_db, get_current_api_key
from app.domain.model import ModelMappingCreate
from app.repositories.sqlalchemy.model_repo import SQLAlchemyModelRepository
from app.domain.api_key import ApiKeyModel

@pytest.mark.asyncio
async def test_list_models(db_session):
    # Override get_db to use the test session
    app.dependency_overrides[get_db] = lambda: db_session

    # Mock CurrentApiKey
    mock_api_key = ApiKeyModel(
        id=1,
        key_name="test-key",
        key_value="sk-test...",
        is_active=True,
        created_at=datetime.utcnow(),
        last_used_at=None
    )
    app.dependency_overrides[get_current_api_key] = lambda: mock_api_key

    # Create a test model mapping
    model_repo = SQLAlchemyModelRepository(db_session)
    await model_repo.create_mapping(ModelMappingCreate(
        requested_model="gpt-4-test",
        strategy="round_robin",
        is_active=True
    ))

    # Call the API
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/v1/models")
    
    # Assertions
    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "list"
    assert len(data["data"]) >= 1
    
    # Verify the created model is present
    found = False
    for item in data["data"]:
        if item["id"] == "gpt-4-test":
            found = True
            assert item["object"] == "model"
            assert item["owned_by"] == "system"
            break
    assert found

    # Clean up overrides
    app.dependency_overrides = {}