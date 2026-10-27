#!/usr/bin/env python
"""
Verify production database is ready with all required columns and indexes.

This script checks:
1. All 6 facility columns exist in production database
2. All 2 performance indexes are created
3. Application can access facilities without OperationalError
4. Database connection is stable
"""

import os
import sys
import django
from django.conf import settings
from pathlib import Path

# Setup Django
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

django.setup()

from django.db import connection
from django.core.exceptions import ImproperlyConfigured
from facilities.models import Facility
from django.db import OperationalError

def check_database_connection():
    """Test basic database connection."""
    print("\n" + "=" * 70)
    print("STEP 1: Testing Database Connection")
    print("=" * 70)
    
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            if result:
                print("✓ Database connection is STABLE")
                return True
    except OperationalError as e:
        print(f"✗ OperationalError: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False

def check_facility_columns():
    """Verify all 6 required facility columns exist."""
    print("\n" + "=" * 70)
    print("STEP 2: Verifying All 6 Required Facility Columns")
    print("=" * 70)
    
    required_columns = [
        'equipment_list',
        'hours_of_operation',
        'noise_level',
        'floor_number',
        'building_code',
        'has_wheelchair_access'
    ]
    
    try:
        with connection.cursor() as cursor:
            # Get table information
            cursor.execute("""
                SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'facilities_facility'
                ORDER BY COLUMN_NAME
            """)
            existing_columns = {row[0] for row in cursor.fetchall()}
        
        print(f"\nFacility table columns found: {len(existing_columns)}")
        
        missing_columns = []
        for col in required_columns:
            if col in existing_columns:
                print(f"  ✓ {col}")
            else:
                print(f"  ✗ {col} (MISSING)")
                missing_columns.append(col)
        
        if not missing_columns:
            print(f"\n✓ All 6 required columns exist")
            return True
        else:
            print(f"\n✗ Missing columns: {', '.join(missing_columns)}")
            return False
            
    except OperationalError as e:
        print(f"✗ OperationalError: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False

def check_performance_indexes():
    """Verify both performance indexes exist."""
    print("\n" + "=" * 70)
    print("STEP 3: Verifying 2 Performance Indexes")
    print("=" * 70)
    
    required_indexes = [
        'fac_noise_capacity_idx',
        'fac_building_floor_idx'
    ]
    
    try:
        with connection.cursor() as cursor:
            # Get existing indexes
            cursor.execute("""
                SELECT DISTINCT INDEX_NAME FROM INFORMATION_SCHEMA.STATISTICS
                WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME = 'facilities_facility'
                AND INDEX_NAME NOT IN ('PRIMARY')
                ORDER BY INDEX_NAME
            """)
            existing_indexes = {row[0] for row in cursor.fetchall()}
        
        print(f"\nPerformance indexes found: {len(existing_indexes)}")
        
        missing_indexes = []
        for idx in required_indexes:
            if idx in existing_indexes:
                print(f"  ✓ {idx}")
            else:
                print(f"  ✗ {idx} (MISSING)")
                missing_indexes.append(idx)
        
        if not missing_indexes:
            print(f"\n✓ All 2 required indexes exist")
            return True
        else:
            print(f"\n✗ Missing indexes: {', '.join(missing_indexes)}")
            return False
            
    except OperationalError as e:
        print(f"✗ OperationalError: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False

def check_facility_access():
    """Verify application can access facilities without OperationalError."""
    print("\n" + "=" * 70)
    print("STEP 4: Verifying Application Can Access Facilities")
    print("=" * 70)
    
    try:
        # Test ORM access
        count = Facility.objects.count()
        print(f"✓ Successfully accessed Facility table via Django ORM")
        print(f"  Total facilities in database: {count}")
        
        # Test querying a facility if any exist
        if count > 0:
            facility = Facility.objects.first()
            print(f"\n  Sample facility: {facility.name}")
            print(f"    - Capacity: {facility.capacity}")
            print(f"    - Equipment: {facility.equipment_list}")
            print(f"    - Noise level: {facility.noise_level}")
            print(f"    - Floor: {facility.floor_number}")
            print(f"    - Building code: {facility.building_code}")
            print(f"    - Wheelchair access: {facility.has_wheelchair_access}")
        
        return True
        
    except OperationalError as e:
        print(f"✗ OperationalError when accessing Facility table: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False

def main():
    """Run all verification checks."""
    print("\n" + "=" * 70)
    print("PRODUCTION DATABASE VERIFICATION")
    print("=" * 70)
    
    # Determine which database we're using
    db_engine = settings.DATABASES['default']['ENGINE']
    db_name = settings.DATABASES['default']['NAME']
    db_host = settings.DATABASES['default'].get('HOST', 'local SQLite')
    
    print(f"\nDatabase Configuration:")
    print(f"  Engine: {db_engine}")
    print(f"  Host: {db_host}")
    print(f"  Database: {db_name}")
    
    results = {
        'connection': check_database_connection(),
        'columns': check_facility_columns(),
        'indexes': check_performance_indexes(),
        'facility_access': check_facility_access(),
    }
    
    # Print summary
    print("\n" + "=" * 70)
    print("VERIFICATION SUMMARY")
    print("=" * 70)
    print(f"Database Connection:     {'✓ PASS' if results['connection'] else '✗ FAIL'}")
    print(f"Facility Columns (6):    {'✓ PASS' if results['columns'] else '✗ FAIL'}")
    print(f"Performance Indexes (2): {'✓ PASS' if results['indexes'] else '✗ FAIL'}")
    print(f"Facility Access (ORM):   {'✓ PASS' if results['facility_access'] else '✗ FAIL'}")
    
    all_passed = all(results.values())
    print("\n" + "=" * 70)
    if all_passed:
        print("✓ PRODUCTION DATABASE IS READY")
        print("=" * 70)
        return 0
    else:
        print("✗ PRODUCTION DATABASE VERIFICATION FAILED")
        print("=" * 70)
        return 1

if __name__ == '__main__':
    sys.exit(main())
