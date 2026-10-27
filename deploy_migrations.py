#!/usr/bin/env python
"""
Deploy script: Apply pending migrations to Aiven cloud database.
Run this once after deployment to add missing columns.

Usage:
    python deploy_migrations.py
"""

import os
import sys
import django
from pathlib import Path

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Setup Django
django.setup()

# Import Django management commands
from django.core.management import call_command

def apply_migrations():
    """Apply all pending migrations."""
    print("=" * 70)
    print("MIGRATION DEPLOYMENT")
    print("=" * 70)
    
    # Show current status
    print("\n1. Current migration status:")
    print("-" * 70)
    call_command('showmigrations', 'facilities')
    
    # Apply migrations
    print("\n2. Applying pending migrations...")
    print("-" * 70)
    try:
        call_command('migrate', verbosity=2)
        print("\n✅ Migrations applied successfully!")
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        sys.exit(1)
    
    # Verify
    print("\n3. Verification:")
    print("-" * 70)
    call_command('showmigrations', 'facilities')
    
    print("\n" + "=" * 70)
    print("✅ DEPLOYMENT COMPLETE")
    print("=" * 70)

if __name__ == '__main__':
    apply_migrations()
