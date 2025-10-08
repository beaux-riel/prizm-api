#!/usr/bin/env python3
"""
CLI tool for managing the PRIZM API cache
"""

import argparse
import json
import sys
from cache_manager_new import cache_manager


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
    
    # Delete command
    delete_parser = subparsers.add_parser('delete', help='Delete cached data for a postal code')
    delete_parser.add_argument('postal_code', help='Postal code to delete from cache')
    
    # Confirm command
    confirm_parser = subparsers.add_parser('confirm', help='Mark postal code data as confirmed')
    confirm_parser.add_argument('postal_code', help='Postal code to confirm')
    
    # Unconfirm command
    unconfirm_parser = subparsers.add_parser('unconfirm', help='Mark postal code data as unconfirmed')
    unconfirm_parser.add_argument('postal_code', help='Postal code to unconfirm')
    
    # List unconfirmed command
    unconfirmed_parser = subparsers.add_parser('unconfirmed', help='List unconfirmed cache entries')
    unconfirmed_parser.add_argument('--limit', type=int, default=100, help='Maximum number of entries to show')
    
    # Migrate command
    migrate_parser = subparsers.add_parser('migrate', help='Migrate database to new schema')
    migrate_parser.add_argument('--no-backup', action='store_true', help='Skip creating backup')
    
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
            print(f"  Confirmed entries: {stats.get('confirmed_entries', 0)}")
            print(f"  Unconfirmed entries: {stats.get('unconfirmed_entries', 0)}")
            
            # Show status breakdown if available
            status_breakdown = stats.get('status_breakdown', {})
            if status_breakdown:
                print(f"  Status breakdown:")
                for status, count in status_breakdown.items():
                    print(f"    - {status}: {count}")
            
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
                print(f"  Confirmed: {'Yes' if cache_info.get('confirmed') else 'No'}")
                print(f"  Has HTML: {'Yes' if cache_info.get('has_html') else 'No'}")
            else:
                print(f"Postal code {postal_code} is not cached")
                
        elif args.command == 'get':
            postal_code = args.postal_code.strip().upper()
            cached_data = cache_manager.get_cached_data(postal_code)
            
            if cached_data:
                print(f"Cached data for {postal_code}:")
                # Remove cache info for cleaner display
                display_data = cached_data.copy()
                display_data.pop('_cache_info', None)
                print(json.dumps(display_data, indent=2))
                
                # Show cache info separately
                cache_info = cached_data.get('_cache_info', {})
                if cache_info:
                    print("\nCache Information:")
                    print(f"  Cached at: {cache_info.get('cached_at', 'Unknown')}")
                    print(f"  Confirmed: {'Yes' if cache_info.get('confirmed') else 'No'}")
                    print(f"  Has HTML: {'Yes' if cache_info.get('has_html') else 'No'}")
            else:
                print(f"No cached data found for {postal_code}")
                return 1
                
        elif args.command == 'delete':
            postal_code = args.postal_code.strip().upper()
            if cache_manager.delete_cached_data(postal_code):
                print(f"Successfully deleted cache entry for {postal_code}")
            else:
                print(f"No cache entry found for {postal_code}")
                return 1
        
        elif args.command == 'confirm':
            postal_code = args.postal_code.strip().upper()
            if cache_manager.confirm_data(postal_code):
                print(f"Successfully confirmed data for {postal_code}")
            else:
                print(f"No valid cache entry found for {postal_code}")
                return 1
        
        elif args.command == 'unconfirm':
            postal_code = args.postal_code.strip().upper()
            if cache_manager.unconfirm_data(postal_code):
                print(f"Successfully unconfirmed data for {postal_code}")
            else:
                print(f"No valid cache entry found for {postal_code}")
                return 1
        
        elif args.command == 'unconfirmed':
            entries = cache_manager.get_unconfirmed_entries(args.limit)
            
            if entries:
                print(f"Unconfirmed cache entries (showing up to {args.limit}):")
                print(f"{'Postal Code':<12} {'Segment #':<10} {'Segment Name':<40} {'Cached At':<20}")
                print("-" * 85)
                
                for entry in entries:
                    postal_code = entry['postal_code']
                    segment_number = entry.get('segment_number', '') or ''
                    segment_name = entry.get('segment_name', '') or ''
                    cached_at = entry.get('cached_at', '')
                    
                    # Truncate segment name if too long
                    if len(segment_name) > 38:
                        segment_name = segment_name[:35] + "..."
                    
                    print(f"{postal_code:<12} {segment_number:<10} {segment_name:<40} {cached_at:<20}")
                
                print(f"\nTotal unconfirmed entries shown: {len(entries)}")
            else:
                print("No unconfirmed cache entries found")
        
        elif args.command == 'migrate':
            from migrate_database import migrate_database, verify_migration
            
            print("Starting database migration...")
            success = migrate_database(backup=not args.no_backup)
            
            if success:
                verify_migration()
                print("\n✅ Migration completed successfully!")
            else:
                print("\n❌ Migration failed! Check the logs for details.")
                return 1
                
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())