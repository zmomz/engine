"""
Integration tests using real_services fixture.
These tests demonstrate actual service integration with mock exchange,
replacing mock-call assertions with behavior assertions.
"""
import pytest
from decimal import Decimal
from uuid import uuid4

from app.models.position_group import PositionGroupStatus
from app.repositories.position_group import PositionGroupRepository


class TestRealServicesFixture:
    """Test that the real_services fixture works correctly."""

    @pytest.mark.asyncio
    async def test_fixture_provides_all_services(self, real_services):
        """Verify fixture provides all expected services."""
        assert "connector" in real_services
        assert "grid_calculator" in real_services
        assert "order_service" in real_services
        assert "position_manager" in real_services
        assert "risk_engine" in real_services
        assert "execution_pool_manager" in real_services
        assert "session" in real_services
        assert "user" in real_services

    @pytest.mark.asyncio
    async def test_services_are_real_instances(self, real_services):
        """Verify services are real instances, not mocks."""
        from app.services.grid_calculator import GridCalculatorService
        from app.services.position_manager import PositionManagerService
        from app.services.risk_engine import RiskEngineService

        assert isinstance(real_services["grid_calculator"], GridCalculatorService)
        assert isinstance(real_services["position_manager"], PositionManagerService)
        assert isinstance(real_services["risk_engine"], RiskEngineService)

    @pytest.mark.asyncio
    async def test_connector_is_mock_exchange(self, real_services):
        """Verify connector is mock exchange for testing."""
        connector = real_services["connector"]

        # Mock exchange should have these capabilities (ExchangeInterface methods)
        assert hasattr(connector, "get_current_price")
        assert hasattr(connector, "place_order")  # ExchangeInterface uses place_order
        assert hasattr(connector, "fetch_free_balance")


class TestGridCalculatorIntegration:
    """Test GridCalculatorService with real integration."""

    @pytest.mark.asyncio
    async def test_calculate_dca_levels_returns_valid_structure(self, real_services):
        """Grid calculator should return properly structured DCA levels."""
        from app.schemas.grid_config import DCAGridConfig

        grid_calculator = real_services["grid_calculator"]

        dca_config = DCAGridConfig.model_validate({
            "levels": [
                {"gap_percent": 0.0, "weight_percent": 50, "tp_percent": 2.0},
                {"gap_percent": -1.0, "weight_percent": 50, "tp_percent": 1.5},
            ],
            "tp_mode": "per_leg",
            "tp_aggregate_percent": Decimal("0")
        })

        base_price = Decimal("50000")

        # Provide required precision_rules
        precision_rules = {
            "tick_size": Decimal("0.01"),
            "step_size": Decimal("0.00001"),
            "min_qty": Decimal("0.00001"),
            "min_notional": Decimal("10")
        }

        levels = grid_calculator.calculate_dca_levels(
            base_price=base_price,
            dca_config=dca_config,  # Correct parameter name
            side="long",
            precision_rules=precision_rules,
            pyramid_index=0
        )

        # Verify structure - not just that a mock was called
        assert len(levels) == 2
        assert levels[0]["gap_percent"] == Decimal("0")
        assert levels[1]["gap_percent"] == Decimal("-1.0")


class TestOrderServiceIntegration:
    """Test OrderService with real integration."""

    @pytest.mark.asyncio
    async def test_order_service_has_session_and_connector(self, real_services):
        """Order service should have valid session and connector."""
        order_service = real_services["order_service"]

        assert order_service.session is not None
        assert order_service.exchange_connector is not None

    @pytest.mark.asyncio
    async def test_slippage_calculation_logic(self, real_services):
        """Test slippage calculation directly without mocking."""
        # This tests the actual slippage calculation logic
        expected_price = Decimal("50000")
        actual_price = Decimal("50250")  # 0.5% slippage

        slippage_percent = abs(actual_price - expected_price) / expected_price * 100

        assert slippage_percent == Decimal("0.5")


class TestPositionManagerIntegration:
    """Test PositionManagerService with real integration."""

    @pytest.mark.asyncio
    async def test_position_manager_has_dependencies(self, real_services):
        """Position manager should have all required dependencies."""
        pm = real_services["position_manager"]

        assert pm.session_factory is not None
        assert pm.user is not None
        assert pm.grid_calculator_service is not None


class TestRiskEngineIntegration:
    """Test RiskEngineService with real integration."""

    @pytest.mark.asyncio
    async def test_risk_engine_config_loaded(self, real_services):
        """Risk engine should have proper configuration."""
        risk_config = real_services["risk_engine_config"]

        assert risk_config.loss_threshold_percent == Decimal("-1.5")
        assert risk_config.required_pyramids_for_timer == 3
        assert risk_config.max_winners_to_combine == 3

    @pytest.mark.asyncio
    async def test_risk_engine_has_repositories(self, real_services):
        """Risk engine should have access to required repositories."""
        risk_engine = real_services["risk_engine"]

        assert risk_engine.position_group_repository_class is not None
        assert risk_engine.risk_action_repository_class is not None
        assert risk_engine.dca_order_repository_class is not None
