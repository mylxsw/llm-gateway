
import pytest
from datetime import datetime, timezone
from app.domain.log import RequestLogCreate, LogCostStatsQuery
from app.repositories.sqlalchemy.log_repo import SQLAlchemyLogRepository

@pytest.mark.asyncio
async def test_get_cost_stats_token_ranking(db_session):
    repo = SQLAlchemyLogRepository(db_session)
    now = datetime.now(timezone.utc)

    # 1. Insert Log 1: Model A (High Cost, Low Tokens)
    await repo.create(RequestLogCreate(
        request_time=now,
        requested_model="model-A",
        target_model="target-A",
        total_cost=10.0,
        input_cost=5.0,
        output_cost=5.0,
        input_tokens=5,
        output_tokens=5,  # Total 10 tokens
        response_status=200,
        api_key_id=1,
        provider_id=1,
        is_stream=False
    ))

    # 2. Insert Log 2: Model B (Low Cost, High Tokens)
    await repo.create(RequestLogCreate(
        request_time=now,
        requested_model="model-B",
        target_model="target-B",
        total_cost=1.0,
        input_cost=0.5,
        output_cost=0.5,
        input_tokens=50,
        output_tokens=50, # Total 100 tokens
        response_status=200,
        api_key_id=1,
        provider_id=1,
        is_stream=False
    ))

    query = LogCostStatsQuery(
        start_time=datetime(2000, 1, 1, tzinfo=timezone.utc),
        group_by="request_model"
    )
    stats = await repo.get_cost_stats(query)

    # Verify by_model (Cost Ranking)
    # Model A (10.0) > Model B (1.0)
    assert len(stats.by_model) == 2
    assert stats.by_model[0].requested_model == "model-A"
    assert stats.by_model[0].total_cost == 10.0
    assert stats.by_model[1].requested_model == "model-B"
    assert stats.by_model[1].total_cost == 1.0

    # Verify by_model_tokens (Token Ranking)
    # Model B (100 tokens) > Model A (10 tokens)
    assert len(stats.by_model_tokens) == 2
    assert stats.by_model_tokens[0].requested_model == "model-B"
    assert stats.by_model_tokens[0].input_tokens == 50
    assert stats.by_model_tokens[0].output_tokens == 50
    assert stats.by_model_tokens[1].requested_model == "model-A"
    assert stats.by_model_tokens[1].input_tokens == 5
    assert stats.by_model_tokens[1].output_tokens == 5
