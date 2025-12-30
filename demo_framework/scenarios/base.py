"""
Base Scenario Classes for Demo Framework.

Provides the foundation for all demo scenarios with:
- Step-based execution with presentation
- Verification with expected/actual comparison
- Automatic timing and result tracking
- Teardown for cleanup
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..clients import EngineClient, MockExchangeClient
    from ..presenters import ConsolePresenter


class ScenarioStatus(Enum):
    """Status of a scenario or step."""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StepResult:
    """Result of a single step within a scenario."""
    name: str
    status: ScenarioStatus
    duration_ms: float
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VerificationResult:
    """Result of a verification check."""
    name: str
    passed: bool
    expected: str
    actual: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ScenarioResult:
    """Complete result of a scenario execution."""
    id: str
    name: str
    category: str
    status: ScenarioStatus
    steps: List[StepResult]
    verifications: List[VerificationResult]
    duration_ms: float
    error: Optional[str] = None


@dataclass
class DemoConfig:
    """Configuration for demo scenarios."""
    user_id: str = ""
    webhook_secret: str = ""
    username: str = "zmomz"
    password: str = "zm0mzzm0mz"
    engine_url: str = "http://127.0.0.1:8000"
    mock_exchange_url: str = "http://127.0.0.1:9000"
    max_open_positions: int = 3
    max_pyramids: int = 2
    auto_mode: bool = False
    pause_delay: float = 2.0


class BaseScenario(ABC):
    """
    Abstract base class for all demo scenarios.

    Scenarios are the core unit of the demo framework. Each scenario:
    1. Has a unique ID (e.g., "S-001", "Q-015")
    2. Tests a specific behavior or feature
    3. Contains setup, execute, and teardown phases
    4. Uses steps for actions and verifications for assertions
    5. Integrates with the presenter for live demo output

    Example usage:
        class MyScenario(BaseScenario):
            id = "S-001"
            name = "My Test Scenario"
            description = "Tests something important"
            category = "signal"

            async def execute(self) -> bool:
                result = await self.step(
                    "Do something",
                    lambda: self.engine.some_action(),
                    narration="Now we will do something..."
                )
                return await self.verify(
                    "Result is correct",
                    result["status"] == "ok",
                    expected="ok",
                    actual=result["status"]
                )
    """

    def __init__(
        self,
        engine: "EngineClient",
        mock: "MockExchangeClient",
        config: DemoConfig,
        presenter: "ConsolePresenter",
    ):
        self.engine = engine
        self.mock = mock
        self.config = config
        self.presenter = presenter
        self._steps: List[StepResult] = []
        self._verifications: List[VerificationResult] = []
        self._start_time: float = 0

    @property
    @abstractmethod
    def id(self) -> str:
        """Unique scenario ID (e.g., 'S-001', 'Q-015')."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable scenario name."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Detailed description of what this scenario tests."""
        pass

    @property
    def category(self) -> str:
        """Category for grouping ('signal', 'queue', 'risk', etc.)."""
        return "general"

    @property
    def tags(self) -> List[str]:
        """Optional tags for filtering scenarios."""
        return []

    async def setup(self) -> bool:
        """
        Pre-scenario setup. Override in subclass if needed.

        Returns:
            True if setup succeeded, False to skip scenario
        """
        return True

    @abstractmethod
    async def execute(self) -> bool:
        """
        Main scenario logic. Must be implemented by subclasses.

        Returns:
            True if scenario passed, False if failed
        """
        pass

    async def teardown(self):
        """
        Post-scenario cleanup. Override in subclass if needed.

        Called regardless of success/failure.
        """
        pass

    async def run(self) -> ScenarioResult:
        """
        Run the scenario with full lifecycle.

        1. Announces scenario to presenter
        2. Runs setup
        3. Executes main logic
        4. Runs teardown
        5. Returns result

        Returns:
            ScenarioResult with status, steps, verifications, timing
        """
        self._start_time = time.time()
        self._steps = []
        self._verifications = []

        # Announce
        self.presenter.announce_scenario(self.id, self.name, self.description)
        self.presenter.pause_for_audience("Ready to begin?")

        try:
            # Setup
            self.presenter.narrate("Setting up scenario...")
            if not await self.setup():
                return self._build_result(
                    ScenarioStatus.SKIPPED,
                    error="Setup returned False",
                )

            # Execute
            self.presenter.narrate("Executing scenario...")
            success = await self.execute()

            status = ScenarioStatus.PASSED if success else ScenarioStatus.FAILED
            return self._build_result(status)

        except Exception as e:
            import traceback
            error_msg = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
            self.presenter.show_error(str(e))
            return self._build_result(ScenarioStatus.FAILED, error=error_msg)

        finally:
            try:
                await self.teardown()
            except Exception as e:
                self.presenter.show_warning(f"Teardown error: {e}")

    async def step(
        self,
        name: str,
        action: Callable,
        narration: Optional[str] = None,
        show_result: bool = False,
    ) -> Any:
        """
        Execute a named step with presentation.

        Args:
            name: Step name shown in output
            action: Async callable to execute
            narration: What to say before executing
            show_result: Whether to display the result

        Returns:
            Whatever the action returns

        Raises:
            Any exception from action (captured in step result)
        """
        if narration:
            self.presenter.narrate(narration)

        self.presenter.start_step(name)
        start = time.time()

        try:
            # Call action (handle both sync and async)
            import asyncio
            if asyncio.iscoroutinefunction(action):
                result = await action()
            else:
                result = action()
                # If lambda returns a coroutine, await it
                if asyncio.iscoroutine(result):
                    result = await result

            duration = (time.time() - start) * 1000

            step_result = StepResult(
                name=name,
                status=ScenarioStatus.PASSED,
                duration_ms=duration,
                message="Success",
            )
            self._steps.append(step_result)
            self.presenter.end_step(step_result)

            if show_result and isinstance(result, dict):
                self.presenter.show_api_response(result)

            return result

        except Exception as e:
            duration = (time.time() - start) * 1000
            step_result = StepResult(
                name=name,
                status=ScenarioStatus.FAILED,
                duration_ms=duration,
                message=str(e),
            )
            self._steps.append(step_result)
            self.presenter.end_step(step_result)
            raise

    async def verify(
        self,
        name: str,
        condition: bool,
        expected: str,
        actual: str,
        details: Optional[Dict] = None,
    ) -> bool:
        """
        Verify a condition with presentation.

        Args:
            name: Verification name
            condition: Boolean result of the check
            expected: String describing expected value
            actual: String describing actual value
            details: Optional additional details

        Returns:
            The condition value (for chaining)
        """
        result = VerificationResult(
            name=name,
            passed=condition,
            expected=expected,
            actual=actual,
            details=details or {},
        )
        self._verifications.append(result)

        status = ScenarioStatus.PASSED if condition else ScenarioStatus.FAILED
        self.presenter.show_verification(name, status, expected, actual)

        return condition

    async def verify_all(self, *verifications: bool) -> bool:
        """
        Check that all verifications passed.

        Args:
            *verifications: Boolean results from verify() calls

        Returns:
            True if all passed, False otherwise
        """
        return all(verifications)

    def _build_result(
        self,
        status: ScenarioStatus,
        error: Optional[str] = None,
    ) -> ScenarioResult:
        """Build the final scenario result."""
        duration = (time.time() - self._start_time) * 1000
        return ScenarioResult(
            id=self.id,
            name=self.name,
            category=self.category,
            status=status,
            steps=self._steps,
            verifications=self._verifications,
            duration_ms=duration,
            error=error,
        )


class SetupScenario(BaseScenario):
    """
    Base class for scenarios that set up initial state.

    Used for scenarios like "clean slate" that prepare for other tests.
    """

    @property
    def category(self) -> str:
        return "setup"


class CleanupScenario(BaseScenario):
    """
    Base class for scenarios that clean up after tests.

    Used for scenarios that reset state between test runs.
    """

    @property
    def category(self) -> str:
        return "cleanup"
