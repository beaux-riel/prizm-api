#!/usr/bin/env python3
"""
CLI tool for managing the PRIZM API cache
"""

import argparse
import json
import sys
from cache_manager import cache_manager


def main():
    parser = argparse.ArgumentParser(description="Manage PRIZM API cache")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show cache statistics')
    
    # Cleanup command
    cleanup_parser = subparsers.add_parser('cleanup', help='Clean up expired cache entries')
    
    # Clear command
    clear_parser = subparsers.add_parser('clear', help='Clear all cache entries')
    clear_parser.add_argument('--confirm', action='store_true', 
                             help='Confirm that you want to clear all cache entries')
    
    # Check command
    check_parser = subparsers.add_parser('check', help='Check if a postal code is cached')
    check_parser.add_argument('postal_code', help='Postal code to check')
    
    # Get command
    get_parser = subparsers.add_parser('get', help='Get cached data for a postal code')
    get_parser.add_argument('postal_code', help='Postal code to retrieve')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    try:
        if args.command == 'stats':
            stats = cache_manager.get_cache_stats()
            print("Cache Statistics:")
            print(f"  Total entries: {stats.get('total_entries', 0)}")
            print(f"  Valid entries: {stats.get('valid_entries', 0)}")
            print(f"  Expired entries: {stats.get('expired_entries', 0)}")
            print(f"  Cache duration: {stats.get('cache_duration_days', 0)} days")
            print(f"  Database size: {stats.get('database_size_bytes', 0):,} bytes")
            print(f"  Oldest entry: {stats.get('oldest_entry', 'N/A')}")
            print(f"  Newest entry: {stats.get('newest_entry', 'N/A')}")
            
        elif args.command == 'cleanup':
            deleted_count = cache_manager.cleanup_expired_cache()
            print(f"Cleaned up {deleted_count} expired cache entries")
            
        elif args.command == 'clear':
            if not args.confirm:
                print("Warning: This will clear ALL cache entries!")
                print("Use --confirm flag to proceed")
                return 1
            
            if cache_manager.clear_cache():
                print("All cache entries cleared successfully")
            else:
                print("Failed to clear cache entries")
                return 1
                
        elif args.command == 'check':
            postal_code = args.postal_code.strip().upper()
            is_cached = cache_manager.is_cached(postal_code)
            
            if is_cached:
                cached_data = cache_manager.get_cached_data(postal_code)
                cache_info = cached_data.get('_cache_info', {}) if cached_data else {}
                print(f"Postal code {postal_code} is cached")
                print(f"  Cached at: {cache_info.get('cached_at', 'Unknown')}")
            else:
                print(f"Postal code {postal_code} is not cached")
                
        elif args.command == 'get':
            postal_code = args.postal_code.strip().upper()
            cached_data = cache_manager.get_cached_data(postal_code)
            
            if cached_data:
                print(f"Cached data for {postal_code}:")
                print(json.dumps(cached_data, indent=2))
            else:
                print(f"No cached data found for {postal_code}")
                return 1
                
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
