#!/usr/bin/env python3
"""
Outputs the default RiskEngineConfig as JSON.

Usage:
    python scripts/get_default_risk_config.py
"""
import sys
import os
import json

# Add backend to path to allow imports
sys.path.append(os.path.join(os.path.dirname(__file__), '../backend'))

try:
    from app.schemas.grid_config import RiskEngineConfig
except ImportError:
    print("Error: Could not import app.schemas.grid_config. Make sure you are running from the project root or backend is in PYTHONPATH.", file=sys.stderr)
    sys.exit(1)

def main():
    try:
        config = RiskEngineConfig()
        print(json.dumps(config.model_dump(mode='json'), indent=2))
        return 0
    except Exception as e:
        print(f"Error generating config: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())