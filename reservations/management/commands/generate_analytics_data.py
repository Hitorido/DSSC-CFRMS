"""
Management command: generate_analytics_data

Generates synthetic reservation and facility data with realistic patterns for analytics.
Data spans 6 months backward + 3 months forward with booking patterns reflecting real-world usage.

Features:
- 80% weekday bookings, 20% weekend bookings
- Peak hours: 70% of bookings in 2-5pm window, 30% other times
- Equipment-dependent variation based on facility type
- ~10% cancellation rate (90% APPROVED, 10% PENDING statuses)
- 1000+ reservations with realistic patterns
- 10+ facilities with varied types and equipment
- 50+ synthetic requesters
- Maintenance records with realistic scheduling

Usage:
    python manage.py generate_analytics_data [--months 6] [--seed 42]

Options:
    --months N     How many months back to generate (default: 6 back + 3 forward)
    --seed N       Random seed for reproducibility (default: 42)
"""

import random
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from faker import Faker

from accounts.models import User
from facilities.models import Facility, FacilityType, FacilityMaintenance
from reservations.models import Reservation


class Command(BaseCommand):
    help = (
        'Generate realistic synthetic reservation and facility data with patterns '
        'reflecting real-world usage across 6 months back + 3 months forward.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--months',
            type=int,
            default=6,
            metavar='N',
            help='How many months back to generate (default: 6 back + 3 forward). '
                 'Total data spans --months backward plus 3 months forward.',
        )
        parser.add_argument(
            '--seed',
            type=int,
            default=42,
            metavar='N',
            help='Random seed for reproducibility (default: 42).',
        )

    def handle(self, *args, **options):
        """Main command handler."""
        months_back = options['months']
        seed = options['seed']

        if months_back < 1:
            raise CommandError('--months must be at least 1.')

        # Initialize random and faker with seed
        random.seed(seed)
        rng = random.Random(seed)
        fake = Faker()
        Faker.seed(seed)

        self.stdout.write(
            self.style.SUCCESS(f'Generating analytics data: {months_back} months back + 3 months forward')
        )

        try:
            # Generate data
            facilities = self._create_facilities(fake, rng)
            self.stdout.write(f'  [OK] Created {len(facilities)} facilities')

            requesters = self._create_requesters(fake, rng, count=50)
            self.stdout.write(f'  [OK] Created {len(requesters)} requesters')

            reviewers = self._create_reviewers(fake, rng)
            self.stdout.write(f'  [OK] Created {len(reviewers)} reviewers')

            reservations_count = self._generate_reservations(
                fake, rng, facilities, requesters, reviewers, months_back
            )
            self.stdout.write(f'  [OK] Created {reservations_count} reservations')

            maintenance_count = self._generate_maintenance_records(
                fake, rng, facilities, reviewers, months_back
            )
            self.stdout.write(f'  [OK] Created {maintenance_count} maintenance records')

            # Verification
            self._verify_data_patterns(months_back)

            self.stdout.write(self.style.SUCCESS('[SUCCESS] Analytics data generation complete!'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'[ERROR] Error: {str(e)}'))
            raise

    def _create_facilities(self, fake, rng):
        """Create 10+ synthetic facilities with realistic types and equipment."""
        facilities = []
        
        # Check if we already have synthetic facilities
        existing_synthetic = Facility.objects.filter(is_synthetic=True).count()
        if existing_synthetic > 0:
            return list(Facility.objects.filter(is_synthetic=True))
        
        facility_types_config = [
            {
                'name': 'Computer Laboratory',
                'capacity_range': (20, 50),
                'equipment': 'Projector, Computers, A/C, Internet',
                'noise_level': Facility.NoiseLevel.SILENT,
                'count': 3,
            },
            {
                'name': 'Classroom',
                'capacity_range': (30, 80),
                'equipment': 'Projector, Whiteboard, Markers, A/C',
                'noise_level': Facility.NoiseLevel.LOW,
                'count': 4,
            },
            {
                'name': 'Conference Room',
                'capacity_range': (10, 30),
                'equipment': 'Projector, Whiteboard, Video Conference',
                'noise_level': Facility.NoiseLevel.MEDIUM,
                'count': 2,
            },
            {
                'name': 'Auditorium',
                'capacity_range': (100, 500),
                'equipment': 'Sound System, Projector, Stage Lighting',
                'noise_level': Facility.NoiseLevel.HIGH,
                'count': 2,
            },
        ]

        buildings = ['ADMIN', 'SCI', 'ARTS', 'ENG', 'BUS', 'HEALTH']
        
        for type_config in facility_types_config:
            facility_type, _ = FacilityType.objects.get_or_create(
                name=type_config['name'],
                defaults={'description': f'{type_config["name"]} facilities', 'is_synthetic': True}
            )

            for i in range(type_config['count']):
                capacity = rng.randint(*type_config['capacity_range'])
                floor = rng.randint(1, 5)
                building = rng.choice(buildings)

                facility = Facility.objects.create(
                    facility_type=facility_type,
                    name=f'{building}-{type_config["name"].split()[0]}-{floor:02d}-{i+1:02d}',
                    location=f'{building} Building, Floor {floor}',
                    capacity=capacity,
                    equipment_list=type_config['equipment'],
                    noise_level=type_config['noise_level'],
                    floor_number=floor,
                    building_code=building,
                    has_wheelchair_access=rng.random() < 0.9,  # 90% true
                    status=Facility.Status.AVAILABLE,
                    is_synthetic=True,
                )
                facilities.append(facility)

        return facilities

    def _create_requesters(self, fake, rng, count=50):
        """Create 50+ synthetic requesters (students/faculty)."""
        # Check if we already have synthetic requesters
        existing_count = User.objects.filter(is_synthetic=True, role=User.Role.REQUESTER).count()
        if existing_count >= count:
            return list(User.objects.filter(is_synthetic=True, role=User.Role.REQUESTER)[:count])
        
        requesters = []
        departments = [
            'BSIS', 'Education', 'Engineering', 'Business', 'Nursing',
            'Psychology', 'Law', 'Humanities', 'Science', 'Fine Arts',
        ]

        for i in range(count):
            username = f'syn_req_{i:04d}'
            try:
                user = User.objects.create(
                    username=username,
                    first_name=fake.first_name(),
                    last_name=fake.last_name(),
                    email=f'{username}@dssc.local',
                    role=User.Role.REQUESTER,
                    user_type=User.UserType.STUDENT,
                    department=rng.choice(departments),
                    is_synthetic=True,
                )
                user.set_unusable_password()
                user.save()
                requesters.append(user)
            except Exception:
                # Skip duplicates
                pass

        return requesters

    def _create_reviewers(self, fake, rng, count=5):
        """Create synthetic staff/admin reviewers."""
        # Check if we already have synthetic reviewers
        existing_count = User.objects.filter(is_synthetic=True, role__in=[User.Role.STAFF, User.Role.ADMIN]).count()
        if existing_count >= count:
            return list(User.objects.filter(is_synthetic=True, role__in=[User.Role.STAFF, User.Role.ADMIN])[:count])
        
        reviewers = []
        for i in range(count):
            username = f'syn_reviewer_{i:04d}'
            try:
                user = User.objects.create(
                    username=username,
                    first_name=fake.first_name(),
                    last_name=fake.last_name(),
                    email=f'{username}@dssc.local',
                    role=rng.choice([User.Role.STAFF, User.Role.ADMIN]),
                    department='Facilities Management',
                    is_synthetic=True,
                )
                user.set_unusable_password()
                user.save()
                reviewers.append(user)
            except Exception:
                # Skip duplicates
                pass

        return reviewers

    def _generate_reservations(self, fake, rng, facilities, requesters, reviewers, months_back):
        """Generate 1000+ reservations with realistic booking patterns."""
        today = timezone.localdate()
        start_date = today - timedelta(days=30 * months_back)
        end_date = today + timedelta(days=90)  # 3 months forward

        reservations = []
        current_date = start_date

        purposes = [
            'Class lecture',
            'Lab session',
            'Team meeting',
            'Exam preparation',
            'Project work',
            'Workshop',
            'Seminar',
            'Presentation',
            'Training session',
            'Student organization meeting',
        ]

        while current_date <= end_date:
            # 80% weekday, 20% weekend
            is_weekday = current_date.weekday() < 5
            
            if is_weekday:
                # More aggressive: 5-12 bookings on weekdays
                num_bookings = rng.randint(5, 12)
            else:
                # 1-3 bookings on weekends
                num_bookings = rng.randint(1, 3)

            for _ in range(num_bookings):
                facility = rng.choice(facilities)
                requester = rng.choice(requesters)
                reviewer = rng.choice(reviewers)

                # Peak hours: 70% in 2-5pm (14:00-17:00), 30% other times
                if rng.random() < 0.7:
                    # Peak hours: 2-5pm
                    hour = rng.randint(14, 16)
                    minute = rng.choice([0, 15, 30, 45])
                else:
                    # Off-peak: 8am-2pm, 5pm-6pm
                    hour = rng.choice([8, 9, 10, 11, 12, 13, 17, 18])
                    minute = rng.choice([0, 15, 30, 45])

                start_time = time(hour, minute)
                duration_hours = rng.randint(1, 3)
                
                # Calculate end time
                end_hour = hour + duration_hours
                if end_hour >= 24:
                    # Skip if goes past midnight
                    continue
                    
                end_time = time(end_hour, minute)

                # 90% APPROVED, 10% PENDING
                if rng.random() < 0.9:
                    status = Reservation.Status.APPROVED
                    reviewed_by = reviewer
                    reviewed_at = timezone.now() - timedelta(days=rng.randint(1, 7))
                else:
                    status = Reservation.Status.PENDING
                    reviewed_by = None
                    reviewed_at = None

                try:
                    reservation = Reservation.objects.create(
                        requested_by=requester,
                        facility=facility,
                        purpose=rng.choice(purposes),
                        reservation_date=current_date,
                        start_time=start_time,
                        end_time=end_time,
                        status=status,
                        reviewed_by=reviewed_by,
                        reviewed_at=reviewed_at,
                        is_synthetic=True,
                    )
                    reservations.append(reservation)
                except Exception:
                    # Skip conflicts
                    continue

            current_date += timedelta(days=1)

        return len(reservations)

    def _generate_maintenance_records(self, fake, rng, facilities, reviewers, months_back):
        """Generate 5-10 maintenance windows per month."""
        today = timezone.localdate()
        start_date = today - timedelta(days=30 * months_back)
        end_date = today + timedelta(days=90)

        maintenance_titles = [
            'HVAC system maintenance',
            'Electrical inspection',
            'Floor cleaning and waxing',
            'Equipment calibration',
            'Fire system inspection',
            'Network maintenance',
            'Lighting replacement',
            'Plumbing inspection',
            'General facility maintenance',
            'Preventive maintenance check',
        ]

        maintenance_records = []
        current_date = start_date

        while current_date <= end_date:
            # Generate 5-10 maintenance records per month
            if current_date.day == 1:  # First day of month
                num_maintenance = rng.randint(5, 10)
                for _ in range(num_maintenance):
                    facility = rng.choice(facilities)
                    creator = rng.choice(reviewers)

                    # Scheduled during low-occupancy times (early morning, late evening)
                    if rng.random() < 0.5:
                        hour = rng.randint(6, 8)  # Early morning
                    else:
                        hour = rng.randint(17, 19)  # Late evening

                    minute = rng.choice([0, 30])
                    start_time = time(hour, minute)
                    
                    duration = rng.randint(1, 3)
                    end_hour = min(hour + duration, 23)
                    end_time = time(end_hour, minute)

                    # Schedule for random day in this month
                    maint_day = rng.randint(1, 28)
                    try:
                        maint_date = current_date.replace(day=maint_day)
                    except ValueError:
                        continue

                    try:
                        maintenance = FacilityMaintenance.objects.create(
                            facility=facility,
                            title=rng.choice(maintenance_titles),
                            description=fake.sentence(),
                            maintenance_date=maint_date,
                            start_time=start_time,
                            end_time=end_time,
                            status=rng.choice([
                                FacilityMaintenance.Status.SCHEDULED,
                                FacilityMaintenance.Status.COMPLETED,
                            ]),
                            created_by=creator,
                            is_synthetic=True,
                        )
                        maintenance_records.append(maintenance)
                    except Exception:
                        # Skip conflicts
                        continue

            current_date += timedelta(days=1)

        return len(maintenance_records)

    def _verify_data_patterns(self, months_back):
        """Verify the generated data matches expected patterns."""
        today = timezone.localdate()
        start_date = today - timedelta(days=30 * months_back)

        # Verify reservation count
        total_reservations = Reservation.objects.filter(is_synthetic=True).count()
        self.stdout.write(f'\n  Verification:')
        self.stdout.write(f'    Total reservations: {total_reservations}')
        
        if total_reservations < 1000:
            self.stdout.write(
                self.style.WARNING(f'    Warning: Expected 1000+, got {total_reservations}')
            )

        # Verify facilities
        total_facilities = Facility.objects.filter(is_synthetic=True).count()
        self.stdout.write(f'    Total facilities: {total_facilities}')

        # Verify all marked as synthetic
        non_synthetic = Reservation.objects.filter(is_synthetic=False).count()
        self.stdout.write(f'    Non-synthetic reservations: {non_synthetic}')

        # Verify booking patterns
        weekday_count = 0
        weekend_count = 0
        for res in Reservation.objects.filter(is_synthetic=True):
            if res.reservation_date.weekday() < 5:
                weekday_count += 1
            else:
                weekend_count += 1

        total = weekday_count + weekend_count
        if total > 0:
            weekday_pct = (weekday_count / total) * 100
            self.stdout.write(f'    Weekday bookings: {weekday_pct:.1f}% (target: 80%)')

        # Verify peak hours
        peak_count = 0
        for res in Reservation.objects.filter(is_synthetic=True):
            if 14 <= res.start_time.hour <= 16:  # 2-5pm window
                peak_count += 1

        if total > 0:
            peak_pct = (peak_count / total) * 100
            self.stdout.write(f'    Peak hour bookings (2-5pm): {peak_pct:.1f}% (target: 70%)')

        # Verify status distribution
        approved = Reservation.objects.filter(
            is_synthetic=True, status=Reservation.Status.APPROVED
        ).count()
        pending = Reservation.objects.filter(
            is_synthetic=True, status=Reservation.Status.PENDING
        ).count()

        if total > 0:
            approved_pct = (approved / total) * 100
            self.stdout.write(f'    APPROVED reservations: {approved_pct:.1f}% (target: 90%)')
