"""
Demo Runner - Orchestrates scenario execution.

Provides scenario discovery, filtering, and execution with
proper setup/teardown and result aggregation.
"""

import asyncio
import importlib
import pkgutil
from typing import Dict, List, Optional, Type

from .clients import EngineClient, MockExchangeClient
from .presenters import ConsolePresenter
from .scenarios.base import BaseScenario, DemoConfig, ScenarioResult, ScenarioStatus


class ScenarioRegistry:
    """Registry of all available scenarios."""

    _scenarios: Dict[str, Type[BaseScenario]] = {}
    _by_category: Dict[str, List[Type[BaseScenario]]] = {}

    @classmethod
    def register(cls, scenario_class: Type[BaseScenario]):
        """Register a scenario class."""
        scenario_id = scenario_class.id
        category = scenario_class.category

        cls._scenarios[scenario_id] = scenario_class

        if category not in cls._by_category:
            cls._by_category[category] = []
        cls._by_category[category].append(scenario_class)

    @classmethod
    def get(cls, scenario_id: str) -> Optional[Type[BaseScenario]]:
        """Get scenario class by ID."""
        return cls._scenarios.get(scenario_id)

    @classmethod
    def get_by_category(cls, category: str) -> List[Type[BaseScenario]]:
        """Get all scenarios in a category."""
        return cls._by_category.get(category, [])

    @classmethod
    def get_all(cls) -> List[Type[BaseScenario]]:
        """Get all registered scenarios."""
        return list(cls._scenarios.values())

    @classmethod
    def get_categories(cls) -> List[str]:
        """Get all categories."""
        return list(cls._by_category.keys())

    @classmethod
    def list_all(cls) -> List[Dict]:
        """List all scenarios with metadata."""
        return [
            {
                "id": s.id,
                "name": s.name,
                "category": s.category,
                "description": s.description,
            }
            for s in cls._scenarios.values()
        ]


def register_scenario(cls: Type[BaseScenario]) -> Type[BaseScenario]:
    """Decorator to register a scenario class."""
    ScenarioRegistry.register(cls)
    return cls


class DemoRunner:
    """
    Main demo runner that orchestrates scenario execution.

    Features:
    - Service health checking
    - Scenario filtering by ID or category
    - Clean slate setup between scenarios
    - Result aggregation and reporting
    """

    def __init__(
        self,
        config: Optional[DemoConfig] = None,
        auto_mode: bool = False,
        verbose: bool = True,
    ):
        self.config = config or DemoConfig()
        self.config.auto_mode = auto_mode

        self.engine = EngineClient(base_url=self.config.engine_url)
        self.mock = MockExchangeClient(base_url=self.config.mock_exchange_url)
        self.presenter = ConsolePresenter(
            auto_mode=auto_mode,
            pause_delay=self.config.pause_delay,
            verbose=verbose,
        )

        self._results: List[ScenarioResult] = []

    async def setup(self) -> bool:
        """
        Initialize connections and verify services.

        Returns:
            True if setup succeeded
        """
        self.presenter.announce_phase(0, "Demo Setup")

        # Check Mock Exchange
        self.presenter.show_info("Checking Mock Exchange...")
        if not await self.mock.health_check():
            self.presenter.show_error("Mock Exchange is not running!")
            self.presenter.show_info("Start with: docker compose up mock-exchange")
            return False
        self.presenter.show_success("Mock Exchange is running")

        # Check Engine
        self.presenter.show_info("Checking Trading Engine...")
        if not await self.engine.health_check():
            self.presenter.show_error("Trading Engine is not running!")
            self.presenter.show_info("Start with: docker compose up app")
            return False
        self.presenter.show_success("Trading Engine is running")

        # Login
        self.presenter.show_info(f"Logging in as {self.config.username}...")
        try:
            await self.engine.login(self.config.username, self.config.password)
            self.config.user_id = self.engine.user_id
            self.config.webhook_secret = await self.engine.get_webhook_secret()
            self.presenter.show_success(f"Logged in. User ID: {self.config.user_id}")
        except Exception as e:
            self.presenter.show_error(f"Login failed: {e}")
            return False

        return True

    async def clean_slate(self):
        """Reset to clean state before running scenarios."""
        self.presenter.show_info("Resetting to clean slate...")

        # Reset mock exchange
        try:
            await self.mock.reset_exchange()
            self.presenter.show_success("Mock exchange reset")
        except Exception as e:
            self.presenter.show_warning(f"Mock reset failed: {e}")

        # Close all positions
        closed = await self.engine.close_all_positions()
        if closed:
            self.presenter.show_info(f"Closed {closed} positions")
            await asyncio.sleep(2)

        # Clear queue
        removed = await self.engine.clear_queue()
        if removed:
            self.presenter.show_info(f"Removed {removed} queued signals")

        self.presenter.show_success("Clean slate ready")

    async def run_scenario(
        self,
        scenario_class: Type[BaseScenario],
        clean_before: bool = False,
    ) -> ScenarioResult:
        """
        Run a single scenario.

        Args:
            scenario_class: The scenario class to instantiate and run
            clean_before: Whether to reset to clean slate before running

        Returns:
            ScenarioResult with execution details
        """
        if clean_before:
            await self.clean_slate()

        scenario = scenario_class(
            engine=self.engine,
            mock=self.mock,
            config=self.config,
            presenter=self.presenter,
        )

        result = await scenario.run()
        self._results.append(result)
        self.presenter.show_scenario_result(result)

        return result

    async def run_by_id(
        self,
        scenario_id: str,
        clean_before: bool = False,
    ) -> Optional[ScenarioResult]:
        """
        Run a scenario by its ID.

        Args:
            scenario_id: Scenario ID (e.g., "S-001")
            clean_before: Whether to reset before running

        Returns:
            ScenarioResult or None if scenario not found
        """
        scenario_class = ScenarioRegistry.get(scenario_id)
        if not scenario_class:
            self.presenter.show_error(f"Scenario '{scenario_id}' not found")
            return None

        return await self.run_scenario(scenario_class, clean_before)

    async def run_category(
        self,
        category: str,
        clean_before_each: bool = False,
    ) -> List[ScenarioResult]:
        """
        Run all scenarios in a category.

        Args:
            category: Category name (e.g., "signal", "queue", "risk")
            clean_before_each: Whether to reset before each scenario

        Returns:
            List of ScenarioResults
        """
        scenarios = ScenarioRegistry.get_by_category(category)
        if not scenarios:
            self.presenter.show_warning(f"No scenarios found in category '{category}'")
            return []

        self.presenter.announce_phase(0, f"Running {len(scenarios)} {category} scenarios")

        results = []
        for scenario_class in scenarios:
            result = await self.run_scenario(scenario_class, clean_before_each)
            results.append(result)

            # Pause between scenarios if not auto mode
            if not self.config.auto_mode:
                await self.presenter.async_pause("Continue to next scenario?")

        return results

    async def run_all(
        self,
        clean_before_each: bool = False,
        categories: Optional[List[str]] = None,
    ) -> List[ScenarioResult]:
        """
        Run all registered scenarios.

        Args:
            clean_before_each: Whether to reset before each scenario
            categories: Optional list of categories to run (None = all)

        Returns:
            List of all ScenarioResults
        """
        target_categories = categories or ScenarioRegistry.get_categories()

        self.presenter.announce_phase(0, "Running All Scenarios")

        all_results = []
        for category in target_categories:
            results = await self.run_category(category, clean_before_each)
            all_results.extend(results)

        return all_results

    async def run_quick_smoke(self) -> List[ScenarioResult]:
        """
        Run a quick smoke test with key scenarios.

        Runs the most important scenarios from each category
        for a quick health check.
        """
        quick_scenarios = [
            # Signal scenarios
            "S-001",  # Valid entry creates position
            "S-013",  # Valid pyramid adds to position
            "S-023",  # Valid exit closes position
            # Queue scenarios
            "Q-001",  # Signal queued when pool full
            "Q-016",  # Pyramid gets highest priority
            # Risk scenarios
            "R-011",  # Timer starts when conditions met
            # Order scenarios
            "O-001",  # Market order immediate fill
            "O-009",  # Full fill TP placement
            # Error scenarios
            "E-001",  # Duplicate signal detection
            # Edge scenarios
            "X-001",  # Minimum order size boundary
            # Lifecycle scenarios
            "L-001",  # Complete trade entry to exit
            # Config scenarios
            "C-004",  # DCA 3 levels
        ]

        self.presenter.announce_phase(0, "Quick Smoke Test")

        results = []
        for scenario_id in quick_scenarios:
            result = await self.run_by_id(scenario_id, clean_before=True)
            if result:
                results.append(result)

        return results

    def get_results(self) -> List[ScenarioResult]:
        """Get all results from this run."""
        return self._results

    def get_summary(self) -> Dict:
        """Get summary statistics from results."""
        passed = sum(1 for r in self._results if r.status == ScenarioStatus.PASSED)
        failed = sum(1 for r in self._results if r.status == ScenarioStatus.FAILED)
        skipped = sum(1 for r in self._results if r.status == ScenarioStatus.SKIPPED)
        total_time = sum(r.duration_ms for r in self._results)

        return {
            "total": len(self._results),
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "duration_ms": total_time,
            "success_rate": passed / len(self._results) * 100 if self._results else 0,
        }

    def show_summary(self):
        """Display summary to presenter."""
        self.presenter.show_demo_summary(self._results)

    async def cleanup(self):
        """Cleanup resources."""
        await self.engine.close()
        await self.mock.close()


async def run_demo(
    scenario_id: Optional[str] = None,
    category: Optional[str] = None,
    auto_mode: bool = False,
    clean_slate: bool = True,
    config: Optional[DemoConfig] = None,
) -> List[ScenarioResult]:
    """
    Convenience function to run demo scenarios.

    Args:
        scenario_id: Run specific scenario by ID
        category: Run all scenarios in category
        auto_mode: Run without pauses
        clean_slate: Reset state before running
        config: Optional demo configuration

    Returns:
        List of ScenarioResults
    """
    runner = DemoRunner(config=config, auto_mode=auto_mode)

    try:
        if not await runner.setup():
            return []

        if clean_slate:
            await runner.clean_slate()

        if scenario_id:
            result = await runner.run_by_id(scenario_id)
            results = [result] if result else []
        elif category:
            results = await runner.run_category(category)
        else:
            results = await runner.run_all()

        runner.show_summary()
        return results

    finally:
        await runner.cleanup()
