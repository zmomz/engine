"""
Demo Framework for Trading Engine
=================================

A comprehensive scenario-based testing framework for live demonstrations.

Usage:
    python -m demo_framework run --category signal
    python -m demo_framework run --scenario S-001
    python -m demo_framework list
    python -m demo_framework quick
"""

from .runner import DemoRunner
from .scenarios.base import BaseScenario, ScenarioResult, ScenarioStatus

__version__ = "1.0.0"
__all__ = ["DemoRunner", "BaseScenario", "ScenarioResult", "ScenarioStatus"]
