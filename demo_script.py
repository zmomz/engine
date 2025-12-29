#!/usr/bin/env python3
"""
Trading Engine Live Demo Script
================================
A comprehensive demo script for Zoom presentations showing the full trading engine journey.

Features demonstrated:
- Phase 1: Clean Slate & Account Setup
- Phase 2: DCA Configuration Setup
- Phase 3: Mock Exchange Price Setup
- Phase 4: Fill Execution Pool (3 positions)
- Phase 5: Queue Demonstration
- Phase 6: Pyramid Continuation
- Phase 7: DCA Order Fills via Price Movement
- Phase 8: Risk Timer Activation
- Phase 9: Risk Engine Execution (offset)
- Phase 10: Queue Promotion After Slot Release
- Phase 11: TP Mode & Exit Signal Demonstration
- Phase 12: History & Analytics Review
- Phase 13: Manual Risk Controls Demo

Prerequisites:
    pip install httpx

Usage:
    python demo_script.py [--phase N] [--auto] [--delay 3]

    Options:
        --phase N       Start from phase N (default: 1)
        --auto          Auto-continue without pausing between phases
        --delay N       Delay in seconds between auto steps (default: 3)
        --username      Demo user username (default: zmomz)
        --password      Demo user password (default: zm0mzzm0mz)
        --engine-url    Trading engine URL (default: http://127.0.0.1:8000)
        --mock-url      Mock exchange URL (default: http://127.0.0.1:9000)

Examples:
    # Run full demo interactively
    python demo_script.py

    # Run from phase 5 onwards
    python demo_script.py --phase 5

    # Run in auto mode with 5 second delays
    python demo_script.py --auto --delay 5
"""

import asyncio
import json
import sys
import time
import argparse
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

# Check for required dependency
try:
    import httpx
except ImportError:
    print("ERROR: httpx is required but not installed.")
    print("Install it with: pip install httpx")
    print("Or if using the backend venv: .venv\\Scripts\\pip install httpx")
    sys.exit(1)


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class DemoConfig:
    """All configurable values for the demo."""

    # URLs
    engine_url: str = "http://127.0.0.1:8000"
    mock_exchange_url: str = "http://127.0.0.1:9000"

    # Demo User Credentials (create this user before demo)
    username: str = "demo_user"
    password: str = "demo_password"
    user_id: str = "00000000-0000-0000-0000-000000000001"  # Will be updated after login
    webhook_secret: str = ""  # Will be fetched from user settings after login

    # Risk Engine Config
    max_open_positions_global: int = 3
    max_pyramids: int = 2
    required_pyramids_for_timer: int = 2
    post_pyramids_wait_minutes: int = 1  # Short for demo (1 minute)
    loss_threshold_percent: float = -1.5

    # Mock Exchange API Keys
    mock_api_key: str = "mock_api_key_12345"
    mock_api_secret: str = "mock_api_secret_67890"

    # Trading Pairs (20 symbols)
    symbols: List[str] = field(default_factory=lambda: [
        "BTCUSDT", "ETHUSDT", "SOLUSDT", "ADAUSDT", "XRPUSDT",
        "DOGEUSDT", "LINKUSDT", "AVAXUSDT", "DOTUSDT", "MATICUSDT",
        "UNIUSDT", "ATOMUSDT", "LTCUSDT", "ETCUSDT", "NEARUSDT",
        "APTUSDT", "ARBUSDT", "OPUSDT", "INJUSDT", "SUIUSDT"
    ])

    # Initial Prices (for Mock Exchange)
    initial_prices: Dict[str, float] = field(default_factory=lambda: {
        "BTCUSDT": 95000.0,
        "ETHUSDT": 3400.0,
        "SOLUSDT": 200.0,
        "ADAUSDT": 0.90,
        "XRPUSDT": 2.20,
        "DOGEUSDT": 0.32,
        "LINKUSDT": 22.0,
        "AVAXUSDT": 38.0,
        "DOTUSDT": 7.5,
        "MATICUSDT": 0.85,
        "UNIUSDT": 13.0,
        "ATOMUSDT": 9.0,
        "LTCUSDT": 105.0,
        "ETCUSDT": 27.0,
        "NEARUSDT": 5.0,
        "APTUSDT": 9.5,
        "ARBUSDT": 0.80,
        "OPUSDT": 1.90,
        "INJUSDT": 25.0,
        "SUIUSDT": 4.2,
    })

    # Presentation timings
    pause_between_phases: bool = True
    auto_continue_delay: float = 3.0  # seconds


# =============================================================================
# HTTP CLIENTS
# =============================================================================

class MockExchangeClient:
    """Client for Mock Exchange Admin API."""

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = httpx.AsyncClient(base_url=base_url, timeout=30.0)

    async def health_check(self) -> bool:
        """Check if mock exchange is running."""
        try:
            resp = await self.client.get("/health")
            return resp.status_code == 200
        except Exception:
            return False

    async def reset_exchange(self) -> Dict:
        """Reset all orders, positions, trades."""
        resp = await self.client.delete("/admin/reset")
        resp.raise_for_status()
        return resp.json()

    async def get_symbols(self) -> List[Dict]:
        """Get all available symbols."""
        resp = await self.client.get("/admin/symbols")
        resp.raise_for_status()
        return resp.json()

    async def set_price(self, symbol: str, price: float) -> Dict:
        """Set price for a symbol."""
        resp = await self.client.put(
            f"/admin/symbols/{symbol}/price",
            json={"price": price}
        )
        resp.raise_for_status()
        return resp.json()

    async def get_all_orders(self, status: str = None, symbol: str = None) -> List[Dict]:
        """Get all orders with optional filters."""
        params = {}
        if status:
            params["status"] = status
        if symbol:
            params["symbol"] = symbol
        resp = await self.client.get("/admin/orders", params=params)
        resp.raise_for_status()
        return resp.json()

    async def fill_order(self, order_id: str, fill_price: float = None) -> Dict:
        """Manually fill an order."""
        params = {}
        if fill_price:
            params["fill_price"] = fill_price
        resp = await self.client.post(f"/admin/orders/{order_id}/fill", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_positions(self) -> List[Dict]:
        """Get all positions on mock exchange."""
        resp = await self.client.get("/admin/positions")
        resp.raise_for_status()
        return resp.json()

    async def get_balances(self) -> List[Dict]:
        """Get all balances."""
        resp = await self.client.get("/admin/balances")
        resp.raise_for_status()
        return resp.json()

    async def close(self):
        await self.client.aclose()


class EngineClient:
    """Client for Trading Engine API."""

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = httpx.AsyncClient(base_url=base_url, timeout=60.0)
        self.access_token: Optional[str] = None
        self.user_id: Optional[str] = None

    async def health_check(self) -> bool:
        """Check if engine is running by testing login endpoint availability."""
        try:
            # Try the API endpoint - /health may serve frontend HTML
            resp = await self.client.get("/api/v1/settings/exchanges")
            # Even 401 means the API is running
            return resp.status_code in (200, 401, 403)
        except Exception:
            return False

    async def login(self, username: str, password: str) -> Dict:
        """Login and get access token."""
        resp = await self.client.post(
            "/api/v1/users/login",
            data={"username": username, "password": password}
        )
        resp.raise_for_status()
        data = resp.json()
        self.access_token = data.get("access_token")
        if data.get("user"):
            self.user_id = str(data["user"]["id"])
        return data

    def _headers(self) -> Dict:
        """Get auth headers."""
        if self.access_token:
            return {"Authorization": f"Bearer {self.access_token}"}
        return {}

    async def get_settings(self) -> Dict:
        """Get user settings."""
        resp = await self.client.get("/api/v1/settings", headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    async def update_settings(self, settings: Dict) -> Dict:
        """Update user settings."""
        resp = await self.client.put(
            "/api/v1/settings",
            headers=self._headers(),
            json=settings
        )
        resp.raise_for_status()
        return resp.json()

    async def get_dca_configs(self) -> List[Dict]:
        """Get all DCA configurations."""
        resp = await self.client.get("/api/v1/dca-configs/", headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    async def create_dca_config(self, config: Dict) -> Dict:
        """Create a DCA configuration."""
        resp = await self.client.post(
            "/api/v1/dca-configs/",
            headers=self._headers(),
            json=config
        )
        resp.raise_for_status()
        return resp.json()

    async def delete_dca_config(self, config_id: str) -> Dict:
        """Delete a DCA configuration."""
        resp = await self.client.delete(
            f"/api/v1/dca-configs/{config_id}",
            headers=self._headers()
        )
        resp.raise_for_status()
        return resp.json()

    async def get_active_positions(self) -> List[Dict]:
        """Get all active positions."""
        resp = await self.client.get("/api/v1/positions/active", headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    async def get_position_history(self, limit: int = 100) -> Dict:
        """Get position history."""
        resp = await self.client.get(
            "/api/v1/positions/history",
            headers=self._headers(),
            params={"limit": limit}
        )
        resp.raise_for_status()
        return resp.json()

    async def close_position(self, group_id: str) -> Dict:
        """Force close a position."""
        resp = await self.client.post(
            f"/api/v1/positions/{group_id}/close",
            headers=self._headers()
        )
        resp.raise_for_status()
        return resp.json()

    async def get_queue(self) -> List[Dict]:
        """Get queued signals."""
        resp = await self.client.get("/api/v1/queue/", headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    async def promote_queued_signal(self, signal_id: str) -> Dict:
        """Promote a signal from queue."""
        resp = await self.client.post(
            f"/api/v1/queue/{signal_id}/promote",
            headers=self._headers()
        )
        resp.raise_for_status()
        return resp.json()

    async def remove_queued_signal(self, signal_id: str) -> Dict:
        """Remove a signal from queue."""
        resp = await self.client.delete(
            f"/api/v1/queue/{signal_id}",
            headers=self._headers()
        )
        resp.raise_for_status()
        return resp.json()

    async def get_risk_status(self) -> Dict:
        """Get risk engine status."""
        resp = await self.client.get("/api/v1/risk/status", headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    async def run_risk_evaluation(self) -> Dict:
        """Trigger risk evaluation."""
        resp = await self.client.post("/api/v1/risk/run-evaluation", headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    async def block_position_risk(self, group_id: str) -> Dict:
        """Block position from risk engine."""
        resp = await self.client.post(
            f"/api/v1/risk/{group_id}/block",
            headers=self._headers()
        )
        resp.raise_for_status()
        return resp.json()

    async def unblock_position_risk(self, group_id: str) -> Dict:
        """Unblock position from risk engine."""
        resp = await self.client.post(
            f"/api/v1/risk/{group_id}/unblock",
            headers=self._headers()
        )
        resp.raise_for_status()
        return resp.json()

    async def force_stop_engine(self) -> Dict:
        """Force stop the engine."""
        resp = await self.client.post("/api/v1/risk/force-stop", headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    async def force_start_engine(self) -> Dict:
        """Force start the engine."""
        resp = await self.client.post("/api/v1/risk/force-start", headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    async def send_webhook(self, payload: Dict) -> Dict:
        """Send a webhook signal (direct to engine)."""
        user_id = payload.get("user_id", self.user_id)
        resp = await self.client.post(
            f"/api/v1/webhooks/{user_id}/tradingview",
            json=payload,
            timeout=60.0
        )
        resp.raise_for_status()
        return resp.json()

    async def get_dashboard_summary(self) -> Dict:
        """Get dashboard summary."""
        resp = await self.client.get("/api/v1/dashboard/summary", headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    async def close(self):
        await self.client.aclose()


# =============================================================================
# WEBHOOK PAYLOAD BUILDER
# =============================================================================

def build_webhook_payload(
    user_id: str,
    secret: str,
    symbol: str,
    action: str,  # "buy" or "sell"
    market_position: str,  # "long", "short", "flat"
    position_size: float,
    entry_price: float,
    prev_market_position: str = "flat",
    prev_position_size: float = 0,
    trade_id: str = None,
    alert_name: str = None,
    timeframe: int = 60,
) -> Dict:
    """Build a TradingView-style webhook payload."""
    return {
        "user_id": user_id,
        "secret": secret,
        "source": "tradingview",
        "timestamp": datetime.utcnow().isoformat(),
        "tv": {
            "exchange": "mock",
            "symbol": symbol.replace("USDT", "/USDT"),
            "timeframe": timeframe,
            "action": action,
            "market_position": market_position,
            "market_position_size": position_size,
            "prev_market_position": prev_market_position,
            "prev_market_position_size": prev_position_size,
            "entry_price": entry_price,
            "close_price": entry_price,
            "order_size": position_size,
        },
        "strategy_info": {
            "trade_id": trade_id or f"demo_{symbol}_{int(time.time())}",
            "alert_name": alert_name or f"Demo {symbol}",
            "alert_message": f"Demo signal for {symbol}",
        },
        "execution_intent": {
            "type": "signal",
            "side": action,
            "position_size_type": "quote",
            "precision_mode": "auto",
        },
        "risk": {
            "max_slippage_percent": 1.0,
        },
    }


# =============================================================================
# DISPLAY UTILITIES
# =============================================================================

class Colors:
    """ANSI color codes for terminal output."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"


def print_header(text: str, char: str = "="):
    """Print a section header."""
    width = 80
    print(f"\n{Colors.CYAN}{Colors.BOLD}{char * width}")
    print(f"  {text}")
    print(f"{char * width}{Colors.RESET}\n")


def print_subheader(text: str):
    """Print a subsection header."""
    print(f"\n{Colors.YELLOW}{Colors.BOLD}>>> {text}{Colors.RESET}")


def print_success(text: str):
    """Print success message."""
    print(f"{Colors.GREEN}[OK] {text}{Colors.RESET}")


def print_error(text: str):
    """Print error message."""
    print(f"{Colors.RED}[ERROR] {text}{Colors.RESET}")


def print_warning(text: str):
    """Print warning message."""
    print(f"{Colors.YELLOW}[WARN] {text}{Colors.RESET}")


def print_info(text: str):
    """Print info message."""
    print(f"{Colors.BLUE}[INFO] {text}{Colors.RESET}")


def print_table(headers: List[str], rows: List[List[Any]], title: str = None):
    """Print a formatted table."""
    if title:
        print(f"\n{Colors.MAGENTA}{Colors.BOLD}{title}{Colors.RESET}")

    # Calculate column widths
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))

    # Print header
    header_line = " | ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers))
    print(f"{Colors.BOLD}{header_line}{Colors.RESET}")
    print("-" * (sum(widths) + 3 * (len(headers) - 1)))

    # Print rows
    for row in rows:
        row_line = " | ".join(str(cell).ljust(widths[i]) for i, cell in enumerate(row))
        print(row_line)
    print()


def format_price(price: float, decimals: int = 2) -> str:
    """Format price with proper decimal places."""
    if price >= 1000:
        return f"${price:,.{decimals}f}"
    elif price >= 1:
        return f"${price:.{decimals}f}"
    else:
        return f"${price:.6f}"


def format_pnl(pnl: float) -> str:
    """Format PnL with color."""
    if pnl >= 0:
        return f"{Colors.GREEN}+${pnl:.2f}{Colors.RESET}"
    else:
        return f"{Colors.RED}-${abs(pnl):.2f}{Colors.RESET}"


# =============================================================================
# VERIFICATION HELPERS
# =============================================================================

async def verify_positions(engine: EngineClient, expected_count: int = None) -> List[Dict]:
    """Verify and display active positions."""
    positions = await engine.get_active_positions()

    if expected_count is not None and len(positions) != expected_count:
        print_warning(f"Expected {expected_count} positions, found {len(positions)}")

    if positions:
        rows = []
        for pos in positions:
            # Handle string or numeric values from API
            qty = pos.get('total_filled_quantity', 0)
            qty_val = float(qty) if qty else 0
            avg_entry = pos.get("weighted_avg_entry", 0)
            avg_entry_val = float(avg_entry) if avg_entry else 0
            pnl_pct = pos.get('unrealized_pnl_percent', 0)
            pnl_pct_val = float(pnl_pct) if pnl_pct else 0

            rows.append([
                pos.get("symbol", "N/A"),
                pos.get("side", "N/A"),
                pos.get("pyramid_count", 0),
                f"{qty_val:.4f}",
                format_price(avg_entry_val),
                f"{pnl_pct_val:.2f}%",
                pos.get("status", "N/A"),
                "Yes" if pos.get("risk_eligible", False) else "No",
            ])
        print_table(
            ["Symbol", "Side", "Pyramids", "Qty", "Avg Entry", "PnL %", "Status", "Risk Eligible"],
            rows,
            title="Active Positions"
        )
    else:
        print_info("No active positions")

    return positions


async def verify_queue(engine: EngineClient, expected_count: int = None) -> List[Dict]:
    """Verify and display queue status."""
    queue = await engine.get_queue()

    if expected_count is not None and len(queue) != expected_count:
        print_warning(f"Expected {expected_count} queued signals, found {len(queue)}")

    if queue:
        rows = []
        for sig in queue:
            rows.append([
                sig.get("symbol", "N/A"),
                sig.get("side", "N/A"),
                sig.get("replacement_count", 0),
                sig.get("priority", 0),
                sig.get("status", "N/A"),
            ])
        print_table(
            ["Symbol", "Side", "Replacements", "Priority", "Status"],
            rows,
            title="Queue Status"
        )
    else:
        print_info("Queue is empty")

    return queue


async def verify_mock_exchange_orders(mock: MockExchangeClient, status: str = None) -> List[Dict]:
    """Verify and display mock exchange orders."""
    orders = await mock.get_all_orders(status=status)

    if orders:
        rows = []
        for order in orders[:20]:  # Limit display
            rows.append([
                str(order.get("orderId", "N/A"))[:10],
                order.get("symbol", "N/A"),
                order.get("side", "N/A"),
                order.get("type", "N/A"),
                f"{order.get('price', 0):.2f}",
                f"{order.get('quantity', 0):.4f}",
                order.get("status", "N/A"),
            ])
        print_table(
            ["Order ID", "Symbol", "Side", "Type", "Price", "Qty", "Status"],
            rows,
            title=f"Mock Exchange Orders ({status or 'All'})"
        )
    else:
        print_info(f"No orders found with status: {status or 'any'}")

    return orders


async def verify_risk_status(engine: EngineClient) -> Dict:
    """Verify and display risk engine status."""
    status = await engine.get_risk_status()

    print_table(
        ["Metric", "Value"],
        [
            ["Status", status.get("status", "N/A")],
            ["Active Positions", status.get("active_positions", 0)],
            ["Risk Level", status.get("risk_level", "N/A")],
            ["Eligible Losers", len(status.get("eligible_losers", []))],
            ["Eligible Winners", len(status.get("eligible_winners", []))],
        ],
        title="Risk Engine Status"
    )

    return status


# =============================================================================
# DEMO RUNNER
# =============================================================================

class DemoRunner:
    """Main demo runner class."""

    def __init__(self, config: DemoConfig):
        self.config = config
        self.mock = MockExchangeClient(config.mock_exchange_url)
        self.engine = EngineClient(config.engine_url)
        self.position_ids: Dict[str, str] = {}  # symbol -> position_group_id

    async def setup(self) -> bool:
        """Initialize connections and verify services."""
        print_header("DEMO SETUP", "=")

        # Check Mock Exchange
        print_info("Checking Mock Exchange...")
        if not await self.mock.health_check():
            print_error("Mock Exchange is not running!")
            print_info("Please start with: docker compose up mock-exchange")
            return False
        print_success("Mock Exchange is running")

        # Check Engine
        print_info("Checking Trading Engine...")
        if not await self.engine.health_check():
            print_error("Trading Engine is not running!")
            print_info("Please start with: docker compose up app")
            return False
        print_success("Trading Engine is running")

        return True

    async def pause_for_presenter(self, message: str = "Press Enter to continue..."):
        """Pause for presenter to explain."""
        if self.config.pause_between_phases:
            print(f"\n{Colors.YELLOW}{Colors.BOLD}{message}{Colors.RESET}")
            await asyncio.get_event_loop().run_in_executor(None, input)

    async def auto_pause(self, seconds: float = None):
        """Auto-pause with countdown for demo."""
        delay = seconds or self.config.auto_continue_delay
        print_info(f"Continuing in {delay} seconds...")
        await asyncio.sleep(delay)

    # -------------------------------------------------------------------------
    # PHASE 1: Clean Slate & Account Setup
    # -------------------------------------------------------------------------
    async def phase_1_clean_slate(self):
        """Phase 1: Reset everything and login."""
        print_header("PHASE 1: CLEAN SLATE & ACCOUNT SETUP")

        # 1.1 Reset Mock Exchange
        print_subheader("Step 1.1: Reset Mock Exchange")
        result = await self.mock.reset_exchange()
        print_success(f"Mock Exchange reset: {result.get('message', 'OK')}")

        # 1.2 Verify symbols available
        print_subheader("Step 1.2: Verify Mock Exchange Symbols")
        symbols = await self.mock.get_symbols()
        symbol_names = [s["symbol"] for s in symbols]
        print_success(f"Found {len(symbols)} symbols: {', '.join(symbol_names[:10])}...")

        # 1.3 Login to Engine
        print_subheader("Step 1.3: Login to Trading Engine")
        try:
            login_result = await self.engine.login(self.config.username, self.config.password)
            self.config.user_id = self.engine.user_id
            print_success(f"Logged in as: {self.config.username}")
            print_info(f"User ID: {self.config.user_id}")

            # Fetch webhook secret from user settings
            user_settings = await self.engine.get_settings()
            self.config.webhook_secret = user_settings.get("webhook_secret", "")
            if self.config.webhook_secret:
                print_success(f"Webhook secret retrieved: {self.config.webhook_secret[:8]}...")
            else:
                print_warning("No webhook secret found in user settings")
        except httpx.HTTPStatusError as e:
            print_error(f"Login failed: {e}")
            print_info("Please create the demo user first")
            return False

        # 1.4 Configure Exchange API Keys
        print_subheader("Step 1.4: Configure Mock Exchange API Keys")
        settings = await self.engine.update_settings({
            "exchange": "mock",
            "api_key": self.config.mock_api_key,
            "secret_key": self.config.mock_api_secret,
            "key_target_exchange": "mock",
        })
        print_success("Mock Exchange API keys configured")

        # 1.5 Configure Risk Settings
        print_subheader("Step 1.5: Configure Risk Engine")
        risk_config = {
            "risk_config": {
                "max_open_positions_global": self.config.max_open_positions_global,
                "max_open_positions_per_symbol": 1,
                "required_pyramids_for_timer": self.config.required_pyramids_for_timer,
                "post_pyramids_wait_minutes": self.config.post_pyramids_wait_minutes,
                "loss_threshold_percent": self.config.loss_threshold_percent,
                "max_winners_to_combine": 3,
            }
        }
        await self.engine.update_settings(risk_config)
        print_success(f"Risk config set: max_positions={self.config.max_open_positions_global}, "
                     f"pyramids={self.config.required_pyramids_for_timer}, timer={self.config.post_pyramids_wait_minutes}min")

        # 1.6 Close ALL existing positions for clean slate
        print_subheader("Step 1.6: Close All Existing Positions")
        existing_positions = await self.engine.get_active_positions()
        if existing_positions:
            for pos in existing_positions:
                try:
                    await self.engine.close_position(pos["id"])
                    print_info(f"Closed position: {pos.get('symbol', 'N/A')}")
                    await asyncio.sleep(1)  # Allow processing
                except httpx.HTTPStatusError as e:
                    print_warning(f"Could not close {pos.get('symbol', 'N/A')}: {e}")
            print_success(f"Closed {len(existing_positions)} existing positions")
        else:
            print_info("No existing positions to close")

        # Wait for positions to be fully closed
        await asyncio.sleep(3)

        # 1.7 Clear existing DCA configs
        print_subheader("Step 1.7: Clear Existing DCA Configurations")
        existing_configs = await self.engine.get_dca_configs()
        for cfg in existing_configs:
            await self.engine.delete_dca_config(cfg["id"])
            print_info(f"Deleted config: {cfg.get('pair', 'N/A')}")
        print_success(f"Cleared {len(existing_configs)} existing DCA configs")

        # 1.8 Clear queue
        print_subheader("Step 1.8: Clear Queue")
        queue = await self.engine.get_queue()
        for sig in queue:
            try:
                await self.engine.remove_queued_signal(sig["id"])
                print_info(f"Removed queued: {sig.get('symbol', 'N/A')}")
            except httpx.HTTPStatusError:
                pass
        print_success(f"Cleared {len(queue)} queued signals")

        # Verification
        print_subheader("Verification: Initial State")
        await verify_positions(self.engine, expected_count=0)
        await verify_queue(self.engine, expected_count=0)

        print_success("Phase 1 Complete: Clean slate established")
        return True

    # -------------------------------------------------------------------------
    # PHASE 2: DCA Configuration Setup
    # -------------------------------------------------------------------------
    async def phase_2_dca_setup(self):
        """Phase 2: Create DCA configurations for demo symbols."""
        print_header("PHASE 2: DCA CONFIGURATION SETUP")

        # Define DCA configs:
        # SOL = Loser with 3% TP (will trigger risk offset)
        # BTC = Winner with 20% TP (high to prevent premature closure)
        # ETH = Winner with 15% aggregate TP
        # Others = Standard configs for queue demo

        configs_to_create = [
            # SOL - LOSER (small TP so it won't close before risk offset)
            {
                "pair": "SOL/USDT",
                "timeframe": 60,
                "exchange": "mock",
                "entry_order_type": "market",
                "max_pyramids": self.config.max_pyramids,
                "tp_mode": "per_leg",
                "tp_settings": {"tp_aggregate_percent": 3.0},
                "dca_levels": [
                    {"gap_percent": 0, "weight_percent": 40, "tp_percent": 3},
                    {"gap_percent": -2, "weight_percent": 30, "tp_percent": 3},
                    {"gap_percent": -4, "weight_percent": 30, "tp_percent": 3},
                ],
            },
            # BTC - WINNER (high TP to prevent closure before offset)
            {
                "pair": "BTC/USDT",
                "timeframe": 60,
                "exchange": "mock",
                "entry_order_type": "market",
                "max_pyramids": self.config.max_pyramids,
                "tp_mode": "per_leg",
                "tp_settings": {"tp_aggregate_percent": 20.0},
                "dca_levels": [
                    {"gap_percent": 0, "weight_percent": 40, "tp_percent": 20},
                    {"gap_percent": -2, "weight_percent": 30, "tp_percent": 20},
                    {"gap_percent": -4, "weight_percent": 30, "tp_percent": 20},
                ],
            },
            # ETH - WINNER with aggregate TP mode
            {
                "pair": "ETH/USDT",
                "timeframe": 60,
                "exchange": "mock",
                "entry_order_type": "market",
                "max_pyramids": self.config.max_pyramids,
                "tp_mode": "aggregate",
                "tp_settings": {"tp_aggregate_percent": 15.0},
                "dca_levels": [
                    {"gap_percent": 0, "weight_percent": 40, "tp_percent": 15},
                    {"gap_percent": -2, "weight_percent": 30, "tp_percent": 15},
                    {"gap_percent": -4, "weight_percent": 30, "tp_percent": 15},
                ],
            },
            # ADA, XRP, DOGE, LINK, AVAX - Queue demo (use symbols available in mock exchange)
        ]

        # Add queue demo configs (all symbols available in mock exchange)
        for symbol in ["ADA/USDT", "XRP/USDT", "DOGE/USDT", "LINK/USDT", "AVAX/USDT", "TRX/USDT", "LTC/USDT"]:
            configs_to_create.append({
                "pair": symbol,
                "timeframe": 60,
                "exchange": "mock",
                "entry_order_type": "market",
                "max_pyramids": self.config.max_pyramids,
                "tp_mode": "per_leg",
                "tp_settings": {"tp_aggregate_percent": 10.0},
                "dca_levels": [
                    {"gap_percent": 0, "weight_percent": 40, "tp_percent": 10},
                    {"gap_percent": -2, "weight_percent": 30, "tp_percent": 10},
                    {"gap_percent": -4, "weight_percent": 30, "tp_percent": 10},
                ],
            })

        # Create configs
        print_subheader("Step 2.1: Create DCA Configurations")
        created_configs = []
        for cfg in configs_to_create:
            try:
                result = await self.engine.create_dca_config(cfg)
                created_configs.append(result)
                tp_mode = cfg.get("tp_mode", "per_leg")
                tp_pct = cfg.get("tp_settings", {}).get("tp_aggregate_percent",
                        cfg.get("dca_levels", [{}])[0].get("tp_percent", 0))
                print_success(f"Created: {cfg['pair']} | TP Mode: {tp_mode} | TP: {tp_pct}%")
            except httpx.HTTPStatusError as e:
                print_warning(f"Config for {cfg['pair']} may already exist: {e}")

        # Verification
        print_subheader("Verification: DCA Configurations")
        configs = await self.engine.get_dca_configs()
        rows = []
        for cfg in configs:
            rows.append([
                cfg.get("pair", "N/A"),
                cfg.get("entry_order_type", "N/A"),
                cfg.get("tp_mode", "N/A"),
                cfg.get("max_pyramids", 0),
                len(cfg.get("dca_levels", [])),
            ])
        print_table(
            ["Pair", "Entry Type", "TP Mode", "Max Pyramids", "DCA Levels"],
            rows,
            title="Configured DCA Settings"
        )

        print_success(f"Phase 2 Complete: {len(configs)} DCA configurations created")
        return True

    # -------------------------------------------------------------------------
    # PHASE 3: Mock Exchange Price Setup
    # -------------------------------------------------------------------------
    async def phase_3_price_setup(self):
        """Phase 3: Set initial prices on mock exchange."""
        print_header("PHASE 3: MOCK EXCHANGE PRICE SETUP")

        print_subheader("Step 3.1: Set Initial Prices")

        # All symbols available in mock exchange:
        # BTCUSDT, ETHUSDT, SOLUSDT, ADAUSDT, XRPUSDT, DOGEUSDT, LINKUSDT, TRXUSDT, LTCUSDT, AVAXUSDT
        prices_to_set = {
            "SOLUSDT": 200.0,    # SOL will become loser
            "BTCUSDT": 95000.0,  # BTC will become winner
            "ETHUSDT": 3400.0,   # ETH will become winner
            "ADAUSDT": 0.90,
            "XRPUSDT": 2.20,
            "DOGEUSDT": 0.32,
            "LINKUSDT": 22.0,
            "AVAXUSDT": 38.0,
            "TRXUSDT": 0.25,
            "LTCUSDT": 105.0,
        }

        for symbol, price in prices_to_set.items():
            result = await self.mock.set_price(symbol, price)
            print_success(f"{symbol}: {format_price(price)}")

        # Verification
        print_subheader("Verification: Current Mock Exchange Prices")
        symbols = await self.mock.get_symbols()
        rows = []
        for s in symbols:
            if s["symbol"] in prices_to_set:
                rows.append([
                    s["symbol"],
                    format_price(s["currentPrice"]),
                    s["tickSize"],
                    s["stepSize"],
                ])
        print_table(
            ["Symbol", "Price", "Tick Size", "Step Size"],
            rows,
            title="Mock Exchange Symbol Prices"
        )

        print_success("Phase 3 Complete: Prices configured")
        return True

    # -------------------------------------------------------------------------
    # PHASE 4: Fill Execution Pool
    # -------------------------------------------------------------------------
    async def phase_4_fill_pool(self):
        """Phase 4: Send 3 signals to fill the execution pool."""
        print_header("PHASE 4: FILL EXECUTION POOL")

        print_info(f"Pool capacity: {self.config.max_open_positions_global} positions")
        print_info("We will send 3 signals to fill the pool: SOL (loser), BTC (winner), ETH (winner)")

        signals = [
            ("SOL/USDT", "SOLUSDT", 200.0, 500),   # SOL entry
            ("BTC/USDT", "BTCUSDT", 95000.0, 500), # BTC entry
            ("ETH/USDT", "ETHUSDT", 3400.0, 500),  # ETH entry
        ]

        for i, (symbol, ex_symbol, price, size) in enumerate(signals, 1):
            print_subheader(f"Step 4.{i}: Send Entry Signal - {symbol}")

            payload = build_webhook_payload(
                user_id=self.config.user_id,
                secret=self.config.webhook_secret,
                symbol=ex_symbol,
                action="buy",
                market_position="long",
                position_size=size,
                entry_price=price,
                trade_id=f"pool_fill_{symbol}_{i}",
                alert_name=f"Pool Fill {symbol}",
            )

            try:
                result = await self.engine.send_webhook(payload)
                # The actual result is in the 'result' field, not 'message'
                response_msg = result.get("result", result.get("message", str(result)))
                if "error" in response_msg.lower() or "failed" in response_msg.lower() or "configuration" in response_msg.lower():
                    print_error(f"Signal REJECTED for {symbol}: {response_msg}")
                elif "created" in response_msg.lower():
                    print_success(f"Position created for {symbol}")
                elif "queued" in response_msg.lower():
                    print_warning(f"Signal queued (pool full?) for {symbol}: {response_msg}")
                else:
                    print_info(f"Response for {symbol}: {response_msg}")
            except httpx.HTTPStatusError as e:
                print_error(f"Signal failed for {symbol}: {e}")

            await asyncio.sleep(1)  # Allow processing

        # Wait for orders to be created
        print_info("Waiting for order processing...")
        await asyncio.sleep(3)

        # Verification
        print_subheader("Verification: Pool State After Entry Signals")
        positions = await verify_positions(self.engine, expected_count=3)

        # Store position IDs
        for pos in positions:
            self.position_ids[pos["symbol"]] = pos["id"]

        await verify_mock_exchange_orders(self.mock, status="NEW")

        print_success("Phase 4 Complete: Execution pool filled with 3 positions")
        return True

    # -------------------------------------------------------------------------
    # PHASE 5: Queue Demonstration
    # -------------------------------------------------------------------------
    async def phase_5_queue_demo(self):
        """Phase 5: Send more signals to demonstrate queue behavior."""
        print_header("PHASE 5: QUEUE DEMONSTRATION")

        # First verify pool is actually full
        positions = await self.engine.get_active_positions()
        print_info(f"Current pool: {len(positions)}/{self.config.max_open_positions_global} positions")

        if len(positions) < self.config.max_open_positions_global:
            print_warning(f"Pool not full yet. Need {self.config.max_open_positions_global - len(positions)} more positions.")
            print_info("Sending additional signals to fill the pool first...")

            # Fill remaining slots
            fill_symbols = [
                ("LINK/USDT", "LINKUSDT", 22.0, 300),
                ("AVAX/USDT", "AVAXUSDT", 38.0, 300),
                ("LTC/USDT", "LTCUSDT", 105.0, 300),
            ]

            slots_needed = self.config.max_open_positions_global - len(positions)
            for i, (symbol, ex_symbol, price, size) in enumerate(fill_symbols[:slots_needed]):
                payload = build_webhook_payload(
                    user_id=self.config.user_id,
                    secret=self.config.webhook_secret,
                    symbol=ex_symbol,
                    action="buy",
                    market_position="long",
                    position_size=size,
                    entry_price=price,
                    trade_id=f"pool_fill_extra_{symbol}",
                )
                try:
                    await self.engine.send_webhook(payload)
                    print_info(f"Sent fill signal for {symbol}")
                except httpx.HTTPStatusError:
                    pass
                await asyncio.sleep(1)

            await asyncio.sleep(3)
            positions = await self.engine.get_active_positions()
            print_info(f"Pool now: {len(positions)}/{self.config.max_open_positions_global}")

        print_info("Pool is full. New signals will be queued.")
        print_info("We will send 3 new signals and demonstrate replacement priority.")

        # Send signals that will be queued (use symbols NOT already in pool)
        # Check which symbols are already in pool
        pool_symbols = {pos.get("symbol", "").replace("/", "") for pos in positions}

        queue_signals = [
            ("ADA/USDT", "ADAUSDT", 0.90, 300),
            ("XRP/USDT", "XRPUSDT", 2.20, 300),
            ("DOGE/USDT", "DOGEUSDT", 0.32, 300),
            ("TRX/USDT", "TRXUSDT", 0.25, 300),
        ]

        # Filter out symbols already in pool
        queue_signals = [(s, e, p, sz) for s, e, p, sz in queue_signals if e not in pool_symbols][:3]

        for i, (symbol, ex_symbol, price, size) in enumerate(queue_signals, 1):
            print_subheader(f"Step 5.{i}: Send Signal (Will Queue) - {symbol}")

            payload = build_webhook_payload(
                user_id=self.config.user_id,
                secret=self.config.webhook_secret,
                symbol=ex_symbol,
                action="buy",
                market_position="long",
                position_size=size,
                entry_price=price,
                trade_id=f"queue_{symbol}_{i}",
            )

            try:
                result = await self.engine.send_webhook(payload)
                # The actual result is in the 'result' field, not 'message'
                response_msg = result.get("result", result.get("message", str(result)))
                # Check if it was actually queued vs executed vs rejected
                if "queued" in response_msg.lower():
                    print_success(f"Signal QUEUED for {symbol}")
                elif "created" in response_msg.lower() or "executed" in response_msg.lower():
                    print_warning(f"Signal EXECUTED (not queued): {response_msg}")
                elif "error" in response_msg.lower() or "failed" in response_msg.lower() or "configuration" in response_msg.lower():
                    print_error(f"Signal REJECTED: {response_msg}")
                else:
                    print_info(f"Response: {response_msg}")
            except httpx.HTTPStatusError as e:
                print_error(f"Signal failed: {e}")

            await asyncio.sleep(1)

        # Verify queue
        print_subheader("Verification: Queue State")
        queue = await verify_queue(self.engine, expected_count=3)

        # Demonstrate replacement (send same symbol again)
        print_subheader("Step 5.4: Demonstrate Replacement Priority")
        print_info("Sending another ADA signal - this will REPLACE the existing queued signal")
        print_info("The replacement_count will increase, boosting priority")

        payload = build_webhook_payload(
            user_id=self.config.user_id,
            secret=self.config.webhook_secret,
            symbol="ADAUSDT",
            action="buy",
            market_position="long",
            position_size=350,  # Different size
            entry_price=0.88,   # Updated price
            trade_id="queue_ADA_replacement",
        )

        try:
            result = await self.engine.send_webhook(payload)
            print_success("ADA replacement signal sent")
        except httpx.HTTPStatusError as e:
            print_error(f"Replacement failed: {e}")

        await asyncio.sleep(2)

        # Verify updated queue
        print_subheader("Verification: Queue After Replacement")
        await verify_queue(self.engine)

        print_success("Phase 5 Complete: Queue demonstration with 3 signals + replacement")
        return True

    # -------------------------------------------------------------------------
    # PHASE 6: Pyramid Continuation
    # -------------------------------------------------------------------------
    async def phase_6_pyramids(self):
        """Phase 6: Demonstrate pyramid signals bypassing pool limit."""
        print_header("PHASE 6: PYRAMID CONTINUATION (BYPASSES POOL)")

        print_info("Pyramids are continuation signals for existing positions")
        print_info("They bypass the pool limit because the position already exists")

        # Send pyramid for SOL (existing position)
        print_subheader("Step 6.1: Send Pyramid Signal for SOL")
        print_info("SOL already has 1 entry (pyramid_count=0). This adds pyramid #1")

        # First, lower SOL price to simulate dip for pyramid
        await self.mock.set_price("SOLUSDT", 196.0)  # -2% from 200
        print_info("SOL price dropped to $196 (-2%)")

        payload = build_webhook_payload(
            user_id=self.config.user_id,
            secret=self.config.webhook_secret,
            symbol="SOLUSDT",
            action="buy",
            market_position="long",
            position_size=500,
            entry_price=196.0,
            prev_market_position="long",
            prev_position_size=500,
            trade_id="sol_pyramid_1",
        )

        try:
            result = await self.engine.send_webhook(payload)
            print_success("SOL pyramid #1 signal sent")
        except httpx.HTTPStatusError as e:
            print_error(f"Pyramid failed: {e}")

        await asyncio.sleep(2)

        # Send second pyramid for SOL
        print_subheader("Step 6.2: Send Pyramid Signal #2 for SOL")
        await self.mock.set_price("SOLUSDT", 192.0)  # -4% from 200
        print_info("SOL price dropped to $192 (-4%)")

        payload = build_webhook_payload(
            user_id=self.config.user_id,
            secret=self.config.webhook_secret,
            symbol="SOLUSDT",
            action="buy",
            market_position="long",
            position_size=500,
            entry_price=192.0,
            prev_market_position="long",
            prev_position_size=500,
            trade_id="sol_pyramid_2",
        )

        try:
            result = await self.engine.send_webhook(payload)
            print_success("SOL pyramid #2 signal sent")
        except httpx.HTTPStatusError as e:
            print_error(f"Pyramid failed: {e}")

        await asyncio.sleep(2)

        # Verification
        print_subheader("Verification: Position State After Pyramids")
        positions = await verify_positions(self.engine)

        # Check SOL position specifically
        sol_pos = next((p for p in positions if "SOL" in p.get("symbol", "")), None)
        if sol_pos:
            print_info(f"SOL Position: pyramid_count={sol_pos.get('pyramid_count', 0)}")

        # Also verify pool is still 3 (pyramids don't add to pool)
        print_info(f"Pool size: {len(positions)} (unchanged - pyramids don't count as new positions)")

        print_success("Phase 6 Complete: Pyramids added to existing SOL position")
        return True

    # -------------------------------------------------------------------------
    # PHASE 7: DCA Order Fills
    # -------------------------------------------------------------------------
    async def phase_7_dca_fills(self):
        """Phase 7: Fill DCA orders by moving prices."""
        print_header("PHASE 7: DCA ORDER FILLS VIA PRICE MOVEMENT")

        print_info("DCA orders are placed at specific price levels below entry")
        print_info("We will move prices to trigger order fills on the mock exchange")

        # Get current open orders
        print_subheader("Step 7.1: Check Pending DCA Orders")
        orders = await verify_mock_exchange_orders(self.mock, status="NEW")

        # Move SOL price down progressively to fill ALL DCA orders
        print_subheader("Step 7.2: Drop SOL Price to Fill DCA Orders")

        # Drop price aggressively to ensure all DCA orders fill
        dca_prices = [195.0, 190.0, 185.0, 180.0, 175.0, 170.0]  # Progressive DCA fills
        for i, price in enumerate(dca_prices, 1):
            print_info(f"Setting SOL price to ${price}")
            result = await self.mock.set_price("SOLUSDT", price)
            filled = result.get("filledOrders", [])
            if filled:
                print_success(f"Price set. Orders filled: {len(filled) if isinstance(filled, list) else filled}")
            else:
                print_info(f"Price set to ${price} - checking for fills...")
            await asyncio.sleep(2)  # Give time for order fill monitor

        # Give order fill monitor time to process
        print_info("Waiting for order fill monitor to process fills...")
        await asyncio.sleep(5)

        # Check if there are still unfilled orders
        print_subheader("Step 7.3: Verify All Orders Filled")
        remaining_orders = await self.mock.get_all_orders(status="NEW")
        sol_orders = [o for o in remaining_orders if o.get("symbol") == "SOLUSDT"]
        if sol_orders:
            print_warning(f"Still {len(sol_orders)} unfilled SOL orders - dropping price further")
            # Drop price to very low to fill remaining
            await self.mock.set_price("SOLUSDT", 150.0)
            await asyncio.sleep(5)

        # Verification
        print_subheader("Verification: Orders After Price Movement")
        await verify_mock_exchange_orders(self.mock, status="FILLED")

        # Check position status - need to see if all DCAs filled
        print_subheader("Verification: Position State After DCA Fills")
        positions = await verify_positions(self.engine)

        # Check SOL specifically
        sol_pos = next((p for p in positions if "SOL" in p.get("symbol", "")), None)
        if sol_pos:
            status = sol_pos.get("status", "N/A")
            pyramid_count = sol_pos.get("pyramid_count", 0)
            filled_legs = sol_pos.get("filled_dca_legs", 0)
            total_legs = sol_pos.get("total_dca_legs", 0)
            print_info(f"SOL Status: {status}, Pyramids: {pyramid_count}, DCA: {filled_legs}/{total_legs} legs filled")

        print_success("Phase 7 Complete: DCA orders filled via price movement")
        return True

    # -------------------------------------------------------------------------
    # PHASE 8: Risk Timer Activation
    # -------------------------------------------------------------------------
    async def phase_8_risk_timer(self):
        """Phase 8: Activate risk timer for SOL position."""
        print_header("PHASE 8: RISK TIMER ACTIVATION")

        print_info("Risk timer starts when:")
        print_info(f"  1. Position has {self.config.required_pyramids_for_timer}+ pyramids (all DCAs filled)")
        print_info(f"  2. Position is losing more than {self.config.loss_threshold_percent}%")
        print_info(f"  3. Timer runs for {self.config.post_pyramids_wait_minutes} minute(s)")

        # Make SOL a loser - but keep loss moderate so winners can cover it
        # After Phase 7 DCA fills, SOL avg entry is ~$192 with ~$1500 invested (~7.8 SOL)
        # We need combined winner profit >= SOL loss
        #
        # Strategy: Keep SOL loss small (-2%) and make winners very profitable (+50%)
        # SOL: -2% of $1500 = ~$30 loss
        # BTC: +50% of $200 = $100 profit
        # ETH: +50% of $200 = $100 profit
        # Combined: $200 profit >> $30 loss ✓
        print_subheader("Step 8.1: Make SOL a Moderate Loser")
        await self.mock.set_price("SOLUSDT", 188.0)  # ~-2.1% from avg entry ~192
        print_success("SOL price set to $188 (~-2% loss, ~$30 loss on ~$1500 invested)")

        # Make BTC and ETH winners with SIGNIFICANT profit (+50%)
        # BTC entry: $95,000 with ~$200 invested (~0.0021 BTC)
        # ETH entry: $3,400 with ~$200 invested (~0.059 ETH)
        # At +50%: BTC=$142,500, ETH=$5,100
        print_subheader("Step 8.2: Make BTC and ETH Winners (High Profit)")
        await self.mock.set_price("BTCUSDT", 142500.0)  # +50% from 95000
        await self.mock.set_price("ETHUSDT", 5100.0)    # +50% from 3400
        print_success("BTC: $142,500 (+50%, ~$100 profit)")
        print_success("ETH: $5,100 (+50%, ~$100 profit)")
        print_info("Combined winner profit: ~$200 >> SOL loss ~$30 ✓")

        await asyncio.sleep(2)

        # Verification
        print_subheader("Verification: Position PnL Status")
        positions = await verify_positions(self.engine)

        # Check SOL specifically for risk eligibility
        sol_pos = next((p for p in positions if "SOL" in p.get("symbol", "")), None)
        if sol_pos:
            pyramid_count = sol_pos.get("pyramid_count", 0)
            risk_eligible = sol_pos.get("risk_eligible", False)
            status = sol_pos.get("status", "N/A")
            pnl_pct = float(sol_pos.get("unrealized_pnl_percent", 0) or 0)

            print_info(f"SOL: pyramids={pyramid_count}, status={status}, risk_eligible={risk_eligible}, pnl={pnl_pct:.2f}%")

            if pyramid_count < self.config.required_pyramids_for_timer:
                print_warning(f"SOL needs {self.config.required_pyramids_for_timer} pyramids but has {pyramid_count}")
            if status != "active":
                print_warning(f"SOL status is '{status}' - needs 'active' (all DCAs filled) for risk timer")
            if pnl_pct > self.config.loss_threshold_percent:
                print_warning(f"SOL PnL {pnl_pct:.2f}% > threshold {self.config.loss_threshold_percent}%")

        # Check risk status
        print_subheader("Step 8.3: Check Risk Engine Status")
        risk_status = await verify_risk_status(self.engine)

        print_info(f"\nRisk timer will run for {self.config.post_pyramids_wait_minutes} minute(s)...")
        print_info("The risk engine evaluation will check for eligible losers and winners")

        print_success("Phase 8 Complete: Risk timer conditions set up")
        return True

    # -------------------------------------------------------------------------
    # PHASE 9: Risk Engine Execution
    # -------------------------------------------------------------------------
    async def phase_9_risk_execution(self):
        """Phase 9: Execute risk engine offset."""
        print_header("PHASE 9: RISK ENGINE EXECUTION (OFFSET)")

        print_info("Risk engine will:")
        print_info("  1. Select SOL as the loser (eligible: pyramids complete, loss > threshold, timer expired)")
        print_info("  2. Select BTC and ETH as winners (combined profit >= SOL loss)")
        print_info("  3. PARTIALLY close winners to realize ONLY the profit needed to cover SOL loss")
        print_info("  4. Close the entire SOL position")
        print_info("  5. Winners retain most of their position (only extracted needed profit)")
        print_info("")
        print_info("IMPORTANT: Offset only uses winners' PROFIT, not their capital!")

        # Wait for timer (already started in Phase 8)
        print_subheader("Step 9.1: Wait for Risk Timer to Expire")
        wait_seconds = self.config.post_pyramids_wait_minutes * 60 + 10
        print_info(f"Timer is {self.config.post_pyramids_wait_minutes} min. Waiting {wait_seconds}s...")

        # Show countdown
        for remaining in range(wait_seconds, 0, -10):
            print_info(f"  {remaining}s remaining...")
            await asyncio.sleep(10)

        # Trigger risk evaluation
        print_subheader("Step 9.2: Trigger Risk Evaluation")
        try:
            result = await self.engine.run_risk_evaluation()
            print_success(f"Risk evaluation triggered: {result}")
        except httpx.HTTPStatusError as e:
            print_warning(f"Risk evaluation response: {e}")

        await asyncio.sleep(5)

        # Verification
        print_subheader("Verification: Position State After Risk Offset")
        positions = await verify_positions(self.engine)

        # Verify winners still have quantity (partial close, not full close)
        for pos in positions:
            symbol = pos.get("symbol", "")
            qty = float(pos.get("total_filled_quantity", 0) or 0)
            hedged_qty = float(pos.get("total_hedged_qty", 0) or 0)
            pnl_usd = float(pos.get("unrealized_pnl_usd", 0) or 0)

            if "BTC" in symbol or "ETH" in symbol:
                if qty > 0:
                    print_success(f"{symbol}: Still has {qty:.6f} qty (hedged: {hedged_qty:.6f}, remaining PnL: ${pnl_usd:.2f})")
                else:
                    print_warning(f"{symbol}: Position fully closed! This should not happen.")

        # Check risk status
        await verify_risk_status(self.engine)

        # Show closed positions
        print_subheader("Verification: Position History (Closed Positions)")
        history = await self.engine.get_position_history(limit=5)
        if history.get("items"):
            rows = []
            for pos in history["items"]:
                rows.append([
                    pos.get("symbol", "N/A"),
                    pos.get("side", "N/A"),
                    f"${float(pos.get('realized_pnl_usd', 0)):.2f}",
                    pos.get("close_reason", "N/A"),
                    pos.get("closed_at", "N/A")[:19] if pos.get("closed_at") else "N/A",
                ])
            print_table(
                ["Symbol", "Side", "Realized PnL", "Close Reason", "Closed At"],
                rows,
                title="Recently Closed Positions"
            )

        print_success("Phase 9 Complete: Risk engine offset executed")
        return True

    # -------------------------------------------------------------------------
    # PHASE 10: Queue Promotion
    # -------------------------------------------------------------------------
    async def phase_10_queue_promotion(self):
        """Phase 10: Queue promotion after slot release."""
        print_header("PHASE 10: QUEUE PROMOTION AFTER SLOT RELEASE")

        print_info("After risk offset closes a position, a pool slot opens")
        print_info("The highest-priority queued signal will be promoted automatically")

        # Check current state
        print_subheader("Step 10.1: Check Pool and Queue State")
        positions = await verify_positions(self.engine)
        queue = await verify_queue(self.engine)

        print_info(f"Pool: {len(positions)}/{self.config.max_open_positions_global}")
        print_info(f"Queue: {len(queue)} signals waiting")

        if queue:
            # Wait for auto-promotion or manually trigger
            print_subheader("Step 10.2: Queue Promotion")
            print_info("Checking if promotion happened automatically...")

            await asyncio.sleep(5)

            new_positions = await verify_positions(self.engine)
            new_queue = await verify_queue(self.engine)

            if len(new_positions) > len(positions):
                print_success("Signal promoted automatically from queue!")
            elif new_queue:
                # Manual promotion
                print_info("Manually promoting top signal...")
                try:
                    promoted = await self.engine.promote_queued_signal(new_queue[0]["id"])
                    print_success(f"Promoted: {promoted.get('symbol', 'N/A')}")
                except httpx.HTTPStatusError as e:
                    print_warning(f"Promotion failed: {e}")
        else:
            print_info("Queue is empty - no signals to promote")

        # Final verification
        print_subheader("Verification: Final Pool State")
        await verify_positions(self.engine)
        await verify_queue(self.engine)

        print_success("Phase 10 Complete: Queue promotion demonstrated")
        return True

    # -------------------------------------------------------------------------
    # PHASE 11: TP Mode & Exit Signal
    # -------------------------------------------------------------------------
    async def phase_11_tp_exit(self):
        """Phase 11: Demonstrate TP modes and exit signals."""
        print_header("PHASE 11: TP MODE & EXIT SIGNAL DEMONSTRATION")

        positions = await self.engine.get_active_positions()

        if not positions:
            print_warning("No active positions to demonstrate TP/exit")
            return True

        # Demonstrate exit signal
        print_subheader("Step 11.1: Send Exit Signal for a Position")

        # Find a position to close
        pos_to_close = positions[0]
        symbol = pos_to_close["symbol"]
        ex_symbol = symbol.replace("/", "")

        print_info(f"Sending exit signal for {symbol}")

        payload = build_webhook_payload(
            user_id=self.config.user_id,
            secret=self.config.webhook_secret,
            symbol=ex_symbol,
            action="sell",
            market_position="flat",
            position_size=0,
            entry_price=0,
            prev_market_position="long",
            prev_position_size=float(pos_to_close.get("total_filled_quantity", 0)),
            trade_id=f"exit_{symbol}",
        )

        try:
            result = await self.engine.send_webhook(payload)
            print_success(f"Exit signal sent: {result.get('status', 'OK')}")
        except httpx.HTTPStatusError as e:
            print_error(f"Exit signal failed: {e}")

        # Wait for exit to process
        print_info("Waiting for exit signal to process...")
        await asyncio.sleep(5)

        # Verification
        print_subheader("Verification: Position State After Exit")
        new_positions = await verify_positions(self.engine)

        # Check if position was actually closed
        closed_symbols = [p["symbol"] for p in positions]
        remaining_symbols = [p["symbol"] for p in new_positions]

        if symbol not in remaining_symbols:
            print_success(f"Position {symbol} successfully closed via exit signal!")
        else:
            print_warning(f"Position {symbol} still active - exit may be pending")
            print_info("Trying manual close as backup...")
            try:
                await self.engine.close_position(pos_to_close["id"])
                await asyncio.sleep(2)
                print_success("Position closed via manual close")
            except httpx.HTTPStatusError as e:
                print_warning(f"Manual close also failed: {e}")

        print_success("Phase 11 Complete: TP mode and exit signal demonstrated")
        return True

    # -------------------------------------------------------------------------
    # PHASE 12: History & Analytics
    # -------------------------------------------------------------------------
    async def phase_12_history(self):
        """Phase 12: Review history and analytics."""
        print_header("PHASE 12: HISTORY & ANALYTICS REVIEW")

        # Get position history
        print_subheader("Step 12.1: Position History")
        history = await self.engine.get_position_history(limit=20)

        if history.get("items"):
            rows = []
            total_pnl = 0
            for pos in history["items"]:
                pnl = float(pos.get("realized_pnl_usd", 0))
                total_pnl += pnl
                rows.append([
                    pos.get("symbol", "N/A"),
                    pos.get("side", "N/A"),
                    pos.get("pyramid_count", 0),
                    f"${pnl:.2f}",
                    pos.get("close_reason", "N/A"),
                    pos.get("closed_at", "N/A")[:19] if pos.get("closed_at") else "N/A",
                ])
            print_table(
                ["Symbol", "Side", "Pyramids", "PnL", "Reason", "Closed At"],
                rows,
                title="Position History"
            )
            print_info(f"Total Realized PnL: ${total_pnl:.2f}")
        else:
            print_info("No closed positions in history")

        # Dashboard summary
        print_subheader("Step 12.2: Dashboard Summary")
        try:
            summary = await self.engine.get_dashboard_summary()
            print_table(
                ["Metric", "Value"],
                [
                    ["Active Positions", summary.get("active_positions", 0)],
                    ["Queued Signals", summary.get("queued_signals", 0)],
                    ["Total Trades Today", summary.get("total_trades_today", 0)],
                    ["PnL Today", f"${summary.get('pnl_today', 0):.2f}"],
                ],
                title="Dashboard Summary"
            )
        except httpx.HTTPStatusError:
            print_warning("Dashboard summary not available")

        print_success("Phase 12 Complete: History and analytics reviewed")
        return True

    # -------------------------------------------------------------------------
    # PHASE 13: Manual Risk Controls
    # -------------------------------------------------------------------------
    async def phase_13_manual_controls(self):
        """Phase 13: Demonstrate manual risk controls."""
        print_header("PHASE 13: MANUAL RISK CONTROLS DEMO")

        positions = await self.engine.get_active_positions()

        # Force Stop Engine
        print_subheader("Step 13.1: Force Stop Engine")
        print_info("This pauses the queue from releasing trades")
        try:
            result = await self.engine.force_stop_engine()
            print_success(f"Engine stopped: {result}")
        except httpx.HTTPStatusError as e:
            print_warning(f"Force stop result: {e}")
        except (httpx.RemoteProtocolError, httpx.ReadError) as e:
            print_warning(f"Server connection issue (may still have worked): {type(e).__name__}")

        await asyncio.sleep(2)

        # Force Start Engine
        print_subheader("Step 13.2: Force Start Engine")
        try:
            result = await self.engine.force_start_engine()
            print_success(f"Engine started: {result}")
        except httpx.HTTPStatusError as e:
            print_warning(f"Force start result: {e}")
        except (httpx.RemoteProtocolError, httpx.ReadError) as e:
            print_warning(f"Server connection issue (may still have worked): {type(e).__name__}")

        # Block/Unblock Position from Risk
        if positions:
            pos = positions[0]
            pos_id = pos["id"]

            print_subheader("Step 13.3: Block Position from Risk Engine")
            try:
                result = await self.engine.block_position_risk(pos_id)
                print_success(f"Position blocked: {pos['symbol']}")
            except httpx.HTTPStatusError as e:
                print_warning(f"Block result: {e}")

            await asyncio.sleep(2)

            print_subheader("Step 13.4: Unblock Position")
            try:
                result = await self.engine.unblock_position_risk(pos_id)
                print_success(f"Position unblocked: {pos['symbol']}")
            except httpx.HTTPStatusError as e:
                print_warning(f"Unblock result: {e}")

        # Manual Position Close
        if positions:
            print_subheader("Step 13.5: Manual Position Close")
            print_info(f"Manually closing position: {positions[0]['symbol']}")
            try:
                result = await self.engine.close_position(positions[0]["id"])
                print_success("Position closed manually")
            except httpx.HTTPStatusError as e:
                print_warning(f"Manual close result: {e}")

        # Final verification
        print_subheader("Final Verification")
        await verify_positions(self.engine)
        await verify_risk_status(self.engine)

        print_success("Phase 13 Complete: Manual risk controls demonstrated")
        return True

    # -------------------------------------------------------------------------
    # RUN ALL PHASES
    # -------------------------------------------------------------------------
    async def run_all(self, start_phase: int = 1):
        """Run all demo phases."""
        phases = [
            (1, "Clean Slate & Account Setup", self.phase_1_clean_slate),
            (2, "DCA Configuration Setup", self.phase_2_dca_setup),
            (3, "Mock Exchange Price Setup", self.phase_3_price_setup),
            (4, "Fill Execution Pool", self.phase_4_fill_pool),
            (5, "Queue Demonstration", self.phase_5_queue_demo),
            (6, "Pyramid Continuation", self.phase_6_pyramids),
            (7, "DCA Order Fills", self.phase_7_dca_fills),
            (8, "Risk Timer Activation", self.phase_8_risk_timer),
            (9, "Risk Engine Execution", self.phase_9_risk_execution),
            (10, "Queue Promotion", self.phase_10_queue_promotion),
            (11, "TP Mode & Exit Signal", self.phase_11_tp_exit),
            (12, "History & Analytics", self.phase_12_history),
            (13, "Manual Risk Controls", self.phase_13_manual_controls),
        ]

        # Setup first
        if not await self.setup():
            print_error("Setup failed. Cannot continue.")
            return

        for phase_num, name, func in phases:
            if phase_num < start_phase:
                continue

            await self.pause_for_presenter(f"Ready for Phase {phase_num}: {name}? Press Enter...")

            try:
                success = await func()
                if not success:
                    print_error(f"Phase {phase_num} failed. Stopping demo.")
                    break
            except Exception as e:
                print_error(f"Phase {phase_num} error: {e}")
                import traceback
                traceback.print_exc()
                break

        print_header("DEMO COMPLETE", "=")
        print_success("Thank you for watching the Trading Engine Demo!")

    async def cleanup(self):
        """Cleanup resources."""
        await self.mock.close()
        await self.engine.close()


# =============================================================================
# MAIN
# =============================================================================

async def main():
    parser = argparse.ArgumentParser(description="Trading Engine Live Demo Script")
    parser.add_argument("--phase", type=int, default=1, help="Start from phase N")
    parser.add_argument("--auto", action="store_true", help="Auto-continue without pausing")
    parser.add_argument("--delay", type=float, default=3.0, help="Delay between auto steps")
    parser.add_argument("--username", type=str, default="zmomz", help="Demo user username")
    parser.add_argument("--password", type=str, default="zm0mzzm0mz", help="Demo user password")
    parser.add_argument("--engine-url", type=str, default="http://127.0.0.1:8000", help="Engine URL")
    parser.add_argument("--mock-url", type=str, default="http://127.0.0.1:9000", help="Mock Exchange URL")

    args = parser.parse_args()

    config = DemoConfig(
        username=args.username,
        password=args.password,
        engine_url=args.engine_url,
        mock_exchange_url=args.mock_url,
        pause_between_phases=not args.auto,
        auto_continue_delay=args.delay,
    )

    runner = DemoRunner(config)

    try:
        await runner.run_all(start_phase=args.phase)
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    print_header("TRADING ENGINE LIVE DEMO", "*")
    print_info("This script demonstrates the full trading engine journey")
    print_info("Perfect for Zoom presentations and client demos")
    print()

    asyncio.run(main())
