"""
Entry point for running demo_framework as a module.

Usage:
    python -m demo_framework run --category signal
    python -m demo_framework run --scenario S-001
    python -m demo_framework list
    python -m demo_framework quick
"""

from .cli import main

if __name__ == "__main__":
    main()
