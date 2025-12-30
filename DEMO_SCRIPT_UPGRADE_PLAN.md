# Demo Script Major Upgrade Plan

## Executive Summary

The current `demo_script.py` (1,803 lines) is a solid foundation but needs significant upgrades to become a production-grade testing and demonstration framework. This plan outlines a comprehensive overhaul to transform it into a modular, extensible, self-validating test/demo system.

---

## Current State Analysis

### Strengths
- ✅ 13 demo phases covering full trading lifecycle
- ✅ Clean async architecture with httpx
- ✅ Color-coded terminal output
- ✅ CLI arguments for flexibility
- ✅ Webhook payload builder
- ✅ Basic verification helpers

### Weaknesses & Gaps
- ❌ **No assertions/validation** - Just prints results, doesn't verify correctness
- ❌ **Hardcoded delays** - Uses arbitrary `asyncio.sleep()` instead of polling for state
- ❌ **No error recovery** - Failures abort entire demo
- ❌ **No scenario isolation** - Phases depend on previous state
- ❌ **Monolithic structure** - Everything in one 1,800 line file
- ❌ **No test reporting** - No summary of pass/fail
- ❌ **No data-driven tests** - Scenarios are hardcoded
- ❌ **No parallel execution** - Sequential only
- ❌ **No mock exchange validation** - Doesn't verify mock exchange state matches expectations
- ❌ **No performance metrics** - No timing/throughput measurement
- ❌ **No screenshots/artifacts** - No evidence collection for demos
- ❌ **No WebSocket support** - Only REST, no real-time updates
- ❌ **No frontend integration** - Can't demonstrate UI alongside API

---

## Proposed Architecture

```
demo_framework/
├── __init__.py
├── config/
│   ├── __init__.py
│   ├── demo_config.py          # Configuration dataclasses
│   ├── scenarios/              # YAML/JSON scenario definitions
│   │   ├── full_demo.yaml
│   │   ├── quick_smoke.yaml
│   │   ├── risk_engine_focus.yaml
│   │   ├── queue_priority.yaml
│   │   └── edge_cases.yaml
│   └── fixtures/               # Test data fixtures
│       ├── dca_configs.json
│       ├── signals.json
│       └── prices.json
│
├── clients/
│   ├── __init__.py
│   ├── base_client.py          # Base HTTP client with retry logic
│   ├── engine_client.py        # Trading engine API client
│   ├── mock_exchange_client.py # Mock exchange admin client
│   ├── websocket_client.py     # WebSocket client for real-time
│   └── database_client.py      # Direct DB access for verification
│
├── scenarios/
│   ├── __init__.py
│   ├── base_scenario.py        # Abstract scenario class
│   ├── setup_scenario.py       # Clean slate, login, config
│   ├── signal_flow_scenario.py # Entry → pyramid → exit
│   ├── queue_scenario.py       # Queue filling and priority
│   ├── dca_fill_scenario.py    # DCA order fill via price movement
│   ├── risk_engine_scenario.py # Risk timer and offset
│   ├── tp_mode_scenario.py     # TP modes demonstration
│   └── manual_controls_scenario.py
│
├── validators/
│   ├── __init__.py
│   ├── base_validator.py       # Assertion framework
│   ├── position_validator.py   # Verify position state
│   ├── queue_validator.py      # Verify queue state
│   ├── order_validator.py      # Verify mock exchange orders
│   ├── risk_validator.py       # Verify risk engine state
│   └── pnl_validator.py        # Verify PnL calculations
│
├── reporters/
│   ├── __init__.py
│   ├── console_reporter.py     # Rich terminal output
│   ├── html_reporter.py        # HTML test report
│   ├── json_reporter.py        # Machine-readable results
│   └── screenshot_reporter.py  # Capture API responses as artifacts
│
├── utils/
│   ├── __init__.py
│   ├── polling.py              # Wait-for-condition utilities
│   ├── payload_builder.py      # Webhook payload construction
│   ├── price_calculator.py     # DCA/TP price calculations
│   └── formatters.py           # Output formatting
│
├── runner.py                   # Main test runner
└── cli.py                      # CLI entry point
```

---

## Phase 1: Core Infrastructure (Foundation)

### 1.1 Modular Client Architecture

**Create `clients/base_client.py`:**
```python
class BaseClient:
    """Base HTTP client with retry, timeout, and logging."""

    def __init__(self, base_url: str, timeout: float = 30.0):
        self.base_url = base_url
        self.client = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout,
            event_hooks={'request': [self._log_request], 'response': [self._log_response]}
        )
        self.request_log: List[RequestLog] = []

    async def _retry_request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Retry with exponential backoff."""
        for attempt in range(3):
            try:
                resp = await getattr(self.client, method)(url, **kwargs)
                return resp
            except httpx.TimeoutException:
                if attempt == 2:
                    raise
                await asyncio.sleep(2 ** attempt)
```

### 1.2 Polling/Wait Utilities

**Create `utils/polling.py`:**
```python
async def wait_for_condition(
    check_fn: Callable[[], Awaitable[bool]],
    timeout: float = 30.0,
    interval: float = 1.0,
    description: str = "condition"
) -> bool:
    """Poll until condition is met or timeout."""
    start = time.time()
    while time.time() - start < timeout:
        if await check_fn():
            return True
        await asyncio.sleep(interval)
    raise TimeoutError(f"Timed out waiting for {description}")

async def wait_for_position_count(
    client: EngineClient,
    expected: int,
    timeout: float = 30.0
) -> List[dict]:
    """Wait for specific number of positions."""
    async def check():
        positions = await client.get_active_positions()
        return len(positions) == expected

    await wait_for_condition(check, timeout, description=f"{expected} positions")
    return await client.get_active_positions()

async def wait_for_order_fills(
    mock: MockExchangeClient,
    symbol: str,
    min_fills: int,
    timeout: float = 60.0
) -> List[dict]:
    """Wait for orders to fill on mock exchange."""
    ...
```

### 1.3 Validation Framework

**Create `validators/base_validator.py`:**
```python
@dataclass
class ValidationResult:
    passed: bool
    message: str
    expected: Any
    actual: Any
    details: Optional[dict] = None

class BaseValidator:
    """Base class for state validators."""

    def __init__(self):
        self.results: List[ValidationResult] = []

    def assert_equal(self, actual, expected, message: str):
        result = ValidationResult(
            passed=actual == expected,
            message=message,
            expected=expected,
            actual=actual
        )
        self.results.append(result)
        return result.passed

    def assert_in_range(self, value, min_val, max_val, message: str):
        ...

    def assert_position_state(self, position: dict, expected_state: dict):
        """Validate position matches expected state."""
        ...
```

**Create `validators/position_validator.py`:**
```python
class PositionValidator(BaseValidator):
    """Validates position group state."""

    async def validate_position_exists(
        self,
        client: EngineClient,
        symbol: str,
        expected_side: str = "long"
    ) -> ValidationResult:
        positions = await client.get_active_positions()
        matching = [p for p in positions if p["symbol"] == symbol]

        return self.assert_equal(
            len(matching) > 0,
            True,
            f"Position {symbol} should exist"
        )

    async def validate_pyramid_count(
        self,
        client: EngineClient,
        symbol: str,
        expected: int
    ) -> ValidationResult:
        positions = await client.get_active_positions()
        pos = next((p for p in positions if p["symbol"] == symbol), None)

        if not pos:
            return ValidationResult(False, f"Position {symbol} not found", expected, None)

        return self.assert_equal(
            pos.get("pyramid_count", 0),
            expected,
            f"{symbol} pyramid count"
        )

    async def validate_pnl_range(
        self,
        client: EngineClient,
        symbol: str,
        min_pnl: float,
        max_pnl: float
    ) -> ValidationResult:
        """Validate PnL is within expected range."""
        ...

    async def validate_risk_eligibility(
        self,
        client: EngineClient,
        symbol: str,
        expected_eligible: bool
    ) -> ValidationResult:
        """Validate position risk eligibility."""
        ...
```

---

## Phase 2: Scenario System

### 2.1 Base Scenario Class

**Create `scenarios/base_scenario.py`:**
```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

class ScenarioStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"

@dataclass
class StepResult:
    name: str
    status: ScenarioStatus
    duration_ms: float
    validations: List[ValidationResult]
    error: Optional[str] = None
    artifacts: Optional[dict] = None  # Screenshots, logs, etc.

class BaseScenario(ABC):
    """Abstract base class for demo scenarios."""

    def __init__(
        self,
        engine: EngineClient,
        mock: MockExchangeClient,
        config: DemoConfig,
        reporter: BaseReporter
    ):
        self.engine = engine
        self.mock = mock
        self.config = config
        self.reporter = reporter
        self.steps: List[StepResult] = []
        self.validators = {
            "position": PositionValidator(),
            "queue": QueueValidator(),
            "order": OrderValidator(),
            "risk": RiskValidator(),
        }

    @property
    @abstractmethod
    def name(self) -> str:
        """Scenario name."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Scenario description."""
        pass

    @abstractmethod
    async def setup(self) -> bool:
        """Pre-scenario setup."""
        pass

    @abstractmethod
    async def execute(self) -> bool:
        """Main scenario execution."""
        pass

    @abstractmethod
    async def teardown(self) -> None:
        """Post-scenario cleanup."""
        pass

    @abstractmethod
    async def validate(self) -> List[ValidationResult]:
        """Final validation."""
        pass

    async def run(self) -> ScenarioResult:
        """Run complete scenario with timing."""
        start = time.time()

        try:
            # Setup
            self.reporter.start_scenario(self.name)
            if not await self.setup():
                return ScenarioResult(status=ScenarioStatus.FAILED, ...)

            # Execute
            if not await self.execute():
                return ScenarioResult(status=ScenarioStatus.FAILED, ...)

            # Validate
            validations = await self.validate()
            all_passed = all(v.passed for v in validations)

            return ScenarioResult(
                status=ScenarioStatus.PASSED if all_passed else ScenarioStatus.FAILED,
                steps=self.steps,
                validations=validations,
                duration_ms=(time.time() - start) * 1000
            )
        except Exception as e:
            return ScenarioResult(status=ScenarioStatus.FAILED, error=str(e), ...)
        finally:
            await self.teardown()

    async def step(self, name: str, fn: Callable, validations: List[Callable] = None):
        """Execute a named step with timing and validation."""
        self.reporter.start_step(name)
        start = time.time()

        try:
            result = await fn()

            # Run step validations
            validation_results = []
            if validations:
                for validate_fn in validations:
                    validation_results.append(await validate_fn())

            step_result = StepResult(
                name=name,
                status=ScenarioStatus.PASSED if all(v.passed for v in validation_results) else ScenarioStatus.FAILED,
                duration_ms=(time.time() - start) * 1000,
                validations=validation_results
            )
            self.steps.append(step_result)
            self.reporter.end_step(step_result)

            return result
        except Exception as e:
            step_result = StepResult(
                name=name,
                status=ScenarioStatus.FAILED,
                duration_ms=(time.time() - start) * 1000,
                validations=[],
                error=str(e)
            )
            self.steps.append(step_result)
            self.reporter.end_step(step_result)
            raise
```

### 2.2 Example: Signal Flow Scenario

**Create `scenarios/signal_flow_scenario.py`:**
```python
class SignalFlowScenario(BaseScenario):
    """Tests complete signal flow: entry → pyramids → DCA fills → exit."""

    name = "Signal Flow"
    description = "Complete trading lifecycle from entry to exit"

    def __init__(self, *args, symbol: str = "SOL/USDT", **kwargs):
        super().__init__(*args, **kwargs)
        self.symbol = symbol
        self.exchange_symbol = symbol.replace("/", "")
        self.initial_price = 200.0
        self.position_id: Optional[str] = None

    async def setup(self) -> bool:
        """Ensure clean state and set initial price."""
        # Set price on mock exchange
        await self.mock.set_price(self.exchange_symbol, self.initial_price)

        # Ensure DCA config exists
        configs = await self.engine.get_dca_configs()
        if not any(c["pair"] == self.symbol for c in configs):
            await self.engine.create_dca_config({
                "pair": self.symbol,
                "timeframe": 60,
                "exchange": "mock",
                "entry_order_type": "market",
                "max_pyramids": 2,
                "tp_mode": "per_leg",
                "dca_levels": [
                    {"gap_percent": 0, "weight_percent": 40, "tp_percent": 5},
                    {"gap_percent": -2, "weight_percent": 30, "tp_percent": 5},
                    {"gap_percent": -4, "weight_percent": 30, "tp_percent": 5},
                ],
            })

        return True

    async def execute(self) -> bool:
        """Execute signal flow steps."""

        # Step 1: Send entry signal
        await self.step(
            "Send Entry Signal",
            self._send_entry_signal,
            validations=[
                lambda: self.validators["position"].validate_position_exists(
                    self.engine, self.symbol
                )
            ]
        )

        # Step 2: Wait for position creation
        await self.step(
            "Wait for Position",
            lambda: wait_for_position_count(self.engine, 1, timeout=15),
            validations=[
                lambda: self.validators["position"].validate_pyramid_count(
                    self.engine, self.symbol, expected=0
                )
            ]
        )

        # Step 3: Send pyramid signal
        await self.step(
            "Send Pyramid Signal",
            self._send_pyramid_signal,
            validations=[
                lambda: self.validators["position"].validate_pyramid_count(
                    self.engine, self.symbol, expected=1
                )
            ]
        )

        # Step 4: Fill DCA orders via price drop
        await self.step(
            "Fill DCA Orders",
            self._trigger_dca_fills,
            validations=[
                lambda: self.validators["order"].validate_fills(
                    self.mock, self.exchange_symbol, min_fills=3
                )
            ]
        )

        # Step 5: Send exit signal
        await self.step(
            "Send Exit Signal",
            self._send_exit_signal,
            validations=[
                lambda: self.validators["position"].validate_position_closed(
                    self.engine, self.symbol
                )
            ]
        )

        return True

    async def _send_entry_signal(self):
        """Send initial entry signal."""
        payload = build_webhook_payload(
            user_id=self.config.user_id,
            secret=self.config.webhook_secret,
            symbol=self.exchange_symbol,
            action="buy",
            market_position="long",
            position_size=500,
            entry_price=self.initial_price,
        )
        return await self.engine.send_webhook(payload)

    async def _send_pyramid_signal(self):
        """Send pyramid continuation signal."""
        # Drop price first
        new_price = self.initial_price * 0.98  # -2%
        await self.mock.set_price(self.exchange_symbol, new_price)

        payload = build_webhook_payload(
            user_id=self.config.user_id,
            secret=self.config.webhook_secret,
            symbol=self.exchange_symbol,
            action="buy",
            market_position="long",
            position_size=500,
            entry_price=new_price,
            prev_market_position="long",
            prev_position_size=500,
        )
        return await self.engine.send_webhook(payload)

    async def _trigger_dca_fills(self):
        """Drop price progressively to fill DCA orders."""
        for price_mult in [0.96, 0.94, 0.92, 0.90]:
            await self.mock.set_price(
                self.exchange_symbol,
                self.initial_price * price_mult
            )
            await asyncio.sleep(2)

        # Wait for fills to be detected
        return await wait_for_order_fills(
            self.mock, self.exchange_symbol, min_fills=3
        )

    async def _send_exit_signal(self):
        """Send exit/close signal."""
        payload = build_webhook_payload(
            user_id=self.config.user_id,
            secret=self.config.webhook_secret,
            symbol=self.exchange_symbol,
            action="sell",
            market_position="flat",
            position_size=0,
            entry_price=0,
            prev_market_position="long",
            prev_position_size=500,
        )
        return await self.engine.send_webhook(payload)

    async def validate(self) -> List[ValidationResult]:
        """Final scenario validations."""
        return [
            # Position should be closed
            await self.validators["position"].validate_position_closed(
                self.engine, self.symbol
            ),
            # Should appear in history
            await self.validators["position"].validate_in_history(
                self.engine, self.symbol
            ),
        ]

    async def teardown(self) -> None:
        """Cleanup after scenario."""
        # Reset price
        await self.mock.set_price(self.exchange_symbol, self.initial_price)
```

---

## Phase 3: Data-Driven Scenarios

### 3.1 YAML Scenario Definitions

**Create `config/scenarios/full_demo.yaml`:**
```yaml
name: Full Trading Demo
description: Complete demonstration of all trading engine features
timeout_minutes: 30

prerequisites:
  - services_running
  - clean_state

phases:
  - name: Setup
    scenarios:
      - type: setup
        config:
          reset_mock_exchange: true
          clear_positions: true
          clear_queue: true
          configure_api_keys: true

  - name: DCA Configuration
    scenarios:
      - type: dca_setup
        config:
          configs:
            - pair: "SOL/USDT"
              role: loser  # Will be used as risk offset target
              tp_percent: 3
              max_pyramids: 2
            - pair: "BTC/USDT"
              role: winner
              tp_percent: 20
              max_pyramids: 2
            - pair: "ETH/USDT"
              role: winner
              tp_mode: aggregate
              tp_percent: 15
              max_pyramids: 2

  - name: Fill Execution Pool
    scenarios:
      - type: signal_flow
        config:
          signals:
            - symbol: "SOL/USDT"
              action: entry
              expected_result: position_created
            - symbol: "BTC/USDT"
              action: entry
              expected_result: position_created
            - symbol: "ETH/USDT"
              action: entry
              expected_result: position_created
        validations:
          - type: position_count
            expected: 3

  - name: Queue Demonstration
    scenarios:
      - type: queue_filling
        config:
          signals:
            - symbol: "ADA/USDT"
              expected_result: queued
            - symbol: "XRP/USDT"
              expected_result: queued
            - symbol: "DOGE/USDT"
              expected_result: queued
      - type: queue_replacement
        config:
          symbol: "ADA/USDT"
          replacement_count: 2
        validations:
          - type: replacement_count
            symbol: "ADA/USDT"
            expected: 2

  - name: Pyramid Continuation
    scenarios:
      - type: pyramid
        config:
          symbol: "SOL/USDT"
          pyramids: 2
          price_drops: [-2%, -4%]
        validations:
          - type: pyramid_count
            symbol: "SOL/USDT"
            expected: 2

  - name: Risk Engine
    scenarios:
      - type: risk_setup
        config:
          loser:
            symbol: "SOL/USDT"
            target_pnl: -3%
          winners:
            - symbol: "BTC/USDT"
              target_pnl: +50%
            - symbol: "ETH/USDT"
              target_pnl: +50%
      - type: wait_for_timer
        config:
          timeout_minutes: 2
      - type: risk_execution
        validations:
          - type: position_closed
            symbol: "SOL/USDT"
            close_reason: risk_offset
          - type: position_partial_close
            symbols: ["BTC/USDT", "ETH/USDT"]
```

### 3.2 Scenario Loader

**Create `scenarios/loader.py`:**
```python
import yaml
from pathlib import Path
from typing import List

class ScenarioLoader:
    """Loads and instantiates scenarios from YAML definitions."""

    SCENARIO_TYPES = {
        "setup": SetupScenario,
        "dca_setup": DCASetupScenario,
        "signal_flow": SignalFlowScenario,
        "queue_filling": QueueFillingScenario,
        "queue_replacement": QueueReplacementScenario,
        "pyramid": PyramidScenario,
        "risk_setup": RiskSetupScenario,
        "risk_execution": RiskExecutionScenario,
        "wait_for_timer": WaitForTimerScenario,
    }

    def load_from_yaml(self, path: Path) -> List[BaseScenario]:
        """Load scenarios from YAML file."""
        with open(path) as f:
            config = yaml.safe_load(f)

        scenarios = []
        for phase in config.get("phases", []):
            for scenario_def in phase.get("scenarios", []):
                scenario_type = scenario_def["type"]
                scenario_class = self.SCENARIO_TYPES.get(scenario_type)

                if not scenario_class:
                    raise ValueError(f"Unknown scenario type: {scenario_type}")

                scenarios.append(
                    scenario_class(
                        config=scenario_def.get("config", {}),
                        validations=scenario_def.get("validations", [])
                    )
                )

        return scenarios
```

---

## Phase 4: Rich Reporting

### 4.1 Console Reporter with Rich

**Create `reporters/console_reporter.py`:**
```python
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.live import Live
from rich.tree import Tree

class ConsoleReporter(BaseReporter):
    """Rich terminal output for demos."""

    def __init__(self):
        self.console = Console()
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console
        )

    def start_scenario(self, name: str):
        self.console.print(Panel(
            f"[bold cyan]{name}[/bold cyan]",
            title="Starting Scenario",
            border_style="cyan"
        ))

    def end_step(self, result: StepResult):
        icon = "✅" if result.status == ScenarioStatus.PASSED else "❌"
        color = "green" if result.status == ScenarioStatus.PASSED else "red"

        self.console.print(
            f"  {icon} [{color}]{result.name}[/{color}] "
            f"({result.duration_ms:.0f}ms)"
        )

        # Show validation details
        for validation in result.validations:
            v_icon = "✓" if validation.passed else "✗"
            v_color = "green" if validation.passed else "red"
            self.console.print(
                f"      [{v_color}]{v_icon} {validation.message}[/{v_color}]"
            )

    def show_positions_table(self, positions: List[dict]):
        """Display positions in a rich table."""
        table = Table(title="Active Positions", show_header=True)
        table.add_column("Symbol", style="cyan")
        table.add_column("Side", style="magenta")
        table.add_column("Pyramids", justify="right")
        table.add_column("Qty", justify="right")
        table.add_column("Avg Entry", justify="right")
        table.add_column("PnL %", justify="right")
        table.add_column("Status")

        for pos in positions:
            pnl = float(pos.get("unrealized_pnl_percent", 0) or 0)
            pnl_style = "green" if pnl >= 0 else "red"

            table.add_row(
                pos.get("symbol", "N/A"),
                pos.get("side", "N/A"),
                str(pos.get("pyramid_count", 0)),
                f"{float(pos.get('total_filled_quantity', 0)):.4f}",
                f"${float(pos.get('weighted_avg_entry', 0)):.2f}",
                f"[{pnl_style}]{pnl:.2f}%[/{pnl_style}]",
                pos.get("status", "N/A"),
            )

        self.console.print(table)

    def show_final_summary(self, results: List[ScenarioResult]):
        """Show final test summary."""
        passed = sum(1 for r in results if r.status == ScenarioStatus.PASSED)
        failed = sum(1 for r in results if r.status == ScenarioStatus.FAILED)

        tree = Tree("[bold]Test Summary[/bold]")
        tree.add(f"[green]Passed: {passed}[/green]")
        tree.add(f"[red]Failed: {failed}[/red]")
        tree.add(f"Total Duration: {sum(r.duration_ms for r in results):.0f}ms")

        self.console.print(Panel(tree, border_style="bold"))
```

### 4.2 HTML Report Generator

**Create `reporters/html_reporter.py`:**
```python
class HTMLReporter(BaseReporter):
    """Generate HTML test reports."""

    def generate_report(self, results: List[ScenarioResult], output_path: Path):
        """Generate HTML report with charts and details."""
        template = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Demo Test Report</title>
            <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
            <style>
                body { font-family: sans-serif; margin: 20px; }
                .passed { color: green; }
                .failed { color: red; }
                .scenario { border: 1px solid #ccc; margin: 10px 0; padding: 15px; }
                .step { margin-left: 20px; }
            </style>
        </head>
        <body>
            <h1>Trading Engine Demo Report</h1>
            <p>Generated: {{ timestamp }}</p>

            <h2>Summary</h2>
            <canvas id="summaryChart" width="400" height="200"></canvas>

            <h2>Scenarios</h2>
            {% for scenario in scenarios %}
            <div class="scenario">
                <h3>{{ scenario.name }} - <span class="{{ scenario.status }}">{{ scenario.status }}</span></h3>
                <p>Duration: {{ scenario.duration_ms }}ms</p>

                <h4>Steps</h4>
                {% for step in scenario.steps %}
                <div class="step">
                    <strong>{{ step.name }}</strong> - {{ step.status }} ({{ step.duration_ms }}ms)
                    <ul>
                    {% for validation in step.validations %}
                        <li class="{{ 'passed' if validation.passed else 'failed' }}">
                            {{ validation.message }}: Expected {{ validation.expected }}, Got {{ validation.actual }}
                        </li>
                    {% endfor %}
                    </ul>
                </div>
                {% endfor %}
            </div>
            {% endfor %}

            <script>
                new Chart(document.getElementById('summaryChart'), {
                    type: 'pie',
                    data: {
                        labels: ['Passed', 'Failed'],
                        datasets: [{
                            data: [{{ passed_count }}, {{ failed_count }}],
                            backgroundColor: ['#4CAF50', '#f44336']
                        }]
                    }
                });
            </script>
        </body>
        </html>
        """
        ...
```

---

## Phase 5: Advanced Features

### 5.1 WebSocket Client for Real-Time Updates

**Create `clients/websocket_client.py`:**
```python
import websockets
import json

class WebSocketClient:
    """WebSocket client for real-time position/queue updates."""

    def __init__(self, ws_url: str, auth_token: str):
        self.ws_url = ws_url
        self.auth_token = auth_token
        self.ws = None
        self.event_handlers: Dict[str, List[Callable]] = {}

    async def connect(self):
        """Establish WebSocket connection."""
        self.ws = await websockets.connect(
            f"{self.ws_url}?token={self.auth_token}"
        )
        asyncio.create_task(self._listen())

    async def _listen(self):
        """Listen for incoming messages."""
        async for message in self.ws:
            data = json.loads(message)
            event_type = data.get("type")

            for handler in self.event_handlers.get(event_type, []):
                await handler(data)

    def on(self, event_type: str, handler: Callable):
        """Register event handler."""
        self.event_handlers.setdefault(event_type, []).append(handler)

    async def wait_for_event(
        self,
        event_type: str,
        condition: Callable[[dict], bool],
        timeout: float = 30.0
    ) -> dict:
        """Wait for specific event matching condition."""
        event = asyncio.Event()
        result = {}

        async def handler(data):
            if condition(data):
                result.update(data)
                event.set()

        self.on(event_type, handler)
        await asyncio.wait_for(event.wait(), timeout)
        return result
```

### 5.2 Parallel Scenario Execution

**Create `runner.py`:**
```python
class DemoRunner:
    """Main demo/test runner with parallel execution support."""

    def __init__(self, config: DemoConfig):
        self.config = config
        self.engine = EngineClient(config.engine_url)
        self.mock = MockExchangeClient(config.mock_exchange_url)
        self.reporters: List[BaseReporter] = []

    async def run_scenarios(
        self,
        scenarios: List[BaseScenario],
        parallel: bool = False
    ) -> List[ScenarioResult]:
        """Run scenarios sequentially or in parallel."""
        if parallel:
            return await self._run_parallel(scenarios)
        return await self._run_sequential(scenarios)

    async def _run_sequential(self, scenarios: List[BaseScenario]) -> List[ScenarioResult]:
        """Run scenarios one by one."""
        results = []
        for scenario in scenarios:
            result = await scenario.run()
            results.append(result)

            for reporter in self.reporters:
                reporter.report_scenario(result)

        return results

    async def _run_parallel(self, scenarios: List[BaseScenario]) -> List[ScenarioResult]:
        """Run independent scenarios in parallel."""
        # Group by dependencies
        independent = [s for s in scenarios if not s.depends_on]
        dependent = [s for s in scenarios if s.depends_on]

        # Run independent in parallel
        results = await asyncio.gather(*[s.run() for s in independent])

        # Run dependent sequentially
        for scenario in dependent:
            results.append(await scenario.run())

        return list(results)
```

### 5.3 Performance Metrics

**Create `utils/metrics.py`:**
```python
@dataclass
class PerformanceMetrics:
    """Performance metrics collection."""

    api_latencies: Dict[str, List[float]] = field(default_factory=dict)
    order_fill_times: List[float] = field(default_factory=list)
    position_creation_times: List[float] = field(default_factory=list)

    def record_api_call(self, endpoint: str, duration_ms: float):
        self.api_latencies.setdefault(endpoint, []).append(duration_ms)

    def get_summary(self) -> dict:
        """Get performance summary."""
        return {
            "api_latencies": {
                endpoint: {
                    "min": min(times),
                    "max": max(times),
                    "avg": sum(times) / len(times),
                    "p95": np.percentile(times, 95),
                }
                for endpoint, times in self.api_latencies.items()
            },
            "order_fill_time_avg": sum(self.order_fill_times) / len(self.order_fill_times) if self.order_fill_times else 0,
            "position_creation_avg": sum(self.position_creation_times) / len(self.position_creation_times) if self.position_creation_times else 0,
        }
```

### 5.4 Database Client for Direct Verification

**Create `clients/database_client.py`:**
```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

class DatabaseClient:
    """Direct database access for verification."""

    def __init__(self, db_url: str):
        self.engine = create_async_engine(db_url)
        self.session_factory = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def get_position_by_symbol(self, user_id: str, symbol: str) -> Optional[dict]:
        """Get position directly from database."""
        async with self.session_factory() as session:
            result = await session.execute(
                select(PositionGroup)
                .where(PositionGroup.user_id == user_id)
                .where(PositionGroup.symbol == symbol)
                .where(PositionGroup.status.notin_(['closed', 'failed']))
            )
            pos = result.scalar_one_or_none()
            return pos.__dict__ if pos else None

    async def verify_order_state(self, order_id: str) -> dict:
        """Verify order state in database vs mock exchange."""
        ...

    async def get_risk_actions(self, limit: int = 10) -> List[dict]:
        """Get recent risk actions."""
        ...
```

---

## Phase 6: CLI & Entry Points

### 6.1 Rich CLI

**Create `cli.py`:**
```python
import click
from rich.console import Console

console = Console()

@click.group()
def cli():
    """Trading Engine Demo Framework CLI."""
    pass

@cli.command()
@click.option('--scenario', '-s', default='full_demo', help='Scenario file name')
@click.option('--phase', '-p', type=int, default=1, help='Start from phase N')
@click.option('--parallel', is_flag=True, help='Run independent scenarios in parallel')
@click.option('--report', '-r', type=click.Choice(['console', 'html', 'json']), default='console')
@click.option('--output', '-o', type=click.Path(), help='Report output path')
@click.option('--fail-fast', is_flag=True, help='Stop on first failure')
def run(scenario, phase, parallel, report, output, fail_fast):
    """Run demo scenarios."""
    asyncio.run(_run_demo(scenario, phase, parallel, report, output, fail_fast))

@cli.command()
@click.option('--scenario', '-s', required=True, help='Scenario file name')
def validate(scenario):
    """Validate scenario YAML without running."""
    ...

@cli.command()
def list_scenarios():
    """List available scenarios."""
    scenarios_dir = Path(__file__).parent / "config" / "scenarios"
    for f in scenarios_dir.glob("*.yaml"):
        console.print(f"  • {f.stem}")

@cli.command()
@click.option('--watch', '-w', is_flag=True, help='Continuously monitor')
@click.option('--interval', '-i', type=int, default=5, help='Watch interval seconds')
def monitor(watch, interval):
    """Monitor system state (positions, queue, risk)."""
    asyncio.run(_monitor(watch, interval))

@cli.command()
def reset():
    """Reset mock exchange and clear all positions."""
    asyncio.run(_reset())

if __name__ == "__main__":
    cli()
```

---

## Phase 7: Additional Scenarios

### 7.1 New Scenario Types to Implement

| Scenario | Description | Key Validations |
|----------|-------------|-----------------|
| `EdgeCaseScenario` | Test boundary conditions | Max positions, max pyramids, invalid signals |
| `ConcurrencyScenario` | Parallel signal processing | Race conditions, order consistency |
| `RecoveryScenario` | Test system recovery | Restart during operations, state consistency |
| `PerformanceScenario` | Load testing | Throughput, latency under load |
| `NegativeTestScenario` | Invalid inputs | Proper error handling, no side effects |
| `ExchangeFailureScenario` | Mock exchange errors | Timeout handling, retry behavior |
| `TPModeScenario` | All TP modes | per_leg, aggregate, hybrid behavior |
| `MultiUserScenario` | Multiple users | Isolation, no cross-contamination |

### 7.2 Edge Case Examples

```python
class EdgeCaseScenario(BaseScenario):
    """Test edge cases and boundary conditions."""

    name = "Edge Cases"

    async def execute(self):
        # Test: Signal with missing DCA config
        await self.step(
            "Signal without DCA config",
            self._send_unconfigured_signal,
            validations=[
                lambda: self.validators["response"].validate_error(
                    expected_error="No DCA configuration"
                )
            ]
        )

        # Test: Duplicate signal (same trade_id)
        await self.step(
            "Duplicate signal rejection",
            self._send_duplicate_signal,
            validations=[
                lambda: self.validators["response"].validate_deduplicated()
            ]
        )

        # Test: Pyramid beyond max
        await self.step(
            "Pyramid beyond max_pyramids",
            self._send_excess_pyramid,
            validations=[
                lambda: self.validators["position"].validate_pyramid_count(
                    self.engine, "SOL/USDT", expected=2  # Should not exceed max
                )
            ]
        )

        # Test: Exit signal for non-existent position
        await self.step(
            "Exit for non-existent position",
            self._send_invalid_exit,
            validations=[
                lambda: self.validators["response"].validate_graceful_handling()
            ]
        )
```

---

## Implementation Roadmap

### Sprint 1 (Foundation)
- [ ] Create directory structure
- [ ] Implement `BaseClient` with retry logic
- [ ] Implement `polling.py` utilities
- [ ] Implement `BaseValidator` and `ValidationResult`
- [ ] Implement `PositionValidator`

### Sprint 2 (Scenarios)
- [ ] Implement `BaseScenario` abstract class
- [ ] Implement `SetupScenario`
- [ ] Implement `SignalFlowScenario`
- [ ] Implement `QueueScenario`
- [ ] YAML scenario loader

### Sprint 3 (Reporting)
- [ ] Implement `ConsoleReporter` with Rich
- [ ] Implement `HTMLReporter`
- [ ] Implement `JSONReporter`
- [ ] Performance metrics collection

### Sprint 4 (Advanced)
- [ ] WebSocket client
- [ ] Database direct verification client
- [ ] Parallel execution support
- [ ] CLI interface

### Sprint 5 (Scenarios)
- [ ] Risk engine scenario
- [ ] Edge case scenarios
- [ ] Recovery scenarios
- [ ] Full demo YAML migration

### Sprint 6 (Polish)
- [ ] Full test coverage
- [ ] Documentation
- [ ] CI/CD integration
- [ ] Migration guide from old script

---

## Migration Strategy

### Backward Compatibility
1. Keep `demo_script.py` functional during migration
2. New framework in `demo_framework/` directory
3. Gradual migration of phases to new scenarios
4. Final cutover once all scenarios pass

### Testing the Migration
```bash
# Run old script
python demo_script.py --auto --delay 1

# Run new framework (same scenarios)
python -m demo_framework run -s full_demo --fail-fast

# Compare results
python -m demo_framework compare old_results.json new_results.json
```

---

## Success Criteria

1. **All 13 phases** from original demo migrated to scenarios
2. **100% validation** - Every step has assertions
3. **<5s latency** on polling (no arbitrary sleeps)
4. **HTML reports** generated for every run
5. **YAML-driven** - New scenarios without code changes
6. **Parallel execution** for independent scenarios
7. **CI/CD ready** - Exit codes, JSON reports
8. **Performance baseline** established

---

## Estimated Effort

| Phase | Effort | Priority |
|-------|--------|----------|
| Phase 1: Core Infrastructure | 3-4 days | P0 |
| Phase 2: Scenario System | 3-4 days | P0 |
| Phase 3: Data-Driven | 2-3 days | P1 |
| Phase 4: Rich Reporting | 2-3 days | P1 |
| Phase 5: Advanced Features | 3-4 days | P2 |
| Phase 6: CLI | 1-2 days | P1 |
| Phase 7: Additional Scenarios | 4-5 days | P2 |

**Total: ~20-25 days**

---

## Appendix: Key Code Patterns

### Pattern: State Polling
```python
# Instead of:
await asyncio.sleep(10)  # Hope it's ready

# Use:
await wait_for_condition(
    lambda: check_position_status(client, symbol, "active"),
    timeout=30.0,
    description="position to become active"
)
```

### Pattern: Validation Chain
```python
# Chain multiple validations
results = await asyncio.gather(
    validator.validate_position_exists(client, "SOL/USDT"),
    validator.validate_pyramid_count(client, "SOL/USDT", 2),
    validator.validate_pnl_range(client, "SOL/USDT", -5, 5),
)
all_passed = all(r.passed for r in results)
```

### Pattern: Scenario Dependencies
```python
class RiskExecutionScenario(BaseScenario):
    depends_on = ["RiskSetupScenario", "WaitForTimerScenario"]

    async def setup(self):
        # Verify prerequisites
        if not await self.verify_loser_exists():
            raise PreconditionFailed("No eligible loser found")
```