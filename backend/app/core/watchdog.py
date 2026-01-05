"""
Watchdog service for monitoring and managing background tasks.

This module provides:
- Monitoring of registered background tasks
- Detection of stalled or crashed tasks
- Automatic restart capability for unhealthy tasks
- Health metrics aggregation
"""
import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Dict, List, Optional, Any, Awaitable

logger = logging.getLogger(__name__)


class TaskHealth(Enum):
    """Health status of a monitored task."""
    HEALTHY = "healthy"           # Task is running normally
    DEGRADED = "degraded"         # Task has errors but is running
    STALLED = "stalled"           # Task hasn't reported heartbeat
    CRASHED = "crashed"           # Task has terminated unexpectedly
    STOPPED = "stopped"           # Task was intentionally stopped
    UNKNOWN = "unknown"           # Cannot determine health


@dataclass
class TaskStatus:
    """Status information for a monitored task."""
    name: str
    health: TaskHealth
    last_heartbeat: Optional[float] = None
    error_count: int = 0
    restart_count: int = 0
    last_error: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    started_at: Optional[float] = None


@dataclass
class WatchdogConfig:
    """Configuration for the watchdog service."""
    check_interval: float = 30.0              # Seconds between health checks
    heartbeat_timeout: float = 120.0          # Seconds before task is considered stalled
    max_restarts: int = 3                     # Maximum restart attempts before giving up
    restart_cooldown: float = 60.0            # Seconds to wait between restart attempts
    error_threshold: int = 10                 # Errors before task is considered degraded


class TaskWatchdog:
    """
    Monitors background tasks and can restart them if they become unhealthy.

    Usage:
        watchdog = TaskWatchdog()

        # Register a task with its start function
        watchdog.register_task(
            name="order_fill_monitor",
            start_func=order_fill_monitor.start_monitoring_task,
            stop_func=order_fill_monitor.stop_monitoring_task,
            health_check=lambda: cache.get_service_health("order_fill_monitor")
        )

        # Start the watchdog
        await watchdog.start()
    """

    def __init__(self, config: Optional[WatchdogConfig] = None):
        self.config = config or WatchdogConfig()
        self._tasks: Dict[str, dict] = {}
        self._status: Dict[str, TaskStatus] = {}
        self._running = False
        self._watchdog_task: Optional[asyncio.Task] = None
        self._restart_timestamps: Dict[str, List[float]] = {}

    def register_task(
        self,
        name: str,
        start_func: Callable[[], Awaitable[None]],
        stop_func: Optional[Callable[[], Awaitable[None]]] = None,
        health_check: Optional[Callable[[], Awaitable[Optional[dict]]]] = None,
        critical: bool = True
    ):
        """
        Register a task for monitoring.

        Args:
            name: Unique identifier for the task
            start_func: Async function to start the task
            stop_func: Async function to stop the task (optional)
            health_check: Async function that returns health data (optional)
            critical: If True, watchdog will attempt restarts on failure
        """
        self._tasks[name] = {
            "start_func": start_func,
            "stop_func": stop_func,
            "health_check": health_check,
            "critical": critical
        }
        self._status[name] = TaskStatus(
            name=name,
            health=TaskHealth.UNKNOWN,
            started_at=time.time()
        )
        self._restart_timestamps[name] = []
        logger.info(f"Watchdog: Registered task '{name}' (critical={critical})")

    async def start(self):
        """Start the watchdog monitoring loop."""
        if self._running:
            logger.warning("Watchdog is already running")
            return

        self._running = True
        self._watchdog_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Watchdog started")

    async def stop(self):
        """Stop the watchdog."""
        if not self._running:
            return

        self._running = False
        if self._watchdog_task:
            self._watchdog_task.cancel()
            try:
                await self._watchdog_task
            except asyncio.CancelledError:
                pass
        logger.info("Watchdog stopped")

    async def _monitoring_loop(self):
        """Main monitoring loop."""
        while self._running:
            try:
                await self._check_all_tasks()
                await asyncio.sleep(self.config.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in watchdog monitoring loop: {e}")
                await asyncio.sleep(self.config.check_interval)

    async def _check_all_tasks(self):
        """Check health of all registered tasks."""
        for name, task_info in self._tasks.items():
            try:
                await self._check_task(name, task_info)
            except Exception as e:
                logger.error(f"Error checking task '{name}': {e}")

    async def _check_task(self, name: str, task_info: dict):
        """Check health of a single task."""
        status = self._status[name]
        health_check = task_info.get("health_check")

        # Get health data if available
        health_data = None
        if health_check:
            try:
                health_data = await health_check()
            except Exception as e:
                logger.warning(f"Health check failed for '{name}': {e}")

        # Determine health status
        now = time.time()
        prev_health = status.health

        if health_data:
            last_heartbeat = health_data.get("last_heartbeat")
            if last_heartbeat:
                status.last_heartbeat = last_heartbeat
                heartbeat_age = now - last_heartbeat

                if heartbeat_age > self.config.heartbeat_timeout:
                    status.health = TaskHealth.STALLED
                elif health_data.get("status") == "error":
                    status.health = TaskHealth.DEGRADED
                elif health_data.get("status") == "stopped":
                    status.health = TaskHealth.STOPPED
                else:
                    status.health = TaskHealth.HEALTHY

                # Update metrics from health data
                metrics = health_data.get("metrics", {})
                status.error_count = metrics.get("error_count", 0)
                status.last_error = metrics.get("last_error")
                status.metrics = metrics

                # Check error threshold for degraded status
                if status.error_count >= self.config.error_threshold and status.health == TaskHealth.HEALTHY:
                    status.health = TaskHealth.DEGRADED
            else:
                # No heartbeat in health data
                status.health = TaskHealth.UNKNOWN
        else:
            # No health data available
            if status.last_heartbeat:
                heartbeat_age = now - status.last_heartbeat
                if heartbeat_age > self.config.heartbeat_timeout:
                    status.health = TaskHealth.STALLED
            else:
                status.health = TaskHealth.UNKNOWN

        # Log health changes
        if prev_health != status.health:
            if status.health in [TaskHealth.STALLED, TaskHealth.CRASHED, TaskHealth.DEGRADED]:
                logger.warning(
                    f"Watchdog: Task '{name}' health changed from {prev_health.value} to {status.health.value}"
                )
            else:
                logger.info(
                    f"Watchdog: Task '{name}' health changed from {prev_health.value} to {status.health.value}"
                )

        # Handle unhealthy tasks
        if status.health in [TaskHealth.STALLED, TaskHealth.CRASHED] and task_info.get("critical"):
            await self._handle_unhealthy_task(name, task_info, status)

    async def _handle_unhealthy_task(self, name: str, task_info: dict, status: TaskStatus):
        """Handle an unhealthy task - attempt restart if allowed."""
        # Check if we can restart
        now = time.time()

        # Clean up old restart timestamps
        self._restart_timestamps[name] = [
            ts for ts in self._restart_timestamps[name]
            if now - ts < self.config.restart_cooldown * self.config.max_restarts
        ]

        # Check restart limits
        recent_restarts = len(self._restart_timestamps[name])
        if recent_restarts >= self.config.max_restarts:
            logger.error(
                f"Watchdog: Task '{name}' has exceeded max restarts ({self.config.max_restarts}). "
                f"Manual intervention required."
            )
            return

        # Check cooldown
        if self._restart_timestamps[name]:
            last_restart = self._restart_timestamps[name][-1]
            if now - last_restart < self.config.restart_cooldown:
                logger.debug(f"Watchdog: Task '{name}' is in restart cooldown")
                return

        # Attempt restart
        logger.warning(f"Watchdog: Attempting to restart task '{name}'")
        try:
            # Stop if stop function exists
            stop_func = task_info.get("stop_func")
            if stop_func:
                try:
                    await stop_func()
                except Exception as e:
                    logger.warning(f"Error stopping task '{name}': {e}")

            # Wait a moment before restarting
            await asyncio.sleep(1.0)

            # Start the task
            start_func = task_info.get("start_func")
            if start_func:
                await start_func()
                status.restart_count += 1
                status.started_at = now
                self._restart_timestamps[name].append(now)
                logger.info(f"Watchdog: Successfully restarted task '{name}'")
            else:
                logger.error(f"Watchdog: No start function for task '{name}'")

        except Exception as e:
            logger.error(f"Watchdog: Failed to restart task '{name}': {e}")

    def get_status(self, name: str) -> Optional[TaskStatus]:
        """Get status of a specific task."""
        return self._status.get(name)

    def get_all_status(self) -> Dict[str, TaskStatus]:
        """Get status of all tasks."""
        return self._status.copy()

    def get_summary(self) -> dict:
        """Get a summary of all task health."""
        healthy = 0
        degraded = 0
        unhealthy = 0

        for status in self._status.values():
            if status.health == TaskHealth.HEALTHY:
                healthy += 1
            elif status.health == TaskHealth.DEGRADED:
                degraded += 1
            else:
                unhealthy += 1

        return {
            "healthy": healthy,
            "degraded": degraded,
            "unhealthy": unhealthy,
            "total": len(self._status),
            "tasks": {
                name: {
                    "health": status.health.value,
                    "last_heartbeat": status.last_heartbeat,
                    "error_count": status.error_count,
                    "restart_count": status.restart_count
                }
                for name, status in self._status.items()
            }
        }


# Global watchdog instance
_watchdog: Optional[TaskWatchdog] = None


def get_watchdog() -> TaskWatchdog:
    """Get the global watchdog instance."""
    global _watchdog
    if _watchdog is None:
        _watchdog = TaskWatchdog()
    return _watchdog


async def setup_watchdog(app) -> TaskWatchdog:
    """
    Set up the watchdog with registered tasks from the app.

    Args:
        app: FastAPI app instance with background services in state

    Returns:
        Configured TaskWatchdog instance
    """
    from app.core.cache import get_cache

    watchdog = get_watchdog()
    cache = await get_cache()

    # Register order fill monitor
    if hasattr(app.state, "order_fill_monitor"):
        async def ofm_health():
            return await cache.get_service_health("order_fill_monitor")

        watchdog.register_task(
            name="order_fill_monitor",
            start_func=app.state.order_fill_monitor.start_monitoring_task,
            stop_func=app.state.order_fill_monitor.stop_monitoring_task,
            health_check=ofm_health,
            critical=True
        )

    # Register queue manager
    if hasattr(app.state, "queue_manager_service"):
        async def qm_health():
            return await cache.get_service_health("queue_manager")

        watchdog.register_task(
            name="queue_manager",
            start_func=app.state.queue_manager_service.start_promotion_task,
            stop_func=app.state.queue_manager_service.stop_promotion_task,
            health_check=qm_health,
            critical=True
        )

    # Register risk engine
    if hasattr(app.state, "risk_engine_service"):
        async def risk_health():
            return await cache.get_service_health("risk_engine")

        watchdog.register_task(
            name="risk_engine",
            start_func=app.state.risk_engine_service.start_monitoring_task,
            stop_func=app.state.risk_engine_service.stop_monitoring_task,
            health_check=risk_health,
            critical=True
        )

    return watchdog
