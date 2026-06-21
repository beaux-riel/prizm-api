#!/usr/bin/env python3
"""
Cache Manager for PRIZM API data - New schema with individual columns
Stores postal code data locally to reduce API calls to the PRIZM website
Data is cached for up to 3 months
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import os
import logging
import re

logger = logging.getLogger(__name__)

class CacheManager:
    """Manages local caching of PRIZM postal code data with individual columns"""
    
    def __init__(self, db_path: str = None, cache_duration_days: int = None):
        """
        Initialize the cache manager
        
        Args:
            db_path: Path to the SQLite database file
            cache_duration_days: Number of days to cache data (default: 90 days = 3 months)
        """
        self.db_path = db_path or os.environ.get("PRIZM_CACHE_DB_PATH", "prizm_cache_v2.db")
        self.cache_duration_days = cache_duration_days or int(os.environ.get("PRIZM_CACHE_DURATION_DAYS", "90"))
        self._init_database()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
        finally:
            conn.close()

    def _normalize_postal_code(self, postal_code: str) -> str:
        compact = postal_code.strip().upper().replace(" ", "")
        if len(compact) == 6 and re.fullmatch(r"[A-Z]\d[A-Z]\d[A-Z]\d", compact):
            return f"{compact[:3]} {compact[3:]}"
        return postal_code.strip().upper()
    
    def _parse_currency_to_int(self, value: Optional[str]) -> Optional[Any]:
        """Convert simple currency strings to integers; keep ranges as text."""
        if not value or value == '' or value == 'Unknown':
            return None
        
        # Remove dollar sign, commas, and any whitespace
        cleaned = re.sub(r'[$,\s]', '', str(value))
        
        try:
            return int(cleaned)
        except (ValueError, TypeError):
            return str(value).strip()
    
    def _format_currency_from_int(self, value: Optional[Any]) -> Optional[str]:
        """Convert integer 95199 to '$95,199'; return range labels unchanged."""
        if value is None:
            return None
        if isinstance(value, str):
            return value if value.startswith("$") else f"${value}"
        
        # Format with comma separators and dollar sign
        return f"${value:,}"
    
    def _normalize_status(self, status: Optional[str]) -> str:
        """Normalize status values to 'success', 'error', or 'invalid'."""
        if not status:
            return 'error'
        
        status_lower = status.lower()
        
        if 'success' in status_lower:
            return 'success'
        elif 'invalid' in status_lower and 'format' in status_lower:
            return 'invalid'
        else:
            return 'error'
    
    def _init_database(self):
        """Initialize the SQLite database with the required table"""
        try:
            db_dir = os.path.dirname(os.path.abspath(self.db_path))
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)

            with self._connect() as conn:
                cursor = conn.cursor()
                
                # Create the cache table with individual columns
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS postal_code_cache (
                        postal_code TEXT PRIMARY KEY,
                        segment_number TEXT,
                        segment_name TEXT,
                        segment_description TEXT,
                        who_they_are TEXT,
                        average_household_income INTEGER,
                        education TEXT,
                        urbanity TEXT,
                        average_household_net_worth INTEGER,
                        occupation TEXT,
                        diversity TEXT,
                        family_life TEXT,
                        tenure TEXT,
                        home_type TEXT,
                        status TEXT NOT NULL DEFAULT 'error',
                        confirmed BOOLEAN DEFAULT 0,
                        cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP NOT NULL,
                        html_content TEXT,
                        CONSTRAINT chk_status CHECK (status IN ('success', 'error', 'invalid'))
                    )
                """)
                
                # Create indexes for better performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_expires_at ON postal_code_cache (expires_at)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON postal_code_cache (status)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_confirmed ON postal_code_cache (confirmed)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_segment_number ON postal_code_cache (segment_number)")
                
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
            postal_code = self._normalize_postal_code(postal_code)
            
            with self._connect() as conn:
                cursor = conn.cursor()
                
                # Get the cached data if it exists and hasn't expired
                cursor.execute("""
                    SELECT postal_code, segment_number, segment_name, segment_description,
                           who_they_are, average_household_income, education, urbanity,
                           average_household_net_worth, occupation, diversity, family_life,
                           tenure, home_type, status, confirmed, cached_at, html_content
                    FROM postal_code_cache 
                    WHERE postal_code = ? AND expires_at > datetime('now')
                """, (postal_code,))
                
                result = cursor.fetchone()
                
                if result:
                    (pc, segment_number, segment_name, segment_description,
                     who_they_are, avg_income, education, urbanity,
                     avg_net_worth, occupation, diversity, family_life,
                     tenure, home_type, status, confirmed, cached_at, html_content) = result
                    
                    # Build the data dictionary
                    cached_data = {
                        'postal_code': pc,
                        'segment_number': segment_number,
                        'segment_name': segment_name,
                        'segment_description': segment_description,
                        'who_they_are': who_they_are,
                        'average_household_income': self._format_currency_from_int(avg_income),
                        'education': education,
                        'urbanity': urbanity,
                        'average_household_net_worth': self._format_currency_from_int(avg_net_worth),
                        'occupation': occupation,
                        'diversity': diversity,
                        'family_life': family_life,
                        'tenure': tenure,
                        'home_type': home_type,
                        'status': status
                    }
                    
                    # Remove None values for cleaner response
                    cached_data = {k: v for k, v in cached_data.items() if v is not None}
                    
                    logger.info(f"Cache hit for postal code {postal_code} (cached at {cached_at})")
                    
                    # Add cache metadata
                    cached_data['_cache_info'] = {
                        'cached_at': cached_at,
                        'from_cache': True,
                        'has_html': html_content is not None and len(html_content) > 0,
                        'confirmed': bool(confirmed)
                    }
                    
                    return cached_data
                else:
                    logger.info(f"Cache miss for postal code {postal_code}")
                    return None
                    
        except sqlite3.Error as e:
            logger.error(f"Error retrieving cached data for {postal_code}: {e}")
            return None
    
    def cache_data(self, postal_code: str, data: Dict[Any, Any], custom_duration_days: Optional[int] = None, html_content: Optional[str] = None) -> bool:
        """
        Cache data for a postal code
        
        Args:
            postal_code: The postal code
            data: The data to cache
            custom_duration_days: Optional custom cache duration in days
            html_content: Optional HTML content to cache alongside the data
            
        Returns:
            True if caching was successful, False otherwise
        """
        try:
            postal_code = self._normalize_postal_code(postal_code)
            
            # Remove cache metadata if present
            data_to_cache = data.copy()
            data_to_cache.pop('_cache_info', None)
            
            # Calculate expiration date
            duration_days = custom_duration_days if custom_duration_days is not None else self.cache_duration_days
            expires_at = datetime.now() + timedelta(days=duration_days)
            
            # Handle legacy 'prizm_code' field
            if 'prizm_code' in data_to_cache and 'segment_number' not in data_to_cache:
                data_to_cache['segment_number'] = data_to_cache['prizm_code']
            
            # Parse currency fields to integers
            avg_income = self._parse_currency_to_int(data_to_cache.get('average_household_income'))
            avg_net_worth = self._parse_currency_to_int(data_to_cache.get('average_household_net_worth'))
            
            # Normalize status
            status = self._normalize_status(data_to_cache.get('status'))
            
            # Extract fields with proper NULL handling
            segment_number = data_to_cache.get('segment_number')
            segment_name = data_to_cache.get('segment_name')
            segment_description = data_to_cache.get('segment_description')
            who_they_are = data_to_cache.get('who_they_are')
            education = data_to_cache.get('education')
            urbanity = data_to_cache.get('urbanity')
            occupation = data_to_cache.get('occupation')
            diversity = data_to_cache.get('diversity')
            family_life = data_to_cache.get('family_life')
            tenure = data_to_cache.get('tenure')
            home_type = data_to_cache.get('home_type')
            
            # Handle empty strings as NULL
            segment_number = segment_number if segment_number and segment_number != '' else None
            segment_name = segment_name if segment_name and segment_name != '' else None
            segment_description = segment_description if segment_description and segment_description != '' else None
            who_they_are = who_they_are if who_they_are and who_they_are != '' else None
            education = education if education and education != '' else None
            urbanity = urbanity if urbanity and urbanity != '' else None
            occupation = occupation if occupation and occupation != '' else None
            diversity = diversity if diversity and diversity != '' else None
            family_life = family_life if family_life and family_life != '' else None
            tenure = tenure if tenure and tenure != '' else None
            home_type = home_type if home_type and home_type != '' else None
            
            with self._connect() as conn:
                cursor = conn.cursor()
                
                # Insert or replace with individual columns
                cursor.execute("""
                    INSERT OR REPLACE INTO postal_code_cache (
                        postal_code, segment_number, segment_name, segment_description,
                        who_they_are, average_household_income, education, urbanity,
                        average_household_net_worth, occupation, diversity, family_life,
                        tenure, home_type, status, confirmed, expires_at, html_content
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    postal_code, segment_number, segment_name, segment_description,
                    who_they_are, avg_income, education, urbanity,
                    avg_net_worth, occupation, diversity, family_life,
                    tenure, home_type, status, False, expires_at, html_content
                ))
                
                conn.commit()
                
                logger.info(f"Cached data for postal code {postal_code} (expires: {expires_at}, duration: {duration_days} days, has_html: {html_content is not None})")
                return True
                
        except sqlite3.Error as e:
            logger.error(f"Error caching data for {postal_code}: {e}")
            return False
    
    def confirm_data(self, postal_code: str) -> bool:
        """
        Mark cached data for a postal code as confirmed/verified
        
        Args:
            postal_code: The postal code to confirm
            
        Returns:
            True if confirmation was successful, False otherwise
        """
        try:
            postal_code = self._normalize_postal_code(postal_code)
            
            with self._connect() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    UPDATE postal_code_cache 
                    SET confirmed = 1
                    WHERE postal_code = ? AND expires_at > datetime('now')
                """, (postal_code,))
                
                updated_count = cursor.rowcount
                conn.commit()
                
                if updated_count > 0:
                    logger.info(f"Confirmed data for postal code {postal_code}")
                    return True
                else:
                    logger.info(f"No valid cache entry found for postal code {postal_code}")
                    return False
                    
        except sqlite3.Error as e:
            logger.error(f"Error confirming data for {postal_code}: {e}")
            return False
    
    def unconfirm_data(self, postal_code: str) -> bool:
        """
        Mark cached data for a postal code as unconfirmed
        
        Args:
            postal_code: The postal code to unconfirm
            
        Returns:
            True if unconfirmation was successful, False otherwise
        """
        try:
            postal_code = self._normalize_postal_code(postal_code)
            
            with self._connect() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    UPDATE postal_code_cache 
                    SET confirmed = 0
                    WHERE postal_code = ? AND expires_at > datetime('now')
                """, (postal_code,))
                
                updated_count = cursor.rowcount
                conn.commit()
                
                if updated_count > 0:
                    logger.info(f"Unconfirmed data for postal code {postal_code}")
                    return True
                else:
                    logger.info(f"No valid cache entry found for postal code {postal_code}")
                    return False
                    
        except sqlite3.Error as e:
            logger.error(f"Error unconfirming data for {postal_code}: {e}")
            return False
    
    def get_unconfirmed_entries(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get a list of unconfirmed cache entries
        
        Args:
            limit: Maximum number of entries to return
            
        Returns:
            List of unconfirmed entries
        """
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT postal_code, segment_number, segment_name, cached_at
                    FROM postal_code_cache 
                    WHERE confirmed = 0 AND expires_at > datetime('now') AND status = 'success'
                    ORDER BY cached_at DESC
                    LIMIT ?
                """, (limit,))
                
                results = cursor.fetchall()
                
                entries = []
                for row in results:
                    entries.append({
                        'postal_code': row[0],
                        'segment_number': row[1],
                        'segment_name': row[2],
                        'cached_at': row[3]
                    })
                
                return entries
                    
        except sqlite3.Error as e:
            logger.error(f"Error getting unconfirmed entries: {e}")
            return []
    
    def get_cached_html(self, postal_code: str) -> Optional[str]:
        """
        Retrieve cached HTML content for a postal code if it exists
        
        Args:
            postal_code: The postal code to look up
            
        Returns:
            String containing the HTML content if found, None otherwise
        """
        try:
            postal_code = self._normalize_postal_code(postal_code)
            
            with self._connect() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT html_content 
                    FROM postal_code_cache 
                    WHERE postal_code = ? AND expires_at > datetime('now')
                """, (postal_code,))
                
                result = cursor.fetchone()
                
                if result and result[0]:
                    logger.info(f"HTML cache hit for postal code {postal_code}")
                    return result[0]
                else:
                    logger.info(f"HTML cache miss for postal code {postal_code}")
                    return None
                    
        except sqlite3.Error as e:
            logger.error(f"Error retrieving cached HTML for {postal_code}: {e}")
            return None
    
    def cleanup_expired_cache(self) -> int:
        """
        Remove expired cache entries
        
        Returns:
            Number of entries removed
        """
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                
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
            with self._connect() as conn:
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
                
                # Get confirmed entries
                cursor.execute("""
                    SELECT COUNT(*) FROM postal_code_cache 
                    WHERE expires_at > datetime('now') AND confirmed = 1
                """)
                confirmed_entries = cursor.fetchone()[0]
                
                # Get entries by status
                cursor.execute("""
                    SELECT status, COUNT(*) 
                    FROM postal_code_cache 
                    WHERE expires_at > datetime('now')
                    GROUP BY status
                """)
                status_counts = dict(cursor.fetchall())
                
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
                    'confirmed_entries': confirmed_entries,
                    'unconfirmed_entries': valid_entries - confirmed_entries,
                    'status_breakdown': status_counts,
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
            with self._connect() as conn:
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
            postal_code = self._normalize_postal_code(postal_code)
            
            with self._connect() as conn:
                cursor = conn.cursor()
                
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
