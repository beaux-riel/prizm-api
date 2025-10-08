#!/usr/bin/env python3
"""
Database migration script to convert from JSON storage to individual columns.
Migrates from postal_code_cache (v2) to postal_code_cache_v3 with individual columns.
"""

import sqlite3
import json
import logging
import sys
import re
from datetime import datetime
from typing import Optional, Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_currency_to_int(value: Optional[str]) -> Optional[int]:
    """Convert currency string like '$95,199' to integer 95199."""
    if not value or value == '' or value == 'Unknown':
        return None
    
    # Remove dollar sign, commas, and any whitespace
    cleaned = re.sub(r'[$,\s]', '', str(value))
    
    try:
        return int(cleaned)
    except (ValueError, TypeError):
        logger.warning(f"Could not parse currency value: {value}")
        return None


def parse_status(status: Optional[str]) -> str:
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


def migrate_database(db_path: str = 'prizm_cache_v2.db', backup: bool = True) -> bool:
    """
    Migrate database from JSON storage to individual columns.
    
    Args:
        db_path: Path to the SQLite database
        backup: Whether to create a backup before migration
    
    Returns:
        True if migration successful, False otherwise
    """
    
    try:
        # Create backup if requested
        if backup:
            import shutil
            backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copy2(db_path, backup_path)
            logger.info(f"Created backup at: {backup_path}")
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if migration already done
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='postal_code_cache_v3'")
        if cursor.fetchone():
            logger.info("Migration already completed (postal_code_cache_v3 exists)")
            return True
        
        # Create new table with individual columns
        logger.info("Creating new table postal_code_cache_v3...")
        cursor.execute("""
            CREATE TABLE postal_code_cache_v3 (
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
        cursor.execute("CREATE INDEX idx_v3_expires_at ON postal_code_cache_v3 (expires_at)")
        cursor.execute("CREATE INDEX idx_v3_status ON postal_code_cache_v3 (status)")
        cursor.execute("CREATE INDEX idx_v3_confirmed ON postal_code_cache_v3 (confirmed)")
        cursor.execute("CREATE INDEX idx_v3_segment_number ON postal_code_cache_v3 (segment_number)")
        
        # Get all records from old table
        logger.info("Reading records from old table...")
        cursor.execute("""
            SELECT postal_code, data, cached_at, expires_at, 
                   CASE 
                       WHEN EXISTS (SELECT 1 FROM pragma_table_info('postal_code_cache') WHERE name='html_content')
                       THEN html_content 
                       ELSE NULL 
                   END as html_content
            FROM postal_code_cache
        """)
        
        records = cursor.fetchall()
        logger.info(f"Found {len(records)} records to migrate")
        
        # Migrate each record
        migrated = 0
        failed = 0
        
        for record in records:
            postal_code, data_json, cached_at, expires_at, html_content = record
            
            try:
                # Parse JSON data
                data = json.loads(data_json)
                
                # Handle legacy 'prizm_code' field (rename to segment_number)
                if 'prizm_code' in data and 'segment_number' not in data:
                    data['segment_number'] = data['prizm_code']
                
                # Extract and convert fields
                segment_number = data.get('segment_number')
                segment_name = data.get('segment_name')
                segment_description = data.get('segment_description')
                who_they_are = data.get('who_they_are')
                education = data.get('education')
                urbanity = data.get('urbanity')
                occupation = data.get('occupation')
                diversity = data.get('diversity')
                family_life = data.get('family_life')
                tenure = data.get('tenure')
                home_type = data.get('home_type')
                
                # Parse currency fields to integers
                average_household_income = parse_currency_to_int(data.get('average_household_income'))
                average_household_net_worth = parse_currency_to_int(data.get('average_household_net_worth'))
                
                # Parse and normalize status
                status = parse_status(data.get('status'))
                
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
                
                # Insert into new table
                cursor.execute("""
                    INSERT INTO postal_code_cache_v3 (
                        postal_code, segment_number, segment_name, segment_description,
                        who_they_are, average_household_income, education, urbanity,
                        average_household_net_worth, occupation, diversity, family_life,
                        tenure, home_type, status, confirmed, cached_at, expires_at, html_content
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    postal_code, segment_number, segment_name, segment_description,
                    who_they_are, average_household_income, education, urbanity,
                    average_household_net_worth, occupation, diversity, family_life,
                    tenure, home_type, status, False, cached_at, expires_at, html_content
                ))
                
                migrated += 1
                
            except Exception as e:
                logger.error(f"Failed to migrate record for {postal_code}: {e}")
                failed += 1
        
        # Drop old table and rename new one
        if migrated > 0:
            logger.info(f"Successfully migrated {migrated} records, {failed} failed")
            
            logger.info("Dropping old table and renaming new one...")
            cursor.execute("DROP TABLE postal_code_cache")
            cursor.execute("ALTER TABLE postal_code_cache_v3 RENAME TO postal_code_cache")
            
            # Rename indexes
            cursor.execute("DROP INDEX IF EXISTS idx_expires_at")
            cursor.execute("DROP INDEX IF EXISTS idx_v3_expires_at")
            cursor.execute("DROP INDEX IF EXISTS idx_v3_status")
            cursor.execute("DROP INDEX IF EXISTS idx_v3_confirmed")
            cursor.execute("DROP INDEX IF EXISTS idx_v3_segment_number")
            
            cursor.execute("CREATE INDEX idx_expires_at ON postal_code_cache (expires_at)")
            cursor.execute("CREATE INDEX idx_status ON postal_code_cache (status)")
            cursor.execute("CREATE INDEX idx_confirmed ON postal_code_cache (confirmed)")
            cursor.execute("CREATE INDEX idx_segment_number ON postal_code_cache (segment_number)")
            
            conn.commit()
            logger.info("Migration completed successfully!")
            
            # Verify migration
            cursor.execute("SELECT COUNT(*) FROM postal_code_cache")
            count = cursor.fetchone()[0]
            logger.info(f"Verified: {count} records in migrated table")
            
            return True
        else:
            logger.error("No records were migrated successfully")
            conn.rollback()
            return False
            
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        if 'conn' in locals():
            conn.rollback()
        return False
    finally:
        if 'conn' in locals():
            conn.close()


def verify_migration(db_path: str = 'prizm_cache_v2.db') -> None:
    """Verify the migration was successful by checking a few records."""
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check table structure
        cursor.execute("PRAGMA table_info(postal_code_cache)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        logger.info("New table columns:")
        for col in columns:
            logger.info(f"  {col[1]} {col[2]}")
        
        # Check a few records
        cursor.execute("""
            SELECT postal_code, segment_number, segment_name, 
                   average_household_income, status, confirmed
            FROM postal_code_cache 
            LIMIT 5
        """)
        
        logger.info("\nSample migrated records:")
        for record in cursor.fetchall():
            logger.info(f"  {record}")
            
    finally:
        conn.close()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--no-backup":
        success = migrate_database(backup=False)
    else:
        success = migrate_database(backup=True)
    
    if success:
        verify_migration()
        logger.info("\n✅ Migration completed successfully!")
        logger.info("Next steps:")
        logger.info("1. Test the application with the new schema")
        logger.info("2. Update the application code to use individual columns")
        logger.info("3. Remove the backup file once verified")
    else:
        logger.error("\n❌ Migration failed! Check the logs above for details.")
        sys.exit(1)