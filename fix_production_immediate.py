#!/usr/bin/env python
"""
EMERGENCY FIX: Add missing facility columns directly to production database.

This script applies the missing columns from migration 0004_add_facility_details.py
directly to the Aiven MySQL database without waiting for full migration framework.

Usage:
    python fix_production_immediate.py

Prerequisites:
    - DB_HOST, DB_USER, DB_PASSWORD, DB_NAME environment variables set
    - MySQL connection working
    - Database accessible
"""

import os
import sys
import mysql.connector
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')

def get_connection():
    """Create MySQL connection from environment variables."""
    return mysql.connector.connect(
        host=os.getenv('DB_HOST') or os.getenv('ANALYTICS_DB_HOST'),
        user=os.getenv('DB_USER') or os.getenv('ANALYTICS_DB_USER'),
        password=os.getenv('DB_PASSWORD') or os.getenv('ANALYTICS_DB_PASSWORD'),
        database=os.getenv('DB_NAME') or os.getenv('ANALYTICS_DB_NAME'),
        port=int(os.getenv('DB_PORT') or os.getenv('ANALYTICS_DB_PORT', 3306)),
        ssl_disabled=False,
    )

def fix_database():
    """Add missing columns to facilities_facility table."""
    
    connection = None
    try:
        print("=" * 70)
        print("PRODUCTION DATABASE FIX: Adding Missing Facility Columns")
        print("=" * 70)
        
        # Connect to database
        print("\n1. Connecting to database...")
        connection = get_connection()
        cursor = connection.cursor()
        print("✅ Connected to database")
        
        # List of columns to add
        columns_to_add = [
            {
                'name': 'equipment_list',
                'type': 'LONGTEXT',
                'default': None,  # TEXT columns cannot have defaults in MySQL
                'null': False
            },
            {
                'name': 'hours_of_operation',
                'type': 'VARCHAR(200)',
                'default': "'8am-6pm'",
                'null': False
            },
            {
                'name': 'noise_level',
                'type': 'VARCHAR(20)',
                'default': "'low'",
                'null': False
            },
            {
                'name': 'floor_number',
                'type': 'INT',
                'default': None,
                'null': True
            },
            {
                'name': 'building_code',
                'type': 'VARCHAR(10)',
                'default': "''",
                'null': False
            },
            {
                'name': 'has_wheelchair_access',
                'type': 'BOOLEAN',
                'default': 'TRUE',
                'null': False
            },
        ]
        
        # Check current columns
        print("\n2. Checking existing columns...")
        cursor.execute("""
            SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'facilities_facility' 
            AND TABLE_SCHEMA = DATABASE()
        """)
        existing_columns = set(row[0] for row in cursor.fetchall())
        print(f"   Found {len(existing_columns)} existing columns")
        
        # Add missing columns
        print("\n3. Adding missing columns...")
        added = 0
        for col in columns_to_add:
            if col['name'] in existing_columns:
                print(f"   ⏭️  Column {col['name']} already exists")
                continue
            
            # Build ALTER TABLE statement
            null_clause = '' if col['null'] else 'NOT NULL'
            default_clause = f"DEFAULT {col['default']}" if col['default'] else ''
            
            sql = f"""
                ALTER TABLE facilities_facility 
                ADD COLUMN {col['name']} {col['type']} {null_clause} {default_clause}
            """
            
            try:
                cursor.execute(sql)
                print(f"   ✅ Added column: {col['name']}")
                added += 1
            except mysql.connector.Error as e:
                print(f"   ❌ Failed to add {col['name']}: {e}")
        
        connection.commit()
        print(f"\n   Total columns added: {added}/{len(columns_to_add)}")
        
        # Create indexes
        print("\n4. Creating performance indexes...")
        indexes = [
            {
                'name': 'fac_noise_capacity_idx',
                'columns': 'noise_level, capacity'
            },
            {
                'name': 'fac_building_floor_idx',
                'columns': 'building_code, floor_number'
            },
        ]
        
        for idx in indexes:
            try:
                sql = f"CREATE INDEX {idx['name']} ON facilities_facility ({idx['columns']})"
                cursor.execute(sql)
                print(f"   ✅ Created index: {idx['name']}")
            except mysql.connector.Error as e:
                if 'Duplicate key name' in str(e):
                    print(f"   ⏭️  Index {idx['name']} already exists")
                else:
                    print(f"   ❌ Failed to create {idx['name']}: {e}")
        
        connection.commit()
        
        # Verify
        print("\n5. Verification - New columns:")
        cursor.execute("""
            SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'facilities_facility' 
            AND TABLE_SCHEMA = DATABASE()
            AND COLUMN_NAME IN (
                'equipment_list', 'hours_of_operation', 'noise_level',
                'floor_number', 'building_code', 'has_wheelchair_access'
            )
            ORDER BY ORDINAL_POSITION
        """)
        
        for row in cursor.fetchall():
            col_name, col_type, nullable, default = row
            null_str = "NULL" if nullable == 'YES' else "NOT NULL"
            default_str = f"DEFAULT {default}" if default else ""
            print(f"   ✅ {col_name}: {col_type} {null_str} {default_str}")
        
        cursor.close()
        connection.close()
        
        print("\n" + "=" * 70)
        print("✅ DATABASE FIX COMPLETE")
        print("=" * 70)
        print("\nYou can now reload the application without errors.")
        print("The missing facility columns have been added to the database.")
        
    except mysql.connector.Error as e:
        print(f"\n❌ Database error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
    finally:
        if connection and connection.is_connected():
            connection.close()

if __name__ == '__main__':
    fix_database()
