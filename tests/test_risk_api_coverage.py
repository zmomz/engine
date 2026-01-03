"""
Additional tests for api/risk.py to improve coverage.
Focuses on create_risk_engine_service edge cases, force_stop/start, sync_exchange,
and HTTP exception handling.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient
from fastapi import HTTPException
import uuid
from decimal import Decimal
from datetime import datetime

from app.main import app
from app.models.position_group import PositionGroup, PositionGroupStatus
from app.schemas.position_group import TPMode
from app.api.risk import get_risk_engine_service, create_risk_engine_service
from app.models.user import User


class TestCreateRiskEngineService:
    """Tests for create_risk_engine_service function."""

    @pytest.mark.asyncio
    async def test_raises_error_on_encryption_service_failure(self):
        """Test HTTPException is raised when EncryptionService fails."""
        mock_session = AsyncMock()
        mock_user = MagicMock()
        mock_user.encrypted_api_keys = {"binance": {"api_key": "test"}}

        with patch("app.api.risk.EncryptionService", side_effect=ValueError("Key error")):
            with pytest.raises(HTTPException) as exc_info:
                create_risk_engine_service(mock_session, mock_user)

            assert exc_info.value.status_code == 500
            assert "Encryption service" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_raises_error_on_missing_api_keys(self):
        """Test HTTPException is raised when API keys are missing."""
        mock_session = AsyncMock()
        mock_user = MagicMock()
        mock_user.encrypted_api_keys = None

        with patch("app.api.risk.EncryptionService"):
            with pytest.raises(HTTPException) as exc_info:
                create_risk_engine_service(mock_session, mock_user)

            assert exc_info.value.status_code == 400
            assert "API keys are missing" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_raises_error_on_invalid_api_keys_format(self):
        """Test HTTPException is raised when API keys format is invalid."""
        mock_session = AsyncMock()
        mock_user = MagicMock()
        mock_user.encrypted_api_keys = "not_a_dict"  # Invalid format

        with patch("app.api.risk.EncryptionService"):
            with pytest.raises(HTTPException) as exc_info:
                create_risk_engine_service(mock_session, mock_user)

            assert exc_info.value.status_code == 400
            assert "Invalid API keys format" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_uses_default_risk_config_on_validation_failure(self):
        """Test default RiskEngineConfig is used when validation fails."""
        mock_session = AsyncMock()
        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.encrypted_api_keys = {"binance": {"api_key": "test"}}
        mock_user.risk_config = {"invalid_field": "bad_value"}  # Invalid config

        with patch("app.api.risk.EncryptionService"):
            with patch("app.api.risk.RiskEngineService") as mock_service_cls:
                mock_service_cls.return_value = MagicMock()

                service = create_risk_engine_service(mock_session, mock_user)

                # Should have called with default config
                call_kwargs = mock_service_cls.call_args[1]
                assert call_kwargs["risk_engine_config"] is not None

    @pytest.mark.asyncio
    async def test_successful_service_creation(self):
        """Test successful risk engine service creation."""
        mock_session = AsyncMock()
        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.encrypted_api_keys = {"binance": {"api_key": "test"}}
        mock_user.risk_config = {}

        with patch("app.api.risk.EncryptionService"):
            with patch("app.api.risk.RiskEngineService") as mock_service_cls:
                mock_service = MagicMock()
                mock_service_cls.return_value = mock_service

                result = create_risk_engine_service(mock_session, mock_user)

                assert result == mock_service
                mock_service_cls.assert_called_once()


class TestGetRiskEngineStatus:
    """Tests for get_risk_engine_status endpoint."""

    @pytest.mark.asyncio
    async def test_returns_not_configured_status(self, authorized_client, test_user, db_session):
        """Test status endpoint returns not_configured when keys missing."""
        test_user.encrypted_api_keys = None
        db_session.add(test_user)
        await db_session.commit()

        response = await authorized_client.get("/api/v1/risk/status")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "not_configured"
        assert data["active_positions"] == 0

    @pytest.mark.asyncio
    async def test_returns_error_status_on_http_exception(self, authorized_client, test_user, db_session):
        """Test status endpoint handles HTTPException from service creation."""
        test_user.encrypted_api_keys = {"binance": {"api_key": "test"}}
        db_session.add(test_user)
        await db_session.commit()

        with patch("app.api.risk.create_risk_engine_service") as mock_create:
            mock_create.side_effect = HTTPException(status_code=400, detail="Bad config")

            response = await authorized_client.get("/api/v1/risk/status")

            assert response.status_code == 200  # Should not crash
            data = response.json()
            assert data["status"] == "error"
            assert "Bad config" in data["message"]

    @pytest.mark.asyncio
    async def test_returns_success_status(self, authorized_client, test_user, db_session):
        """Test status endpoint returns success status."""
        test_user.encrypted_api_keys = {"binance": {"api_key": "test"}}
        db_session.add(test_user)
        await db_session.commit()

        mock_service = AsyncMock()
        mock_service.get_current_status.return_value = {
            "status": "running",
            "active_positions": 5,
            "risk_level": "moderate"
        }

        with patch("app.api.risk.create_risk_engine_service", return_value=mock_service):
            response = await authorized_client.get("/api/v1/risk/status")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "running"
            assert data["active_positions"] == 5


class TestRunRiskEvaluation:
    """Tests for run_risk_evaluation endpoint."""

    @pytest.mark.asyncio
    async def test_run_evaluation_error_handling(self, authorized_client):
        """Test run_evaluation returns 500 on exception."""
        mock_service = AsyncMock()
        mock_service.run_single_evaluation.side_effect = Exception("Evaluation failed")

        app.dependency_overrides[get_risk_engine_service] = lambda: mock_service

        try:
            response = await authorized_client.post("/api/v1/risk/run-evaluation")

            assert response.status_code == 500
            assert "Failed to run risk evaluation" in response.json()["detail"]
        finally:
            del app.dependency_overrides[get_risk_engine_service]


class TestBlockUnblockSkipHTTPExceptions:
    """Tests for HTTP exception re-raising in block/unblock/skip endpoints."""

    @pytest.mark.asyncio
    async def test_block_reraises_http_exception(self, authorized_client):
        """Test block endpoint re-raises HTTPException."""
        mock_service = AsyncMock()
        mock_service.set_risk_blocked.side_effect = HTTPException(
            status_code=404, detail="Position not found"
        )

        app.dependency_overrides[get_risk_engine_service] = lambda: mock_service

        try:
            group_id = uuid.uuid4()
            response = await authorized_client.post(f"/api/v1/risk/{group_id}/block")

            assert response.status_code == 404
            assert "Position not found" in response.json()["detail"]
        finally:
            del app.dependency_overrides[get_risk_engine_service]

    @pytest.mark.asyncio
    async def test_unblock_reraises_http_exception(self, authorized_client):
        """Test unblock endpoint re-raises HTTPException."""
        mock_service = AsyncMock()
        mock_service.set_risk_blocked.side_effect = HTTPException(
            status_code=404, detail="Position not found"
        )

        app.dependency_overrides[get_risk_engine_service] = lambda: mock_service

        try:
            group_id = uuid.uuid4()
            response = await authorized_client.post(f"/api/v1/risk/{group_id}/unblock")

            assert response.status_code == 404
            assert "Position not found" in response.json()["detail"]
        finally:
            del app.dependency_overrides[get_risk_engine_service]

    @pytest.mark.asyncio
    async def test_skip_reraises_http_exception(self, authorized_client):
        """Test skip endpoint re-raises HTTPException."""
        mock_service = AsyncMock()
        mock_service.set_risk_skip_once.side_effect = HTTPException(
            status_code=404, detail="Position not found"
        )

        app.dependency_overrides[get_risk_engine_service] = lambda: mock_service

        try:
            group_id = uuid.uuid4()
            response = await authorized_client.post(f"/api/v1/risk/{group_id}/skip")

            assert response.status_code == 404
            assert "Position not found" in response.json()["detail"]
        finally:
            del app.dependency_overrides[get_risk_engine_service]


class TestForceStopEngine:
    """Tests for force_stop_engine endpoint."""

    @pytest.mark.asyncio
    async def test_force_stop_success(self, authorized_client, test_user, db_session):
        """Test successful force stop of engine."""
        test_user.encrypted_api_keys = {"binance": {"api_key": "test"}}
        db_session.add(test_user)
        await db_session.commit()

        mock_service = AsyncMock()
        mock_service.force_stop_engine.return_value = {
            "status": "stopped",
            "message": "Engine stopped successfully"
        }

        with patch("app.api.risk.create_risk_engine_service", return_value=mock_service):
            response = await authorized_client.post("/api/v1/risk/force-stop")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "stopped"
            mock_service.force_stop_engine.assert_called_once()

    @pytest.mark.asyncio
    async def test_force_stop_error(self, authorized_client, test_user, db_session):
        """Test force stop error handling."""
        test_user.encrypted_api_keys = {"binance": {"api_key": "test"}}
        db_session.add(test_user)
        await db_session.commit()

        mock_service = AsyncMock()
        mock_service.force_stop_engine.side_effect = Exception("Stop failed")

        with patch("app.api.risk.create_risk_engine_service", return_value=mock_service):
            response = await authorized_client.post("/api/v1/risk/force-stop")

            assert response.status_code == 500
            assert "Failed to stop" in response.json()["detail"]


class TestForceStartEngine:
    """Tests for force_start_engine endpoint."""

    @pytest.mark.asyncio
    async def test_force_start_success(self, authorized_client, test_user, db_session):
        """Test successful force start of engine."""
        test_user.encrypted_api_keys = {"binance": {"api_key": "test"}}
        db_session.add(test_user)
        await db_session.commit()

        mock_service = AsyncMock()
        mock_service.force_start_engine.return_value = {
            "status": "running",
            "message": "Engine started successfully"
        }

        with patch("app.api.risk.create_risk_engine_service", return_value=mock_service):
            response = await authorized_client.post("/api/v1/risk/force-start")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "running"
            mock_service.force_start_engine.assert_called_once()

    @pytest.mark.asyncio
    async def test_force_start_error(self, authorized_client, test_user, db_session):
        """Test force start error handling."""
        test_user.encrypted_api_keys = {"binance": {"api_key": "test"}}
        db_session.add(test_user)
        await db_session.commit()

        mock_service = AsyncMock()
        mock_service.force_start_engine.side_effect = Exception("Start failed")

        with patch("app.api.risk.create_risk_engine_service", return_value=mock_service):
            response = await authorized_client.post("/api/v1/risk/force-start")

            assert response.status_code == 500
            assert "Failed to start" in response.json()["detail"]


class TestSyncWithExchange:
    """Tests for sync_with_exchange endpoint."""

    @pytest.mark.asyncio
    async def test_sync_exchange_success(self, authorized_client, test_user, db_session):
        """Test successful exchange sync."""
        test_user.encrypted_api_keys = {"binance": {"api_key": "test"}}
        db_session.add(test_user)
        await db_session.commit()

        mock_service = AsyncMock()
        mock_service.sync_with_exchange.return_value = {
            "synced_positions": 3,
            "updated_pnl": True,
            "closed_externally": 0
        }

        with patch("app.api.risk.create_risk_engine_service", return_value=mock_service):
            response = await authorized_client.post("/api/v1/risk/sync-exchange")

            assert response.status_code == 200
            data = response.json()
            assert data["synced_positions"] == 3
            mock_service.sync_with_exchange.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_exchange_error(self, authorized_client, test_user, db_session):
        """Test exchange sync error handling."""
        test_user.encrypted_api_keys = {"binance": {"api_key": "test"}}
        db_session.add(test_user)
        await db_session.commit()

        mock_service = AsyncMock()
        mock_service.sync_with_exchange.side_effect = Exception("Sync failed")

        with patch("app.api.risk.create_risk_engine_service", return_value=mock_service):
            response = await authorized_client.post("/api/v1/risk/sync-exchange")

            assert response.status_code == 500
            assert "Failed to synchronize" in response.json()["detail"]


class TestGetRiskEngineServiceDependency:
    """Tests for get_risk_engine_service dependency function."""

    @pytest.mark.asyncio
    async def test_dependency_creates_service(self):
        """Test that dependency creates risk engine service correctly."""
        mock_request = MagicMock()
        mock_session = AsyncMock()
        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.encrypted_api_keys = {"binance": {"api_key": "test"}}
        mock_user.risk_config = {}

        with patch("app.api.risk.create_risk_engine_service") as mock_create:
            mock_service = MagicMock()
            mock_create.return_value = mock_service

            from app.api.risk import get_risk_engine_service as gres
            result = gres(mock_request, mock_session, mock_user)

            mock_create.assert_called_once_with(mock_session, mock_user)
            assert result == mock_service
