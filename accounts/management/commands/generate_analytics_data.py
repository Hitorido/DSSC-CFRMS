"""
Management command to generate synthetic analytics data for dashboards.

This command creates sample reservations and maintenance records
to populate analytics dashboards with meaningful data.

Usage:
    python manage.py generate_analytics_data
"""

from datetime import date, timedelta, time as dtime
from django.core.management.base import BaseCommand
from django.utils import timezone

from facilities.models import Facility, FacilityMaintenance, FacilityType
from reservations.models import Reservation
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = 'Generate synthetic analytics data for dashboard display'

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=100,
            help='Number of reservations to create'
        )

    def handle(self, *args, **options):
        self.stdout.write("Generating analytics data...")
        
        count = options['count']
        
        # Ensure we have facilities
        facilities = Facility.objects.filter(status=Facility.Status.AVAILABLE)
        if not facilities.exists():
            self.stdout.write(self.style.WARNING('No available facilities found. Skipping data generation.'))
            return
        
        # Get or create test users
        requester, _ = User.objects.get_or_create(
            username='demo_requester',
            defaults={
                'email': 'demo@example.com',
                'role': User.Role.REQUESTER,
                'user_type': User.UserType.STUDENT,
                'is_active': True
            }
        )
        
        reviewer, _ = User.objects.get_or_create(
            username='demo_reviewer',
            defaults={
                'email': 'reviewer@example.com',
                'role': User.Role.STAFF,
                'is_active': True
            }
        )
        
        # Generate reservations with distributed times to avoid conflicts
        created = 0
        today = date.today()
        start_date = today + timedelta(days=1)  # Start from tomorrow (can't be in past)
        
        # Time slots to use (non-overlapping): 8-9, 10-11, 12-1, 2-3, 3-4, 4-5
        time_slots = [
            (dtime(8, 0), dtime(9, 0)),
            (dtime(10, 0), dtime(11, 0)),
            (dtime(12, 0), dtime(13, 0)),
            (dtime(14, 0), dtime(15, 0)),
            (dtime(15, 30), dtime(16, 30)),
            (dtime(17, 0), dtime(18, 0)),
        ]
        
        # Distribute across facilities and dates
        facility_idx = 0
        time_slot_idx = 0
        current_date = start_date
        
        while created < count:
            # Realistic pattern: 80% weekdays, 20% weekends
            is_weekday = current_date.weekday() < 5
            if not is_weekday and created % 5 != 0:
                current_date += timedelta(days=1)
                continue
            
            # Pick facility and time slot from rotation
            facility = facilities[facility_idx % len(facilities)]
            start_time, end_time = time_slots[time_slot_idx % len(time_slots)]
            
            # Move to next facility/time for next iteration
            time_slot_idx += 1
            if time_slot_idx >= len(time_slots):
                time_slot_idx = 0
                facility_idx += 1
            
            # Mixed status: 70% APPROVED, 20% PENDING, 10% COMPLETED
            status_rand = created % 100
            if status_rand < 70:
                status = Reservation.Status.APPROVED
                reviewed_by = reviewer
                reviewed_at = timezone.now()
            elif status_rand < 90:
                status = Reservation.Status.PENDING
                reviewed_by = None
                reviewed_at = None
            else:
                status = Reservation.Status.COMPLETED
                reviewed_by = reviewer
                reviewed_at = timezone.now()
            
            try:
                # Check if reservation already exists
                existing = Reservation.objects.filter(
                    facility=facility,
                    requested_by=requester,
                    reservation_date=current_date,
                    start_time=start_time,
                    end_time=end_time,
                ).exists()
                
                if not existing:
                    # Create reservation while bypassing validation for synthetic data
                    reservation = Reservation(
                        facility=facility,
                        requested_by=requester,
                        reservation_date=current_date,
                        start_time=start_time,
                        end_time=end_time,
                        purpose=f'Demo {facility.name} booking',
                        status=status,
                        reviewed_by=reviewed_by,
                        reviewed_at=reviewed_at,
                        is_synthetic=True,
                    )
                    # Save without calling full_clean() to bypass past date validation
                    super(Reservation, reservation).save(using=reservation._state.db)
                
                created += 1
            except Exception as e:
                # Skip on any validation error and move to next slot
                self.stdout.write(self.style.WARNING(f'⏭️  Skipped conflicting slot: {str(e)[:50]}'))
            
            # Move to next date when we've used all slots for current facility
            if time_slot_idx == 0:
                current_date += timedelta(days=1)
        
        self.stdout.write(self.style.SUCCESS(f'✓ Created {created} reservations'))
        
        # Generate some maintenance records
        maintenance_count = 0
        for facility in facilities[:3]:
            for i in range(3):
                maint_date = start_date + timedelta(days=i * 30)
                # Check if maintenance already exists
                existing = FacilityMaintenance.objects.filter(
                    facility=facility,
                    maintenance_date=maint_date,
                ).exists()
                
                if not existing:
                    maintenance = FacilityMaintenance(
                        facility=facility,
                        maintenance_date=maint_date,
                        title=f'Maintenance for {facility.name}',
                        description=f'Routine maintenance',
                        start_time=dtime(18, 0),
                        end_time=dtime(20, 0),
                        status=FacilityMaintenance.Status.SCHEDULED,
                        created_by=reviewer,
                        is_synthetic=True,
                    )
                    # Save without validation for synthetic data
                    super(FacilityMaintenance, maintenance).save(using=maintenance._state.db)
                    maintenance_count += 1
        
        self.stdout.write(self.style.SUCCESS(f'✓ Created {maintenance_count} maintenance records'))
        self.stdout.write(self.style.SUCCESS('✓ Analytics data generation complete!'))
