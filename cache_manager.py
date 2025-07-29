#!/usr/bin/env python3
"""
Cache Manager for PRIZM API data
Stores postal code data locally to reduce API calls to the PRIZM website
Data is cached for up to 3 months
"""

import sqlite3
import json
from json import JSONDecodeError
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import os
import logging

logger = logging.getLogger(__name__)

class CacheManager:
    """Manages local caching of PRIZM postal code data"""
    
    def __init__(self, db_path: str = "prizm_cache.db", cache_duration_days: int = 90):
        """
        Initialize the cache manager
        
        Args:
            db_path: Path to the SQLite database file
            cache_duration_days: Number of days to cache data (default: 90 days = 3 months)
        """
        self.db_path = db_path
        self.cache_duration_days = cache_duration_days
        self._init_database()
    
    def _init_database(self):
        """Initialize the SQLite database with the required table"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create the cache table if it doesn't exist
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS postal_code_cache (
                        postal_code TEXT PRIMARY KEY,
                        data TEXT NOT NULL,
                        cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP NOT NULL
                    )
                """)
                
                # Create an index on expires_at for efficient cleanup
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_expires_at 
                    ON postal_code_cache (expires_at)
                """)
                
                conn.commit()
                logger.info(f"Cache database initialized at {self.db_path}")
                
        except sqlite3.Error as e:
            logger.error(f"Failed to initialize cache database: {e}")
            raise
    
    def get_cached_data(self, postal_code: str) -> Optional[Dict[Any, Any]]:
        """
        Retrieve cached data for a postal code if it exists and hasn't expired
        
        Args:
            postal_code: The postal code to look up
            
        Returns:
            Dict containing the cached data if found and valid, None otherwise
        """
        try:
            postal_code = postal_code.strip().upper()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get the cached data if it exists and hasn't expired
                cursor.execute("""
                    SELECT data, cached_at 
                    FROM postal_code_cache 
                    WHERE postal_code = ? AND expires_at > datetime('now')
                """, (postal_code,))
                
                result = cursor.fetchone()
                
                if result:
                    data_json, cached_at = result
                    cached_data = json.loads(data_json)
                    
                    logger.info(f"Cache hit for postal code {postal_code} (cached at {cached_at})")
                    
                    # Add cache metadata
                    cached_data['_cache_info'] = {
                        'cached_at': cached_at,
                        'from_cache': True
                    }
                    
                    return cached_data
                else:
                    logger.info(f"Cache miss for postal code {postal_code}")
                    return None
                    
        except (sqlite3.Error, JSONDecodeError) as e:
            logger.error(f"Error retrieving cached data for {postal_code}: {e}")
            return None
    
    def cache_data(self, postal_code: str, data: Dict[Any, Any], custom_duration_days: Optional[int] = None) -> bool:
        """
        Cache data for a postal code
        
        Args:
            postal_code: The postal code
            data: The data to cache (will be JSON serialized)
            custom_duration_days: Optional custom cache duration in days. If None, uses default duration.
            
        Returns:
            True if caching was successful, False otherwise
        """
        try:
            postal_code = postal_code.strip().upper()
            
            # Remove cache metadata if present
            data_to_cache = data.copy()
            data_to_cache.pop('_cache_info', None)
            
            # Calculate expiration date using custom duration or default
            duration_days = custom_duration_days if custom_duration_days is not None else self.cache_duration_days
            expires_at = datetime.now() + timedelta(days=duration_days)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Insert or replace the cached data
                cursor.execute("""
                    INSERT OR REPLACE INTO postal_code_cache 
                    (postal_code, data, expires_at) 
                    VALUES (?, ?, ?)
                """, (postal_code, json.dumps(data_to_cache), expires_at))
                
                conn.commit()
                
                logger.info(f"Cached data for postal code {postal_code} (expires: {expires_at}, duration: {duration_days} days)")
                return True
                
        except (sqlite3.Error, JSONDecodeError) as e:
            logger.error(f"Error caching data for {postal_code}: {e}")
            return False
    
    def cleanup_expired_cache(self) -> int:
        """
        Remove expired cache entries
        
        Returns:
            Number of entries removed
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Delete expired entries
                cursor.execute("""
                    DELETE FROM postal_code_cache 
                    WHERE expires_at <= datetime('now')
                """)
                
                deleted_count = cursor.rowcount
                conn.commit()
                
                if deleted_count > 0:
                    logger.info(f"Cleaned up {deleted_count} expired cache entries")
                
                return deleted_count
                
        except sqlite3.Error as e:
            logger.error(f"Error cleaning up expired cache: {e}")
            return 0
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the cache
        
        Returns:
            Dict containing cache statistics
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get total entries
                cursor.execute("SELECT COUNT(*) FROM postal_code_cache")
                total_entries = cursor.fetchone()[0]
                
                # Get valid (non-expired) entries
                cursor.execute("""
                    SELECT COUNT(*) FROM postal_code_cache 
                    WHERE expires_at > datetime('now')
                """)
                valid_entries = cursor.fetchone()[0]
                
                # Get expired entries
                expired_entries = total_entries - valid_entries
                
                # Get oldest and newest entries
                cursor.execute("""
                    SELECT MIN(cached_at), MAX(cached_at) 
                    FROM postal_code_cache 
                    WHERE expires_at > datetime('now')
                """)
                oldest, newest = cursor.fetchone()
                
                # Get database file size
                db_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
                
                return {
                    'total_entries': total_entries,
                    'valid_entries': valid_entries,
                    'expired_entries': expired_entries,
                    'oldest_entry': oldest,
                    'newest_entry': newest,
                    'database_size_bytes': db_size,
                    'cache_duration_days': self.cache_duration_days
                }
                
        except sqlite3.Error as e:
            logger.error(f"Error getting cache stats: {e}")
            return {}
    
    def clear_cache(self) -> bool:
        """
        Clear all cache entries
        
        Returns:
            True if successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM postal_code_cache")
                deleted_count = cursor.rowcount
                conn.commit()
                
                logger.info(f"Cleared {deleted_count} cache entries")
                return True
                
        except sqlite3.Error as e:
            logger.error(f"Error clearing cache: {e}")
            return False
    
    def is_cached(self, postal_code: str) -> bool:
        """
        Check if a postal code is cached and valid
        
        Args:
            postal_code: The postal code to check
            
        Returns:
            True if the postal code is cached and valid, False otherwise
        """
        return self.get_cached_data(postal_code) is not None
    
    def delete_cached_data(self, postal_code: str) -> bool:
        """
        Delete cached data for a specific postal code
        
        Args:
            postal_code: The postal code to delete from cache
            
        Returns:
            True if deletion was successful, False otherwise
        """
        try:
            postal_code = postal_code.strip().upper()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Delete the entry for this postal code
                cursor.execute("""
                    DELETE FROM postal_code_cache 
                    WHERE postal_code = ?
                """, (postal_code,))
                
                deleted_count = cursor.rowcount
                conn.commit()
                
                if deleted_count > 0:
                    logger.info(f"Deleted cache entry for postal code {postal_code}")
                    return True
                else:
                    logger.info(f"No cache entry found for postal code {postal_code}")
                    return False
                    
        except sqlite3.Error as e:
            logger.error(f"Error deleting cached data for {postal_code}: {e}")
            return False


# Global cache manager instance
cache_manager = CacheManager()
