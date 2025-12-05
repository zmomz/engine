#!/usr/bin/env python3
"""
Outputs default configurations for various system components.

Usage:
    python scripts/get_default_config.py [--schema {risk,grid,all}] [--output FILE]
"""
import sys
import os
import json
import argparse

from decimal import Decimal

# Add backend to path to allow imports
sys.path.append(os.path.join(os.path.dirname(__file__), '../backend'))

try:
    from app.schemas.grid_config import RiskEngineConfig, GridConfig
except ImportError:
    print("Error: Could not import schemas. Make sure you are running from the project root or backend is in PYTHONPATH.", file=sys.stderr)
    sys.exit(1)

def decimal_default(obj):
    if isinstance(obj, Decimal):
        return str(obj)
    raise TypeError

def get_risk_config():
    return RiskEngineConfig().model_dump(mode='json')

def get_grid_config():
    # Assuming GridConfig has defaults or we create a dummy one. 
    # If GridConfig doesn't have defaults, we might need to construct it.
    # For now, we instantiate it to get defaults if any.
    try:
        return GridConfig(
            grid_type="geometric",
            lower_price=1000.0,
            upper_price=2000.0,
            grid_levels=10
        ).model_dump(mode='json')
    except Exception:
        return {"error": "GridConfig requires mandatory fields, no default available without context."}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--schema', choices=['risk', 'grid', 'all'], default='risk', help='Config schema to generate')
    parser.add_argument('--output', help='Output file path (default: stdout)')
    
    args = parser.parse_args()
    
    data = {}
    if args.schema == 'risk' or args.schema == 'all':
        data['risk_config'] = get_risk_config()
    if args.schema == 'grid' or args.schema == 'all':
        data['grid_config'] = get_grid_config()
        
    # If asking for a specific single schema, return just that object, not wrapped in a dict
    if args.schema == 'risk':
        output_data = data['risk_config']
    elif args.schema == 'grid':
        output_data = data['grid_config']
    else:
        output_data = data

    json_output = json.dumps(output_data, indent=2, default=decimal_default)

    if args.output:
        try:
            with open(args.output, 'w') as f:
                f.write(json_output)
            print(f"Configuration saved to {args.output}")
        except Exception as e:
            print(f"Error writing to file: {e}", file=sys.stderr)
            return 1
    else:
        print(json_output)

    return 0

if __name__ == "__main__":
    sys.exit(main())