import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.api.dependencies.users import get_current_active_user
from app.main import app
import uuid

@pytest.mark.asyncio
async def test_get_risk_engine_status_not_configured(authorized_client, test_user, db_session):
    # Setup user with NO keys
    test_user.encrypted_api_keys = {}
    db_session.add(test_user)
    await db_session.commit()

    response = await authorized_client.get("/api/v1/risk/status")
    
    assert response.status_code == 200
    assert response.json()["status"] == "not_configured"

@pytest.mark.asyncio
async def test_get_risk_engine_status_error_creation(authorized_client, test_user, db_session):
    # Setup user with keys
    test_user.encrypted_api_keys = {"binance": {"encrypted_data": "..."}}
    test_user.exchange = "binance"
    db_session.add(test_user)
    await db_session.commit()

    # Mock create_risk_engine_service to raise HTTPException
    # Since it's imported inside the route logic? No, it's defined in the module.
    # We patch it where it is used.
    with patch("app.api.risk.create_risk_engine_service", side_effect=Exception("Setup Failed")):
        response = await authorized_client.get("/api/v1/risk/status")
        
        assert response.status_code == 200
        assert response.json()["status"] == "error"
        assert "Setup Failed" in response.json()["message"]

@pytest.mark.asyncio
async def test_run_risk_evaluation_success(authorized_client):
    mock_service = AsyncMock()
    mock_service.run_single_evaluation.return_value = {"processed": 1}

    async def mock_get_service():
        return mock_service

    app.dependency_overrides["get_risk_engine_service"] = mock_get_service
    # Need to find the exact import path for the dependency override
    # In app.api.risk, it is defined as get_risk_engine_service.
    # FastAPI resolves dependencies by function identity.
    from app.api.risk import get_risk_engine_service
    app.dependency_overrides[get_risk_engine_service] = mock_get_service

    try:
        response = await authorized_client.post("/api/v1/risk/run-evaluation")
        assert response.status_code == 200
        assert response.json()["result"] == {"processed": 1}
    finally:
        del app.dependency_overrides[get_risk_engine_service]

@pytest.mark.asyncio
async def test_block_risk_for_group_error(authorized_client):
    mock_service = AsyncMock()
    mock_service.set_risk_blocked.side_effect = Exception("DB Error")

    async def mock_get_service():
        return mock_service

    from app.api.risk import get_risk_engine_service
    app.dependency_overrides[get_risk_engine_service] = mock_get_service

    try:
        group_id = uuid.uuid4()
        response = await authorized_client.post(f"/api/v1/risk/{group_id}/block")
        assert response.status_code == 500
        assert "DB Error" in response.json()["detail"]
    finally:
        del app.dependency_overrides[get_risk_engine_service]

@pytest.mark.asyncio
async def test_unblock_risk_for_group_error(authorized_client):
    mock_service = AsyncMock()
    mock_service.set_risk_blocked.side_effect = Exception("DB Error")

    async def mock_get_service():
        return mock_service

    from app.api.risk import get_risk_engine_service
    app.dependency_overrides[get_risk_engine_service] = mock_get_service

    try:
        group_id = uuid.uuid4()
        response = await authorized_client.post(f"/api/v1/risk/{group_id}/unblock")
        assert response.status_code == 500
    finally:
        del app.dependency_overrides[get_risk_engine_service]

@pytest.mark.asyncio
async def test_skip_risk_for_group_error(authorized_client):
    mock_service = AsyncMock()
    mock_service.set_risk_skip_once.side_effect = Exception("DB Error")

    async def mock_get_service():
        return mock_service

    from app.api.risk import get_risk_engine_service
    app.dependency_overrides[get_risk_engine_service] = mock_get_service

    try:
        group_id = uuid.uuid4()
        response = await authorized_client.post(f"/api/v1/risk/{group_id}/skip")
        assert response.status_code == 500
    finally:
        del app.dependency_overrides[get_risk_engine_service]
