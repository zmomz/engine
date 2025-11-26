#!/usr/bin/env python3
"""
Checks the health of the system by querying the API health endpoints.

Usage:
    python scripts/health_check.py [--url URL] [--verbose]
"""
import argparse
import sys
import requests
import json

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://localhost:8000', help='Base URL of the API')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    overall_success = True
    
    # Check 1: Root Health
    try:
        if args.verbose:
            print(f"Checking {args.url}/api/v1/health...")
        resp = requests.get(f"{args.url}/api/v1/health", timeout=5)
        if resp.status_code == 200:
            print("[PASS] API Health")
            data = resp.json()
            if args.verbose:
                print(json.dumps(data, indent=2))
            
            # Check for DB status in response if available
            if "database" in data:
                if data["database"] == "online" or data["database"] is True:
                    print("[PASS] Database Connection (via Health)")
                else:
                    print(f"[FAIL] Database Connection (via Health): {data['database']}")
                    overall_success = False
        else:
            print(f"[FAIL] API Health (Status: {resp.status_code})")
            overall_success = False
    except Exception as e:
        print(f"[FAIL] API Health (Connection Error: {e})")
        overall_success = False
        
    # Optional: Check dedicated DB health endpoint if it exists
    # try:
    #     ...
    # except:
    #     pass
        
    if overall_success:
        print("\nSystem Status: HEALTHY")
        return 0
    else:
        print("\nSystem Status: UNHEALTHY")
        return 1

if __name__ == "__main__":
    sys.exit(main())
