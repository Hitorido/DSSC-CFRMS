#!/usr/bin/env python
"""
Test analytics API endpoints directly
"""
import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from analytics.services import (
    get_reservation_kpis,
    get_reservation_status_distribution,
    get_monthly_trends,
    get_facility_demand
)

print("=" * 70)
print("TESTING ANALYTICS API ENDPOINTS")
print("=" * 70)

# Test 1: KPIs
print("\n1. Testing get_reservation_kpis()...")
try:
    kpis = get_reservation_kpis()
    print("✓ SUCCESS")
    print(json.dumps(kpis, indent=2, default=str))
except Exception as e:
    print(f"✗ FAILED: {type(e).__name__}: {e}")

# Test 2: Status Distribution
print("\n2. Testing get_reservation_status_distribution()...")
try:
    distribution = get_reservation_status_distribution()
    print("✓ SUCCESS")
    print(json.dumps(distribution, indent=2, default=str))
except Exception as e:
    print(f"✗ FAILED: {type(e).__name__}: {e}")

# Test 3: Monthly Trends
print("\n3. Testing get_monthly_trends()...")
try:
    trends = get_monthly_trends()
    print("✓ SUCCESS")
    print(json.dumps(trends, indent=2, default=str))
except Exception as e:
    print(f"✗ FAILED: {type(e).__name__}: {e}")

# Test 4: Facility Demand
print("\n4. Testing get_facility_demand()...")
try:
    demand = get_facility_demand()
    print("✓ SUCCESS")
    if demand:
        print(f"  Facilities: {len(demand)}")
        print(json.dumps(demand[:2], indent=2, default=str))
    else:
        print("  (empty)")
except Exception as e:
    print(f"✗ FAILED: {type(e).__name__}: {e}")

print("\n" + "=" * 70)
