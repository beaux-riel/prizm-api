#!/usr/bin/env python3
"""
Test script to verify that invalid postal codes are cached properly
"""

import time
import requests
import json

# Test configuration
BASE_URL = "http://localhost:8080"
TEST_CASES = [
    "INVALID",      # Invalid format
    "Z9Z 9Z9",      # Invalid postal code (not assigned)
    "A1A 1A1",      # Might be valid or invalid
]

def test_caching():
    print("Testing Invalid Postal Code Caching")
    print("=" * 50)
    
    for postal_code in TEST_CASES:
        print(f"\nTesting postal code: {postal_code}")
        
        # First request - should hit the API
        print("First request (should fetch from API)...")
        start_time = time.time()
        try:
            response1 = requests.get(f"{BASE_URL}/api/prizm", params={"postal_code": postal_code})
            end_time = time.time()
            first_duration = end_time - start_time
            
            if response1.status_code == 200:
                data1 = response1.json()
                print(f"  Status: {data1.get('status', 'unknown')}")
                print(f"  Duration: {first_duration:.2f}s")
                cache_info = data1.get('cache_info', {})
                if cache_info:
                    print(f"  From cache: {cache_info.get('from_cache', False)}")
                else:
                    print("  From cache: False (fresh API call)")
            else:
                print(f"  Error: HTTP {response1.status_code}")
                continue
                
        except Exception as e:
            print(f"  Error: {e}")
            continue
        
        # Wait a moment
        time.sleep(1)
        
        # Second request - should come from cache
        print("Second request (should come from cache)...")
        start_time = time.time()
        try:
            response2 = requests.get(f"{BASE_URL}/api/prizm", params={"postal_code": postal_code})
            end_time = time.time()
            second_duration = end_time - start_time
            
            if response2.status_code == 200:
                data2 = response2.json()
                print(f"  Status: {data2.get('status', 'unknown')}")
                print(f"  Duration: {second_duration:.2f}s")
                cache_info = data2.get('cache_info', {})
                if cache_info:
                    print(f"  From cache: {cache_info.get('from_cache', False)}")
                    print(f"  Cached at: {cache_info.get('cached_at', 'unknown')}")
                else:
                    print("  From cache: False")
                
                # Performance comparison
                if first_duration > 0 and second_duration > 0:
                    speedup = first_duration / second_duration
                    print(f"  Speed improvement: {speedup:.1f}x faster")
                    
            else:
                print(f"  Error: HTTP {response2.status_code}")
                
        except Exception as e:
            print(f"  Error: {e}")

    # Check cache stats
    print(f"\n{'='*50}")
    print("Cache Statistics:")
    try:
        response = requests.get(f"{BASE_URL}/api/cache/stats")
        if response.status_code == 200:
            stats = response.json()
            if stats.get('status') == 'success':
                cache_stats = stats.get('cache_stats', {})
                print(f"  Total entries: {cache_stats.get('total_entries', 0)}")
                print(f"  Valid entries: {cache_stats.get('valid_entries', 0)}")
                print(f"  Expired entries: {cache_stats.get('expired_entries', 0)}")
            else:
                print("  Error getting cache stats")
        else:
            print(f"  Error: HTTP {response.status_code}")
    except Exception as e:
        print(f"  Error: {e}")

if __name__ == "__main__":
    print("Make sure the Flask server is running on port 8080 before running this test.")
    input("Press Enter to continue...")
    test_caching()
