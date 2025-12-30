"""
Trading Engine API Client.
"""

from typing import Any, Dict, List, Optional

from .base_client import BaseClient, RetryConfig


class EngineClient(BaseClient):
    """
    Client for Trading Engine API.

    Handles authentication, settings, positions, queue, risk, and webhook operations.
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8000",
        timeout: float = 60.0,
        retry_config: Optional[RetryConfig] = None,
    ):
        super().__init__(base_url, timeout, retry_config)
        self.access_token: Optional[str] = None
        self.user_id: Optional[str] = None
        self.webhook_secret: Optional[str] = None

    def _get_headers(self) -> Dict[str, str]:
        """Get auth headers."""
        if self.access_token:
            return {"Authorization": f"Bearer {self.access_token}"}
        return {}

    async def health_check(self) -> bool:
        """Check if engine is running."""
        try:
            response = await self._request("GET", "/api/v1/settings/exchanges")
            # Even 401 means the API is running
            return response.status_code in (200, 401, 403)
        except Exception:
            return False

    # -------------------------------------------------------------------------
    # Authentication
    # -------------------------------------------------------------------------

    async def login(self, username: str, password: str) -> Dict:
        """Login and get access token."""
        data = await self.post(
            "/api/v1/users/login",
            data={"username": username, "password": password},
        )
        self.access_token = data.get("access_token")
        if data.get("user"):
            self.user_id = str(data["user"]["id"])
        return data

    # -------------------------------------------------------------------------
    # Settings
    # -------------------------------------------------------------------------

    async def get_settings(self) -> Dict:
        """Get user settings."""
        return await self.get("/api/v1/settings")

    async def update_settings(self, settings: Dict) -> Dict:
        """Update user settings."""
        return await self.put("/api/v1/settings", json=settings)

    async def get_webhook_secret(self) -> str:
        """Get webhook secret from settings."""
        settings = await self.get_settings()
        self.webhook_secret = settings.get("webhook_secret", "")
        return self.webhook_secret

    # -------------------------------------------------------------------------
    # DCA Configurations
    # -------------------------------------------------------------------------

    async def get_dca_configs(self) -> List[Dict]:
        """Get all DCA configurations."""
        return await self.get("/api/v1/dca-configs/")

    async def create_dca_config(self, config: Dict) -> Dict:
        """Create a DCA configuration."""
        return await self.post("/api/v1/dca-configs/", json=config)

    async def update_dca_config(self, config_id: str, config: Dict) -> Dict:
        """Update a DCA configuration."""
        return await self.put(f"/api/v1/dca-configs/{config_id}", json=config)

    async def delete_dca_config(self, config_id: str) -> Dict:
        """Delete a DCA configuration."""
        return await self.delete(f"/api/v1/dca-configs/{config_id}")

    async def get_dca_config_by_pair(
        self,
        pair: str,
        timeframe: int = 60,
        exchange: str = "mock",
    ) -> Optional[Dict]:
        """Get DCA config for a specific pair."""
        configs = await self.get_dca_configs()
        for cfg in configs:
            if (
                cfg.get("pair") == pair
                and cfg.get("timeframe") == timeframe
                and cfg.get("exchange") == exchange
            ):
                return cfg
        return None

    # -------------------------------------------------------------------------
    # Positions
    # -------------------------------------------------------------------------

    async def get_active_positions(self) -> List[Dict]:
        """Get all active positions."""
        return await self.get("/api/v1/positions/active")

    async def get_position(self, group_id: str) -> Dict:
        """Get a specific position by ID."""
        return await self.get(f"/api/v1/positions/{group_id}")

    async def get_position_history(self, limit: int = 100) -> Dict:
        """Get position history."""
        return await self.get("/api/v1/positions/history", params={"limit": limit})

    async def close_position(self, group_id: str) -> Dict:
        """Force close a position."""
        return await self.post(f"/api/v1/positions/{group_id}/close")

    async def get_position_by_symbol(
        self,
        symbol: str,
        timeframe: int = 60,
    ) -> Optional[Dict]:
        """Get active position for a specific symbol."""
        positions = await self.get_active_positions()
        for pos in positions:
            if pos.get("symbol") == symbol and pos.get("timeframe") == timeframe:
                return pos
        return None

    # -------------------------------------------------------------------------
    # Queue
    # -------------------------------------------------------------------------

    async def get_queue(self) -> List[Dict]:
        """Get queued signals."""
        return await self.get("/api/v1/queue/")

    async def get_queue_history(self, limit: int = 50) -> List[Dict]:
        """Get queue history."""
        return await self.get("/api/v1/queue/history", params={"limit": limit})

    async def promote_queued_signal(self, signal_id: str) -> Dict:
        """Promote a signal from queue."""
        return await self.post(f"/api/v1/queue/{signal_id}/promote")

    async def remove_queued_signal(self, signal_id: str) -> Dict:
        """Remove a signal from queue."""
        return await self.delete(f"/api/v1/queue/{signal_id}")

    async def get_queued_signal_by_symbol(self, symbol: str) -> Optional[Dict]:
        """Get queued signal for a specific symbol."""
        queue = await self.get_queue()
        for sig in queue:
            if sig.get("symbol") == symbol:
                return sig
        return None

    # -------------------------------------------------------------------------
    # Risk Engine
    # -------------------------------------------------------------------------

    async def get_risk_status(self) -> Dict:
        """Get risk engine status."""
        return await self.get("/api/v1/risk/status")

    async def run_risk_evaluation(self) -> Dict:
        """Trigger risk evaluation."""
        return await self.post("/api/v1/risk/run-evaluation")

    async def block_position_risk(self, group_id: str) -> Dict:
        """Block position from risk engine."""
        return await self.post(f"/api/v1/risk/{group_id}/block")

    async def unblock_position_risk(self, group_id: str) -> Dict:
        """Unblock position from risk engine."""
        return await self.post(f"/api/v1/risk/{group_id}/unblock")

    async def skip_position_once(self, group_id: str) -> Dict:
        """Skip position for one risk evaluation cycle."""
        return await self.post(f"/api/v1/risk/{group_id}/skip-once")

    async def force_stop_engine(self) -> Dict:
        """Force stop the engine."""
        return await self.post("/api/v1/risk/force-stop")

    async def force_start_engine(self) -> Dict:
        """Force start the engine."""
        return await self.post("/api/v1/risk/force-start")

    # -------------------------------------------------------------------------
    # Webhooks
    # -------------------------------------------------------------------------

    async def send_webhook(self, payload: Dict) -> Dict:
        """Send a webhook signal."""
        user_id = payload.get("user_id", self.user_id)
        return await self.post(
            f"/api/v1/webhooks/{user_id}/tradingview",
            json=payload,
            timeout=60.0,
        )

    # -------------------------------------------------------------------------
    # Dashboard
    # -------------------------------------------------------------------------

    async def get_dashboard_summary(self) -> Dict:
        """Get dashboard summary."""
        return await self.get("/api/v1/dashboard/summary")

    # -------------------------------------------------------------------------
    # Cleanup Helpers
    # -------------------------------------------------------------------------

    async def close_all_positions(self) -> int:
        """Close all active positions. Returns number closed."""
        positions = await self.get_active_positions()
        closed = 0
        for pos in positions:
            try:
                await self.close_position(pos["id"])
                closed += 1
            except Exception:
                pass
        return closed

    async def clear_queue(self) -> int:
        """Remove all signals from queue. Returns number removed."""
        queue = await self.get_queue()
        removed = 0
        for sig in queue:
            try:
                await self.remove_queued_signal(sig["id"])
                removed += 1
            except Exception:
                pass
        return removed

    async def delete_all_dca_configs(self) -> int:
        """Delete all DCA configurations. Returns number deleted."""
        configs = await self.get_dca_configs()
        deleted = 0
        for cfg in configs:
            try:
                await self.delete_dca_config(cfg["id"])
                deleted += 1
            except Exception:
                pass
        return deleted
