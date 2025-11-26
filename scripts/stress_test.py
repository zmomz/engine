#!/usr/bin/env python3
"""
Simple stress test script for the API.

Usage:
    python scripts/stress_test.py --url URL --requests 100 --concurrency 10
"""
import argparse
import asyncio
import sys
import time
import logging

try:
    import httpx
except ImportError:
    print("Error: httpx is required. Install it via 'poetry add httpx' or 'pip install httpx'.")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

async def make_request(client, url):
    start = time.time()
    try:
        resp = await client.get(url)
        duration = time.time() - start
        return resp.status_code, duration
    except Exception as e:
        return 0, time.time() - start

async def run_stress_test(url, num_requests, concurrency):
    logger.info(f"Starting stress test: {num_requests} requests to {url} with concurrency {concurrency}")
    
    async with httpx.AsyncClient() as client:
        tasks = []
        results = []
        
        start_total = time.time()
        
        # Simple semaphore logic or batching
        # For true concurrency control, we use asyncio.Semaphore if strictly needed,
        # but for simple batching we can just gather chunks or use a semaphore.
        sem = asyncio.Semaphore(concurrency)

        async def worker():
            async with sem:
                return await make_request(client, url)

        for _ in range(num_requests):
            tasks.append(worker())
            
        results = await asyncio.gather(*tasks)
        total_time = time.time() - start_total
        
    # Analyze
    status_codes = {}
    total_duration = 0
    for code, dur in results:
        status_codes[code] = status_codes.get(code, 0) + 1
        total_duration += dur
        
    avg_latency = total_duration / num_requests if num_requests else 0
    rps = num_requests / total_time if total_time else 0
    
    logger.info("\nResults:")
    logger.info(f"Total Time: {total_time:.2f}s")
    logger.info(f"RPS: {rps:.2f}")
    logger.info(f"Avg Latency: {avg_latency*1000:.2f}ms")
    logger.info(f"Status Codes: {status_codes}")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://localhost:8000/api/v1/health', help='Target URL')
    parser.add_argument('--requests', type=int, default=100, help='Total requests')
    parser.add_argument('--concurrency', type=int, default=10, help='Concurrent requests')
    
    args = parser.parse_args()
    
    asyncio.run(run_stress_test(args.url, args.requests, args.concurrency))

if __name__ == "__main__":
    sys.exit(main())
