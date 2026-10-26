c#!/usr/bin/env python
"""
Diagnose why analytics dashboard shows no data
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import connections
from reservations.models import Reservation
from facilities.models import Facility

print("=" * 70)
print("ANALYTICS DASHBOARD DIAGNOSTIC")
print("=" * 70)

conn = connections['analytics']

# Check total reservations
total = Reservation.objects.using('analytics').count()
synthetic = Reservation.objects.using('analytics').filter(is_synthetic=True).count()
non_synthetic = Reservation.objects.using('analytics').filter(is_synthetic=False).count()

print(f"\nTotal reservations in cloud DB: {total:,}")
print(f"  - Marked as synthetic: {synthetic:,}")
print(f"  - Marked as non-synthetic: {non_synthetic:,}")

# Check reservation statuses
print(f"\nReservation statuses:")
statuses = Reservation.objects.using('analytics').values('status').distinct()
for status_dict in statuses:
    status = status_dict['status']
    count = Reservation.objects.using('analytics').filter(status=status).count()
    synthetic_count = Reservation.objects.using('analytics').filter(status=status, is_synthetic=True).count()
    print(f"  {status}: {count} total ({synthetic_count} synthetic)")

# Show sample data
print(f"\nSample reservations:")
for res in Reservation.objects.using('analytics').all()[:5]:
    print(f"  ID: {res.id}")
    print(f"    Status: {res.status}")
    print(f"    is_synthetic: {res.is_synthetic}")
    print(f"    created_at: {res.created_at}")
    if hasattr(res, 'reviewed_at'):
        print(f"    reviewed_at: {res.reviewed_at}")
    print()

# THE PROBLEM
print("\n" + "=" * 70)
print("DIAGNOSIS:")
print("=" * 70)
if synthetic == 0 and total > 0:
    print("❌ PROBLEM FOUND!")
    print(f"   Data exists ({total} reservations) but is_synthetic=False")
    print(f"   Analytics filters for is_synthetic=True, so it sees 0 records")
    print("\n   SOLUTION:")
    print("   Run: python manage.py fix_synthetic_flag --database=analytics")
elif synthetic > 0:
    print("✓ Data looks good - synthetic flag is set correctly")
    print(f"   {synthetic:,} reservations with is_synthetic=True")
else:
    print("❌ No data at all - database is empty")
