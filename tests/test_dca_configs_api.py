"""Tests for DCA Configurations API endpoints"""
import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, MagicMock, patch
from app.main import app
from app.db.database import get_db_session
from app.models.user import User
from app.models.dca_configuration import DCAConfiguration, EntryOrderType, TakeProfitMode
from app.api.dependencies.users import get_current_user
import uuid


@pytest.fixture
def mock_user():
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.username = "testuser"
    return user


@pytest.fixture
def sample_dca_config(mock_user):
    config = MagicMock(spec=DCAConfiguration)
    config.id = uuid.uuid4()
    config.user_id = mock_user.id
    config.pair = "BTC/USDT"
    config.timeframe = 15
    config.exchange = "binance"
    config.entry_order_type = EntryOrderType.LIMIT
    config.dca_levels = [
        {"gap_percent": 0.0, "weight_percent": 50, "tp_percent": 1.0},
        {"gap_percent": -1.0, "weight_percent": 50, "tp_percent": 0.5}
    ]
    config.pyramid_specific_levels = {}
    config.tp_mode = TakeProfitMode.PER_LEG
    config.tp_settings = {}
    config.max_pyramids = 5
    config.to_dict = MagicMock(return_value={
        "id": str(config.id),
        "user_id": str(config.user_id),
        "pair": config.pair,
        "timeframe": config.timeframe,
        "exchange": config.exchange,
        "entry_order_type": "limit",
        "dca_levels": config.dca_levels,
        "pyramid_specific_levels": config.pyramid_specific_levels,
        "tp_mode": "per_leg",
        "tp_settings": config.tp_settings,
        "max_pyramids": config.max_pyramids
    })
    return config


@pytest.fixture
def mock_db_session():
    session = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


class TestDCAConfigsAPI:
    """Tests for DCA Configs API endpoints"""

    @pytest.mark.asyncio
    async def test_get_my_dca_configs_empty(self, mock_user, mock_db_session):
        """Test getting configs when none exist"""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        with patch('app.api.dca_configs.DCAConfigurationRepository') as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_all_by_user = AsyncMock(return_value=[])

            async with AsyncClient(app=app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/dca-configs/")

            assert response.status_code == 200
            assert response.json() == []

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_my_dca_configs_with_data(self, mock_user, mock_db_session, sample_dca_config):
        """Test getting configs with existing data"""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        with patch('app.api.dca_configs.DCAConfigurationRepository') as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_all_by_user = AsyncMock(return_value=[sample_dca_config])

            async with AsyncClient(app=app, base_url="http://test") as ac:
                response = await ac.get("/api/v1/dca-configs/")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["pair"] == "BTC/USDT"

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_create_dca_config_success(self, mock_user, mock_db_session, sample_dca_config):
        """Test creating a new DCA config"""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        with patch('app.api.dca_configs.DCAConfigurationRepository') as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_specific_config = AsyncMock(return_value=None)  # No existing
            mock_repo.create = AsyncMock(return_value=sample_dca_config)

            async with AsyncClient(app=app, base_url="http://test") as ac:
                response = await ac.post(
                    "/api/v1/dca-configs/",
                    json={
                        "pair": "BTC/USDT",
                        "timeframe": 15,
                        "exchange": "binance",
                        "entry_order_type": "limit",
                        "dca_levels": [
                            {"gap_percent": 0.0, "weight_percent": 50, "tp_percent": 1.0},
                            {"gap_percent": -1.0, "weight_percent": 50, "tp_percent": 0.5}
                        ],
                        "tp_mode": "per_leg",
                        "tp_settings": {},
                        "max_pyramids": 5
                    }
                )

            assert response.status_code == 200
            data = response.json()
            assert data["pair"] == "BTC/USDT"

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_create_dca_config_duplicate(self, mock_user, mock_db_session, sample_dca_config):
        """Test creating a duplicate config fails"""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        with patch('app.api.dca_configs.DCAConfigurationRepository') as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_specific_config = AsyncMock(return_value=sample_dca_config)  # Already exists

            async with AsyncClient(app=app, base_url="http://test") as ac:
                response = await ac.post(
                    "/api/v1/dca-configs/",
                    json={
                        "pair": "BTC/USDT",
                        "timeframe": 15,
                        "exchange": "binance",
                        "entry_order_type": "limit",
                        "dca_levels": [
                            {"gap_percent": 0.0, "weight_percent": 100, "tp_percent": 1.0}
                        ],
                        "tp_mode": "per_leg",
                        "tp_settings": {},
                        "max_pyramids": 5
                    }
                )

            assert response.status_code == 400
            assert "already exists" in response.json()["detail"]

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_create_dca_config_with_pyramid_specific_levels(self, mock_user, mock_db_session, sample_dca_config):
        """Test creating config with pyramid-specific levels"""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        with patch('app.api.dca_configs.DCAConfigurationRepository') as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_specific_config = AsyncMock(return_value=None)
            mock_repo.create = AsyncMock(return_value=sample_dca_config)

            async with AsyncClient(app=app, base_url="http://test") as ac:
                response = await ac.post(
                    "/api/v1/dca-configs/",
                    json={
                        "pair": "ETH/USDT",
                        "timeframe": 60,
                        "exchange": "binance",
                        "entry_order_type": "market",
                        "dca_levels": [
                            {"gap_percent": 0.0, "weight_percent": 100, "tp_percent": 1.0}
                        ],
                        "pyramid_specific_levels": {
                            "1": [{"gap_percent": 0.0, "weight_percent": 50, "tp_percent": 0.5}]
                        },
                        "tp_mode": "aggregate",
                        "tp_settings": {"tp_aggregate_percent": 2.0},
                        "max_pyramids": 3
                    }
                )

            assert response.status_code == 200

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_update_dca_config_success(self, mock_user, mock_db_session, sample_dca_config):
        """Test updating an existing config"""
        sample_dca_config.user_id = mock_user.id

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        with patch('app.api.dca_configs.DCAConfigurationRepository') as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_by_id = AsyncMock(return_value=sample_dca_config)

            async with AsyncClient(app=app, base_url="http://test") as ac:
                response = await ac.put(
                    f"/api/v1/dca-configs/{sample_dca_config.id}",
                    json={
                        "max_pyramids": 10
                    }
                )

            assert response.status_code == 200

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_update_dca_config_not_found(self, mock_user, mock_db_session):
        """Test updating non-existent config"""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        with patch('app.api.dca_configs.DCAConfigurationRepository') as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_by_id = AsyncMock(return_value=None)

            async with AsyncClient(app=app, base_url="http://test") as ac:
                response = await ac.put(
                    f"/api/v1/dca-configs/{uuid.uuid4()}",
                    json={"max_pyramids": 10}
                )

            assert response.status_code == 404

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_update_dca_config_not_authorized(self, mock_user, mock_db_session, sample_dca_config):
        """Test updating config belonging to another user"""
        sample_dca_config.user_id = uuid.uuid4()  # Different user

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        with patch('app.api.dca_configs.DCAConfigurationRepository') as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_by_id = AsyncMock(return_value=sample_dca_config)

            async with AsyncClient(app=app, base_url="http://test") as ac:
                response = await ac.put(
                    f"/api/v1/dca-configs/{sample_dca_config.id}",
                    json={"max_pyramids": 10}
                )

            assert response.status_code == 403

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_update_dca_config_all_fields(self, mock_user, mock_db_session, sample_dca_config):
        """Test updating all fields of a config"""
        sample_dca_config.user_id = mock_user.id

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        with patch('app.api.dca_configs.DCAConfigurationRepository') as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_by_id = AsyncMock(return_value=sample_dca_config)

            async with AsyncClient(app=app, base_url="http://test") as ac:
                response = await ac.put(
                    f"/api/v1/dca-configs/{sample_dca_config.id}",
                    json={
                        "entry_order_type": "market",
                        "dca_levels": [
                            {"gap_percent": 0.0, "weight_percent": 100, "tp_percent": 2.0}
                        ],
                        "pyramid_specific_levels": {
                            "1": [{"gap_percent": -0.5, "weight_percent": 100, "tp_percent": 1.0}]
                        },
                        "tp_mode": "aggregate",
                        "tp_settings": {"tp_aggregate_percent": 3.0},
                        "max_pyramids": 7
                    }
                )

            assert response.status_code == 200

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_delete_dca_config_success(self, mock_user, mock_db_session, sample_dca_config):
        """Test deleting a config"""
        sample_dca_config.user_id = mock_user.id

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        with patch('app.api.dca_configs.DCAConfigurationRepository') as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_by_id = AsyncMock(return_value=sample_dca_config)
            mock_repo.delete = AsyncMock()

            async with AsyncClient(app=app, base_url="http://test") as ac:
                response = await ac.delete(f"/api/v1/dca-configs/{sample_dca_config.id}")

            assert response.status_code == 200
            assert response.json()["message"] == "Configuration deleted"

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_delete_dca_config_not_found(self, mock_user, mock_db_session):
        """Test deleting non-existent config"""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        with patch('app.api.dca_configs.DCAConfigurationRepository') as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_by_id = AsyncMock(return_value=None)

            async with AsyncClient(app=app, base_url="http://test") as ac:
                response = await ac.delete(f"/api/v1/dca-configs/{uuid.uuid4()}")

            assert response.status_code == 404

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_delete_dca_config_not_authorized(self, mock_user, mock_db_session, sample_dca_config):
        """Test deleting config belonging to another user"""
        sample_dca_config.user_id = uuid.uuid4()  # Different user

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        with patch('app.api.dca_configs.DCAConfigurationRepository') as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_by_id = AsyncMock(return_value=sample_dca_config)

            async with AsyncClient(app=app, base_url="http://test") as ac:
                response = await ac.delete(f"/api/v1/dca-configs/{sample_dca_config.id}")

            assert response.status_code == 403

        app.dependency_overrides.clear()
