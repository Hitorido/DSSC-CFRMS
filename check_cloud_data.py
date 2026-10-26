#!/usr/bin/env python
"""
Quick check: Does cloud database have data?
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import connections
from reservations.models import Reservation
from facilities.models import Facility
from accounts.models import User

print("=" * 60)
print("CLOUD DATABASE DATA CHECK")
print("=" * 60)

try:
    # Connect to analytics database
    conn = connections['analytics']
    conn.ensure_connection()
    print("✓ Connected to cloud database\n")
    
    # Check data counts
    reservations_count = Reservation.objects.using('analytics').count()
    facilities_count = Facility.objects.using('analytics').count()
    users_count = User.objects.using('analytics').count()
    
    print(f"Reservations:  {reservations_count:,}")
    print(f"Facilities:    {facilities_count:,}")
    print(f"Users:         {users_count:,}")
    print()
    
    # Status
    total_data = reservations_count + facilities_count + users_count
    if total_data == 0:
        print("❌ CLOUD DATABASE IS EMPTY - No data found")
        print("\nTo populate with test data, run:")
        print("  python manage.py generate_synthetic_data --database=analytics")
    else:
        print(f"✓ CLOUD DATABASE HAS DATA - {total_data:,} records total")
        
        # Show sample data
        if reservations_count > 0:
            sample = Reservation.objects.using('analytics').first()
            print(f"\nSample reservation: {sample.facility.name} on {sample.reservation_date}")
        
        if facilities_count > 0:
            sample = Facility.objects.using('analytics').first()
            print(f"Sample facility: {sample.name}")
    
    print("\n" + "=" * 60)
    
except Exception as e:
    print(f"✗ Error connecting to cloud database:")
    print(f"  {type(e).__name__}: {e}")
    print("\nCheck your .env file:")
    print("  - ANALYTICS_DB_HOST")
    print("  - ANALYTICS_DB_PASSWORD")
    print("  - ANALYTICS_DB_SSL_CA path exists")
