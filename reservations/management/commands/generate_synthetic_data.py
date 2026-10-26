"""
Management command: generate_synthetic_data

Phase 5.5 - Synthetic User, Facility, Maintenance, and Reservation Generation
------------------------------------------------------------------------------
Generates realistic synthetic data for DSSC CFRMS analytics and testing:
  - Users: REQUESTER, STAFF, ADMIN (with unusable passwords)
  - Facility types and facilities
  - Maintenance windows (SCHEDULED/COMPLETED) with conflict avoidance
  - Reservations (APPROVED/PENDING/REJECTED/CANCELLED) spanning a
    configurable historical window around --reference-date

All generated records are marked with is_synthetic=True.
The generator is non-destructive: it refuses to run if synthetic records exist.

NOTE: created_at / updated_at are backfilled after bulk_create() using
QuerySet.update() + Case/When, which bypasses pre_save on MySQL safely.
reviewed_at is a regular DateTimeField, fully controlled by the generator.
All timestamps are timezone-aware (Asia/Manila).

SYNTHETIC DATA DISCLAIMER:
Academic calendar weights, facility demand distributions, status ratios,
and purpose text are synthetic assumptions for data generation only.
They do not represent verified DSSC statistics or operational data.

Usage:
    python manage.py generate_synthetic_data [options]

Options:
    --count N                 Reservations to generate (1-10000, default 5000)
    --seed N                  RNG seed for reproducibility (default 42)
    --reference-date YYYY-MM-DD  Anchor date for historical window (default 2026-10-01)
    --dry-run                 Report plan without writing anything
"""

import calendar
import random
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connections, transaction
from faker import Faker

# ---------------------------------------------------------------------------
# Local-only host identifiers
# ---------------------------------------------------------------------------
_LOCAL_DB_HOSTS = {'127.0.0.1', 'localhost', '::1', ''}

# ---------------------------------------------------------------------------
# DEFAULT REFERENCE DATE
# Fixed to October 2026 (Phase 5.5 implementation month).
# Using a fixed date ensures reproducibility regardless of run date.
# ---------------------------------------------------------------------------
_DEFAULT_REFERENCE_DATE = date(2026, 10, 1)

# ---------------------------------------------------------------------------
# SYNTHETIC ACADEMIC CALENDAR WEIGHTS (synthetic assumptions only)
# ---------------------------------------------------------------------------
_MONTHLY_WEIGHTS = {
    1: 7, 2: 8, 3: 6, 4: 4, 5: 5,
    6: 2, 7: 2, 8: 9, 9: 8, 10: 5, 11: 7, 12: 3,
}
_DOW_WEIGHTS = {0: 9, 1: 9, 2: 8, 3: 8, 4: 7, 5: 2, 6: 0}

# ---------------------------------------------------------------------------
# SYNTHETIC TIME SLOT TEMPLATES (synthetic assumptions only)
# (start_hour, start_min, duration_min, weight)
# ---------------------------------------------------------------------------
_TIME_SLOTS = [
    (7,  0,  60,  2), (7,  30, 90,  3),
    (8,  0,  60,  6), (8,  0,  90,  8),
    (9,  0,  60,  9), (9,  0,  120, 9),
    (10, 0,  60,  8), (10, 0,  90,  7),
    (11, 0,  60,  6),
    (12, 0,  60,  4),
    (13, 0,  60,  7), (13, 0,  120, 8),
    (14, 0,  60,  8), (14, 0,  90,  7),
    (15, 0,  60,  6), (15, 0,  90,  5),
    (16, 0,  60,  4),
    (17, 0,  60,  3),
    (18, 0,  90,  2),
]
_TIME_SLOT_POPULATION = [s for s in _TIME_SLOTS for _ in range(s[3])]

# ---------------------------------------------------------------------------
# SYNTHETIC STATUS DISTRIBUTION (synthetic assumptions only)
# 55% APPROVED, 15% REJECTED, 20% CANCELLED, 10% PENDING
# ---------------------------------------------------------------------------
_STATUS_POPULATION = (
    ['APPROVED'] * 55 +
    ['REJECTED'] * 15 +
    ['CANCELLED'] * 20 +
    ['PENDING'] * 10
)

# ---------------------------------------------------------------------------
# SYNTHETIC FACILITY TYPE DEMAND WEIGHTS (synthetic assumptions only)
# ---------------------------------------------------------------------------
_FACILITY_TYPE_DEMAND = {
    'Computer Laboratory': 9,
    'Classroom':           8,
    'Conference Room':     5,
    'Auditorium':          3,
    'Laboratory':          6,
    'Gymnasium':           3,
}
_DEFAULT_FACILITY_DEMAND = 4

# ---------------------------------------------------------------------------
# SYNTHETIC PURPOSE TEMPLATES keyed by facility type (synthetic assumptions only)
# ---------------------------------------------------------------------------
_PURPOSES_BY_TYPE = {
    'Computer Laboratory': [
        'BSIT Network Administration Lab',
        'Computer Programming Laboratory Class',
        'Web Development Workshop',
        'Database Management Practical Exam',
        'IT Capstone Project Defense',
        'Software Engineering Lab Session',
    ],
    'Classroom': [
        'BSED Methods of Teaching Lecture',
        'Business Administration Case Study',
        'Nursing Theory Review Session',
        'General Education Lecture',
        'Psychology Research Presentation',
        'Engineering Mathematics Class',
    ],
    'Conference Room': [
        'Faculty Senate Meeting',
        'Department Curriculum Review',
        'Student Council Executive Meeting',
        'Research Colloquium',
        'Faculty Development Workshop',
        'College Accreditation Planning',
    ],
    'Auditorium': [
        'College Recognition Ceremony',
        'Department General Assembly',
        'Career Fair Orientation',
        'Seminar on Campus Leadership',
        'Alumni Homecoming Program',
        'Institutional Convocation',
    ],
    'Laboratory': [
        'Nursing Skills Demonstration',
        'Science Research Experiment',
        'Chemistry Laboratory Practical',
        'Biology Field Specimen Analysis',
        'Engineering Design Experiment',
        'Medical Technology Practicum',
    ],
    'Gymnasium': [
        'NSTP Physical Training Activity',
        'Intramural Sports Event',
        'Physical Education Class',
        'College Foundation Day Program',
        'Student Leadership Retreat',
        'Campus-wide Sports Festival',
    ],
}
_DEFAULT_PURPOSES = [
    'Academic Activity', 'Department Event',
    'Student Organization Meeting', 'College Program',
    'Institutional activity',
]

# ---------------------------------------------------------------------------
# SYNTHETIC REJECTION REASONS (synthetic assumptions only)
# ---------------------------------------------------------------------------
_REJECTION_REASONS = [
    'Facility reserved for institutional accreditation activity.',
    'Overlapping event already approved by administration.',
    'Facility under preventive maintenance on requested date.',
    'Insufficient lead time; request submitted too close to event.',
    'Required supporting documents not submitted with request.',
    'Requesting department has outstanding facility obligations.',
    'Event conflicts with DSSC academic calendar activity.',
    'Capacity requirements exceed available facility space.',
]

_FUTURE_WINDOW_DAYS = 30


class Command(BaseCommand):
    help = (
        'Generate realistic synthetic reservation data for DSSC CFRMS analytics. '
        'Only operates on local development databases. '
        'All synthetic records are flagged with is_synthetic=True.'
    )

    # ------------------------------------------------------------------
    # Arguments
    # ------------------------------------------------------------------

    def add_arguments(self, parser):
        parser.add_argument(
            '--count', type=int, default=5000, metavar='N',
            help='Number of reservation records to generate (1-10000). Default: 5000.',
        )
        parser.add_argument(
            '--seed', type=int, default=42, metavar='N',
            help='Integer seed for the random number generator. Default: 42.',
        )
        parser.add_argument(
            '--reference-date', type=str, default=None, metavar='YYYY-MM-DD',
            help=(
                f'Anchor date for the historical reservation window. '
                f'Defaults to {_DEFAULT_REFERENCE_DATE.isoformat()}. '
                f'24-month historical window backward; '
                f'{_FUTURE_WINDOW_DAYS}-day future window for PENDING/pre-approved.'
            ),
        )
        parser.add_argument(
            '--dry-run', action='store_true', default=False,
            help='Validate and report without writing.',
        )
        parser.add_argument(
            '--clear', action='store_true', default=False,
            help='DEPRECATED: not implemented. Synthetic data cleanup requires manual review.',
        )
        parser.add_argument(
            '--with-notifications', action='store_true', default=False,
            help=(
                'Generate synthetic notifications for APPROVED and REJECTED '
                'synthetic reservations. Default: no notifications generated.'
            ),
        )
        parser.add_argument(
            '--analytics-db', action='store_true', default=False,
            help=(
                'Route all generation to the "analytics" database alias '
                'instead of "default". Requires the analytics alias to be '
                'configured in settings.DATABASES. Explicit opt-in only; '
                'the default behavior (local DB) is unchanged.'
            ),
        )

    # ------------------------------------------------------------------
    # Safety guards
    # ------------------------------------------------------------------

    def _check_environment(self):
        if not settings.DEBUG:
            raise CommandError('Refused: DEBUG=False. Local development databases only.')
        db_host = settings.DATABASES.get('default', {}).get('HOST', '')
        if db_host not in _LOCAL_DB_HOSTS:
            raise CommandError(
                f'Refused: database HOST is "{db_host}". Local addresses only.'
            )

    def _check_synthetic_records_exist(self):
        from django.contrib.auth import get_user_model
        from facilities.models import Facility, FacilityMaintenance, FacilityType
        from reservations.models import Reservation
        User = get_user_model()
        alias = self._db_alias
        models_to_check = [
            ('User', User), ('FacilityType', FacilityType), ('Facility', Facility),
            ('FacilityMaintenance', FacilityMaintenance), ('Reservation', Reservation),
        ]
        existing = {
            label: m.objects.using(alias).filter(is_synthetic=True).count()
            for label, m in models_to_check
            if m.objects.using(alias).filter(is_synthetic=True).count() > 0
        }
        if existing:
            summary = '\n'.join(f'  {lbl}: {cnt} records' for lbl, cnt in existing.items())
            raise CommandError(
                'Refused: Synthetic records already exist.\n'
                f'{summary}\n\n'
                'Remove synthetic records (is_synthetic=True) manually, then re-run.'
            )

    def _validate_arguments(self, options):
        count = options['count']
        if not (1 <= count <= 10000):
            raise CommandError(f'Invalid --count {count}. Must be 1-10000.')
        if options['seed'] < 0:
            raise CommandError(f'Invalid --seed {options["seed"]}. Must be non-negative.')
        if options['clear']:
            raise CommandError('Synthetic cleanup is not implemented yet.')

        raw_ref = options.get('reference_date')
        if raw_ref:
            try:
                ref_date = date.fromisoformat(raw_ref)
            except ValueError:
                raise CommandError(
                    f'Invalid --reference-date "{raw_ref}". Expected YYYY-MM-DD.'
                )
        else:
            ref_date = _DEFAULT_REFERENCE_DATE
        options['_reference_date'] = ref_date

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def _report_current_state(self, options):
        from django.contrib.auth import get_user_model
        from facilities.models import Facility, FacilityMaintenance, FacilityType
        from reservations.models import Reservation
        User = get_user_model()
        alias = self._db_alias
        self.stdout.write(f'\nCurrent database state (alias="{alias}"):')
        self.stdout.write(self.style.HTTP_INFO(
            f'  {"Model":<22}  {"Total":>6}  {"Synthetic":>9}  {"Real":>6}'
        ))
        self.stdout.write('  ' + '-' * 50)
        for label, model in [
            ('User', User), ('FacilityType', FacilityType), ('Facility', Facility),
            ('FacilityMaintenance', FacilityMaintenance), ('Reservation', Reservation),
        ]:
            total = model.objects.using(alias).count()
            synth = model.objects.using(alias).filter(is_synthetic=True).count()
            self.stdout.write(f'  {label:<22}  {total:>6}  {synth:>9}  {total - synth:>6}')
        self.stdout.write('')

    def _report_generation_plan(self, options):
        count = options['count']
        ref   = options['_reference_date']
        n_req   = max(10, count // 30)
        n_staff = max(2, n_req // 20)
        n_admin = 1
        n_ft    = 6
        n_fac   = max(8, count // 500)
        n_maint = max(10, count // 60)
        self.stdout.write('\nGeneration plan:')
        self.stdout.write(f'  --count          : {count}')
        self.stdout.write(f'  --seed           : {options["seed"]}')
        self.stdout.write(f'  --reference-date : {ref.isoformat()}')
        self.stdout.write(f'  --dry-run        : {options["dry_run"]}')
        self.stdout.write(
            f'  Historical window: {(ref - timedelta(days=365*2)).isoformat()} to {ref.isoformat()}'
        )
        self.stdout.write(
            f'  Future window    : {ref.isoformat()} to {(ref + timedelta(days=_FUTURE_WINDOW_DAYS)).isoformat()}'
        )
        self.stdout.write('')
        self.stdout.write('  Planned generation (synthetic assumptions):')
        self.stdout.write(f'    REQUESTER users        : ~{n_req}')
        self.stdout.write(f'    STAFF users            : ~{n_staff}')
        self.stdout.write(f'    ADMIN users            : ~{n_admin}')
        self.stdout.write(f'    Facility types         : ~{n_ft}')
        self.stdout.write(f'    Facilities             : ~{n_fac}')
        self.stdout.write(f'    Maintenance windows    : ~{n_maint} (estimated)')
        self.stdout.write(f'    Reservations           : exactly {count}')
        self.stdout.write('')

    # ------------------------------------------------------------------
    # Availability tracker
    # ------------------------------------------------------------------

    def _build_availability_tracker(self):
        from reservations.models import Reservation
        from facilities.models import FacilityMaintenance
        alias = self._db_alias
        tracker = {}
        for res in Reservation.objects.using(alias).filter(status__in=Reservation.BLOCKING_STATUSES):
            tracker.setdefault((res.facility_id, res.reservation_date), []).append(
                (res.start_time, res.end_time)
            )
        for maint in FacilityMaintenance.objects.using(alias).filter(status=FacilityMaintenance.Status.SCHEDULED):
            tracker.setdefault((maint.facility_id, maint.maintenance_date), []).append(
                (maint.start_time, maint.end_time)
            )
        return tracker

    def _interval_overlaps(self, s1, e1, s2, e2):
        return s1 < e2 and e1 > s2

    def _slot_is_free(self, facility_id, res_date, start_t, end_t, tracker):
        for bs, be in tracker.get((facility_id, res_date), []):
            if self._interval_overlaps(start_t, end_t, bs, be):
                return False
        return True

    def _claim_slot(self, facility_id, res_date, start_t, end_t, tracker):
        tracker.setdefault((facility_id, res_date), []).append((start_t, end_t))

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------

    def _generate_users(self, fake, rng, options):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        count   = options['count']
        n_req   = max(10, count // 30)
        n_staff = max(2, n_req // 20)
        n_admin = 1
        departments = [
            'BSIS', 'Education', 'Engineering', 'Business', 'Nursing',
            'Psychology', 'Law', 'Humanities', 'Science', 'Fine Arts', 'Administration',
        ]
        users = []
        for i in range(n_req):
            username = f'syn_req_{i:05d}_{rng.randint(1000, 9999)}'
            users.append(User(
                username=username, first_name=fake.first_name(), last_name=fake.last_name(),
                email=f'{username}@dssc.local', role=User.Role.REQUESTER,
                user_type=User.UserType.STUDENT,
                department=rng.choice(departments), is_synthetic=True,
            ))
        for i in range(n_staff):
            username = f'syn_staff_{i:05d}_{rng.randint(1000, 9999)}'
            users.append(User(
                username=username, first_name=fake.first_name(), last_name=fake.last_name(),
                email=f'{username}@dssc.local', role=User.Role.STAFF,
                user_type='', department='Facilities Management', is_synthetic=True,
            ))
        for i in range(n_admin):
            username = f'syn_admin_{i:05d}_{rng.randint(1000, 9999)}'
            users.append(User(
                username=username, first_name=fake.first_name(), last_name=fake.last_name(),
                email=f'{username}@dssc.local', role=User.Role.ADMIN,
                user_type='', department='Administration', is_synthetic=True,
            ))
        for u in users:
            u.set_unusable_password()
        return User.objects.using(self._db_alias).bulk_create(users, batch_size=500)

    # ------------------------------------------------------------------
    # Facilities
    # ------------------------------------------------------------------

    def _generate_facilities(self, fake, rng, options):
        from facilities.models import Facility, FacilityType
        alias = self._db_alias
        count = options['count']
        n_fac = max(8, count // 500)
        facility_types_data = [
            ('Computer Laboratory', 'Facilities with networked workstations and software'),
            ('Classroom',           'Standard lecture rooms with basic AV equipment'),
            ('Conference Room',     'Meeting spaces for small groups and seminars'),
            ('Auditorium',          'Large capacity venues for presentations and events'),
            ('Laboratory',          'Specialized experimental and research facilities'),
            ('Gymnasium',           'Physical fitness and recreational spaces'),
        ]
        facility_types = []
        for name, desc in facility_types_data:
            ft, _ = FacilityType.objects.using(alias).get_or_create(
                name=name, defaults={'description': desc, 'is_synthetic': True},
            )
            facility_types.append(ft)
        locations = [
            'Admin Building', 'IT Building', 'Science Hall',
            'Arts & Design Center', 'Business Complex', 'Main Gym',
        ]
        facilities = []
        for i in range(n_fac):
            ftype    = rng.choice(facility_types)
            capacity = rng.choice([20, 30, 40, 50, 60, 80, 100, 120, 150, 200, 300])
            facilities.append(Facility(
                facility_type=ftype, name=f'syn_facility_{i:04d}',
                location=rng.choice(locations), capacity=capacity,
                description=fake.sentence(),
                status=Facility.Status.AVAILABLE, is_synthetic=True,
            ))
        Facility.objects.using(alias).bulk_create(facilities, batch_size=500)
        return list(Facility.objects.using(alias).filter(is_synthetic=True).select_related('facility_type'))

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def _generate_maintenance(self, fake, rng, options, tracker):
        from facilities.models import Facility, FacilityMaintenance
        from django.contrib.auth import get_user_model
        User = get_user_model()
        alias = self._db_alias
        count   = options['count']
        n_maint = max(10, count // 60)
        facilities = list(Facility.objects.using(alias).filter(is_synthetic=True))
        creators   = list(User.objects.using(alias).filter(
            is_synthetic=True, role__in=[User.Role.STAFF, User.Role.ADMIN]
        ))
        if not facilities or not creators:
            return 0
        ref_date = options['_reference_date']
        records  = []
        maintenance_titles = [
            'Annual electrical inspection', 'HVAC system maintenance',
            'Carpet cleaning and floor waxing', 'Plumbing inspection and repair',
            'Emergency lighting system test', 'Fire suppression system check',
            'Network infrastructure upgrade', 'Lighting fixture replacement',
            'Equipment calibration', 'Pest control service',
            'Wall repair and painting', 'Door and lock maintenance',
            'Stairwell safety inspection', 'Accessibility compliance check',
            'Contingency maintenance',
        ]
        maintenance_descriptions = [
            'Scheduled preventive maintenance', 'Safety compliance inspection',
            'Seasonal facility inspection', 'Emergency repair work',
            'System upgrade and modernization', 'Infrastructure assessment',
            'Regulatory inspection and certification',
            'Post-incident repair and restoration',
        ]
        for _ in range(n_maint):
            facility = rng.choice(facilities)
            creator  = rng.choice(creators)
            if rng.random() < 0.4:
                maint_date   = ref_date - timedelta(days=rng.randint(7, 180))
                maint_status = FacilityMaintenance.Status.COMPLETED
            else:
                maint_date   = ref_date + timedelta(days=rng.randint(1, 90))
                maint_status = FacilityMaintenance.Status.SCHEDULED
            slot = self._find_maintenance_slot(facility.id, maint_date, tracker, rng)
            if not slot:
                continue
            start_t, end_t = slot
            if maint_status == FacilityMaintenance.Status.SCHEDULED:
                self._claim_slot(facility.id, maint_date, start_t, end_t, tracker)
            records.append(FacilityMaintenance(
                facility=facility, title=rng.choice(maintenance_titles),
                description=rng.choice(maintenance_descriptions),
                maintenance_date=maint_date, start_time=start_t, end_time=end_t,
                status=maint_status, created_by=creator, is_synthetic=True,
            ))
        for i, r in enumerate(records):
            assert r.title and r.title.strip(),                             f'Maintenance[{i}]: blank title'
            assert r.end_time > r.start_time,                               f'Maintenance[{i}]: end <= start'
            assert r.created_by.role in [User.Role.STAFF, User.Role.ADMIN], f'Maintenance[{i}]: invalid creator role'
            assert r.is_synthetic,                                          f'Maintenance[{i}]: is_synthetic not set'
        FacilityMaintenance.objects.using(alias).bulk_create(records, batch_size=500)
        return len(records)

    def _find_maintenance_slot(self, facility_id, maint_date, tracker, rng):
        for _ in range(5):
            sh = rng.randint(8, 20)
            sm = rng.choice([0, 15, 30, 45])
            start_t = time(sh, sm)
            dur = rng.choice([30, 45, 60, 90, 120, 150, 180])
            end_dt = datetime.combine(maint_date, start_t) + timedelta(minutes=dur)
            if end_dt.date() != maint_date:
                continue
            end_t = end_dt.time()
            if self._slot_is_free(facility_id, maint_date, start_t, end_t, tracker):
                return (start_t, end_t)
        return None

    # ------------------------------------------------------------------
    # Reservations (Phase 5.5)
    # ------------------------------------------------------------------

    def _build_facility_weights(self, facilities):
        """Assign demand weights. NOTE: Synthetic assumptions only."""
        population, weights = [], []
        for f in facilities:
            w = _FACILITY_TYPE_DEMAND.get(f.facility_type.name, _DEFAULT_FACILITY_DEMAND)
            population.append(f)
            weights.append(w)
        return population, weights

    def _sample_date(self, rng, ref_date, months_back=24):
        """Sample a historical date. NOTE: Synthetic weights only."""
        month_candidates, month_wts = [], []
        for m_offset in range(months_back):
            total_months = ref_date.year * 12 + (ref_date.month - 1) - m_offset
            yr = total_months // 12
            mo = total_months % 12 + 1
            month_candidates.append((yr, mo))
            month_wts.append(_MONTHLY_WEIGHTS.get(mo, 4))
        yr, mo = rng.choices(month_candidates, weights=month_wts, k=1)[0]
        _, days_in_month = calendar.monthrange(yr, mo)
        day_candidates, day_wts = [], []
        for d in range(1, days_in_month + 1):
            try:
                candidate = date(yr, mo, d)
            except ValueError:
                continue
            if candidate > ref_date:
                continue
            dow = candidate.weekday()
            w   = _DOW_WEIGHTS.get(dow, 0)
            if w == 0:
                continue
            day_candidates.append(candidate)
            day_wts.append(w)
        if not day_candidates:
            return ref_date
        return rng.choices(day_candidates, weights=day_wts, k=1)[0]

    def _sample_future_date(self, rng, ref_date, window_days=_FUTURE_WINDOW_DAYS):
        candidates = []
        for offset in range(1, window_days + 1):
            d   = ref_date + timedelta(days=offset)
            dow = d.weekday()
            if _DOW_WEIGHTS.get(dow, 0) > 0:
                candidates.append(d)
        if not candidates:
            return ref_date + timedelta(days=1)
        return rng.choice(candidates)

    def _sample_time_slot(self, rng):
        sh, sm, dur, _ = rng.choice(_TIME_SLOT_POPULATION)
        start_t = time(sh, sm)
        end_dt  = datetime.combine(date.today(), start_t) + timedelta(minutes=dur)
        return start_t, end_dt.time()

    def _make_aware(self, naive_dt):
        return naive_dt.replace(tzinfo=ZoneInfo(settings.TIME_ZONE))

    def _generate_submission_dt(self, rng, res_date, ref_date=None):
        """
        Synthetic created_at: 1-14 days before event, business hours.
        Clamped so that submission never occurs after the reference date
        (the simulated 'now'). For future-dated reservations, submission
        is between ref_date-14 and ref_date.
        """
        days_before = rng.randint(1, 14)
        submit_date = res_date - timedelta(days=days_before)
        # Clamp: submission must not occur after the simulated current date
        if ref_date is not None and submit_date > ref_date:
            submit_date = ref_date - timedelta(days=rng.randint(0, min(days_before, 7)))
        while submit_date.weekday() == 6:
            submit_date -= timedelta(days=1)
        # Final clamp: submit_date must be before res_date
        if submit_date >= res_date:
            submit_date = res_date - timedelta(days=1)
        naive = datetime(
            submit_date.year, submit_date.month, submit_date.day,
            rng.randint(8, 17), rng.choice([0, 15, 30, 45]), 0,
        )
        return self._make_aware(naive)

    def _generate_reviewed_at(self, rng, res_date, created_at, ref_date=None):
        """
        Synthetic reviewed_at: after created_at, on or before event date.
        Clamped so review never occurs after the simulated reference date.
        This ensures notifications (which inherit reviewed_at as their
        created_at) do not carry future-information timestamps.
        """
        submit_date = created_at.date()
        window_end  = min(submit_date + timedelta(days=7), res_date)
        # Clamp: review must not occur after the simulated current date
        if ref_date is not None:
            window_end = min(window_end, ref_date)
        if window_end <= submit_date:
            review_date = submit_date
        else:
            days_range  = (window_end - submit_date).days
            review_date = submit_date + timedelta(days=rng.randint(0, max(0, days_range)))
            while review_date.weekday() == 6:
                review_date += timedelta(days=1)
        naive = datetime(
            review_date.year, review_date.month, review_date.day,
            rng.randint(8, 17), rng.choice([0, 15, 30, 45]), 0,
        )
        reviewed_dt = self._make_aware(naive)
        if reviewed_dt <= created_at:
            reviewed_dt = created_at + timedelta(hours=2)
        # Final clamp: ensure reviewed_dt does not exceed ref_date end-of-day
        if ref_date is not None:
            ref_end = self._make_aware(datetime(ref_date.year, ref_date.month, ref_date.day, 23, 59, 59))
            if reviewed_dt > ref_end:
                reviewed_dt = ref_end
        return reviewed_dt

    def _generate_updated_at(self, rng, status, created_at, reviewed_at, res_date):
        """Synthetic updated_at: PENDING=created_at, APPROVED/REJECTED=reviewed_at, CANCELLED=between."""
        if status in ('APPROVED', 'REJECTED'):
            return reviewed_at
        if status == 'PENDING':
            return created_at
        event_end = self._make_aware(datetime(
            res_date.year, res_date.month, res_date.day, 18, 0, 0,
        ))
        window_seconds = max(0, int((event_end - created_at).total_seconds()))
        if window_seconds <= 0:
            return created_at
        return created_at + timedelta(seconds=rng.randint(3600, max(3601, window_seconds)))

    def _generate_reservations(self, fake, rng, options, tracker):
        """
        Generate exactly --count synthetic reservations.

        bulk_create() bypasses clean() Rule 3 (past-date guard), which is a
        UX form validation, not a data-integrity invariant. All real invariants
        are enforced in _validate_reservation_batch().

        Timestamps (created_at/updated_at) are backfilled via QuerySet.update()
        + Case/When after each batch insert. MySQL does not return PKs from
        bulk_create, so we use max(pk) before/after to identify inserted rows.

        Tracker is updated immediately per APPROVED/PENDING record.

        If exactly --count cannot be produced after MAX_ATTEMPTS, raises
        CommandError and the entire transaction rolls back.
        """
        from django.contrib.auth import get_user_model
        from reservations.models import Reservation
        from facilities.models import Facility
        User = get_user_model()
        alias = self._db_alias

        count    = options['count']
        ref_date = options['_reference_date']

        requesters = list(User.objects.using(alias).filter(is_synthetic=True, role=User.Role.REQUESTER))
        reviewers  = list(User.objects.using(alias).filter(
            is_synthetic=True, role__in=[User.Role.STAFF, User.Role.ADMIN]
        ))
        facilities = list(Facility.objects.using(alias).filter(is_synthetic=True).select_related('facility_type'))
        if not requesters:
            raise CommandError('No synthetic REQUESTER users found.')
        if not reviewers:
            raise CommandError('No synthetic STAFF/ADMIN users found.')
        if not facilities:
            raise CommandError('No synthetic facilities found.')

        fac_pop, fac_wts = self._build_facility_weights(facilities)
        MAX_ATTEMPTS = count * 20
        attempts     = 0
        produced     = 0
        batch        = []
        ts_data      = []
        BATCH_SIZE   = 500

        while produced < count:
            if attempts >= MAX_ATTEMPTS:
                raise CommandError(
                    f'Could not generate {count} reservations after '
                    f'{MAX_ATTEMPTS} attempts (produced {produced}).'
                )
            attempts += 1

            # Status: synthetic distribution (55% APPROVED, 15% REJECTED, 20% CANCELLED, 10% PENDING)
            status = rng.choice(_STATUS_POPULATION)

            # Date: PENDING near ref_date; APPROVED 10% future; others historical
            if status == 'PENDING':
                if rng.random() < 0.5:
                    res_date = self._sample_future_date(rng, ref_date)
                else:
                    res_date = ref_date - timedelta(days=rng.randint(0, 14))
                    while res_date.weekday() == 6:
                        res_date -= timedelta(days=1)
            elif status == 'APPROVED' and rng.random() < 0.10:
                res_date = self._sample_future_date(rng, ref_date)
            else:
                res_date = self._sample_date(rng, ref_date)

            facility = rng.choices(fac_pop, weights=fac_wts, k=1)[0]
            start_t, end_t = self._sample_time_slot(rng)

            if status in ('APPROVED', 'PENDING'):
                if not self._slot_is_free(facility.id, res_date, start_t, end_t, tracker):
                    continue

            created_at_val   = self._generate_submission_dt(rng, res_date, ref_date)
            reviewed_at_val  = None
            rejection_reason = ''
            reviewer         = None
            if status in ('APPROVED', 'REJECTED'):
                reviewer        = rng.choice(reviewers)
                reviewed_at_val = self._generate_reviewed_at(rng, res_date, created_at_val, ref_date)
            if status == 'REJECTED':
                rejection_reason = rng.choice(_REJECTION_REASONS)
            updated_at_val = self._generate_updated_at(
                rng, status, created_at_val, reviewed_at_val, res_date
            )

            ftype_name   = facility.facility_type.name
            purpose_list = _PURPOSES_BY_TYPE.get(ftype_name, _DEFAULT_PURPOSES)
            purpose      = rng.choice(purpose_list)

            record = Reservation(
                requested_by=rng.choice(requesters), facility=facility,
                purpose=purpose, reservation_date=res_date,
                start_time=start_t, end_time=end_t, status=status,
                reviewed_by=reviewer, reviewed_at=reviewed_at_val,
                rejection_reason=rejection_reason, is_synthetic=True,
            )

            if status in ('APPROVED', 'PENDING'):
                self._claim_slot(facility.id, res_date, start_t, end_t, tracker)

            batch.append(record)
            ts_data.append((created_at_val, updated_at_val))
            produced += 1

            if len(batch) >= BATCH_SIZE:
                self._validate_reservation_batch(batch)
                self._flush_batch_with_backfill(batch, ts_data, Reservation)
                batch, ts_data = [], []
                self.stdout.write(f'  ... {produced}/{count} reservations inserted', ending='\r')

        if batch:
            self._validate_reservation_batch(batch)
            self._flush_batch_with_backfill(batch, ts_data, Reservation)

        self.stdout.write('')
        return produced

    def _flush_batch_with_backfill(self, batch, ts_data, ReservationModel):
        """
        Insert via bulk_create(), then backfill created_at/updated_at via
        QuerySet.update() + Case/When.

        MySQL has no RETURNING clause, so bulk_create does not set PKs.
        Strategy: use SELECT LAST_INSERT_ID() on the same connection to get
        the first auto-increment PK from our INSERT. MySQL guarantees that
        all rows in a single INSERT VALUES statement get consecutive
        auto-increment IDs, even with innodb_autoinc_lock_mode=2.

        LAST_INSERT_ID() is connection-scoped: it returns the first
        auto-generated ID from the most recent INSERT on THIS connection,
        regardless of concurrent inserts by other connections. This is
        strictly safer than the previous max(pk) range approach, which
        could accidentally include rows inserted by another connection.

        Safety:
        - Exact PK identification via connection-scoped LAST_INSERT_ID().
        - Verifies consecutive PK count matches batch size (detects gaps).
        - Strictly is_synthetic=True filtered on the update.
        - Inside transaction.atomic().
        - Non-synthetic records never touched.
        - Raises CommandError on PK count mismatch.
        """
        from django.db.models import Case, DateTimeField, When

        alias = self._db_alias
        n = len(batch)
        ReservationModel.objects.using(alias).bulk_create(batch, batch_size=n)

        # Get the first auto-increment PK from our INSERT via LAST_INSERT_ID()
        # This is connection-scoped and not affected by other connections.
        # CRITICAL: bulk_create above used the connection for `alias`; the
        # cursor below MUST use the same alias for LAST_INSERT_ID() to be
        # consistent.
        with connections[alias].cursor() as cursor:
            cursor.execute('SELECT LAST_INSERT_ID()')
            first_pk = cursor.fetchone()[0]

        if not first_pk:
            raise CommandError(
                'LAST_INSERT_ID() returned 0 after bulk_create. '
                'Cannot identify inserted rows for timestamp backfill.'
            )

        # Compute expected consecutive PKs: first_pk, first_pk+1, ..., first_pk+n-1
        expected_pks = list(range(first_pk, first_pk + n))

        # Verify: fetch the actual rows at those PKs, filtered to is_synthetic
        actual_pks = list(
            ReservationModel.objects.using(alias).filter(
                pk__in=expected_pks,
                is_synthetic=True,
            ).order_by('pk').values_list('pk', flat=True)
        )

        if len(actual_pks) != n:
            raise CommandError(
                f'Backfill safety check failed: expected {n} consecutive PKs '
                f'starting at {first_pk}, but only {len(actual_pks)} found with '
                f'is_synthetic=True. Concurrent inserts may have interfered. '
                f'Aborting to preserve data integrity.'
            )

        # Build Case/When for exact PK-to-timestamp mapping
        created_cases = [When(pk=pk, then=ts[0]) for pk, ts in zip(expected_pks, ts_data)]
        updated_cases = [When(pk=pk, then=ts[1]) for pk, ts in zip(expected_pks, ts_data)]

        ReservationModel.objects.using(alias).filter(
            pk__in=expected_pks,
            is_synthetic=True,
        ).update(
            created_at=Case(*created_cases, output_field=DateTimeField()),
            updated_at=Case(*updated_cases, output_field=DateTimeField()),
        )

    def _validate_reservation_batch(self, batch):
        """Generator-side invariant checks before every bulk_create()."""
        from reservations.models import Reservation
        from django.contrib.auth import get_user_model
        from facilities.models import Facility
        User = get_user_model()

        for i, r in enumerate(batch):
            assert r.purpose and r.purpose.strip(), f'Reservation[{i}]: blank purpose'
            assert r.end_time > r.start_time, f'Reservation[{i}]: end <= start'
            assert r.is_synthetic, f'Reservation[{i}]: is_synthetic not set'
            assert r.requested_by.role == User.Role.REQUESTER, f'Reservation[{i}]: wrong requester role'
            assert r.facility.status == Facility.Status.AVAILABLE, f'Reservation[{i}]: facility not AVAILABLE'
            assert r.status in [s.value for s in Reservation.Status], f'Reservation[{i}]: invalid status'

            if r.status in (Reservation.Status.APPROVED, Reservation.Status.REJECTED):
                assert r.reviewed_by is not None, f'Reservation[{i}]: {r.status} but reviewed_by is None'
                assert r.reviewed_at is not None, f'Reservation[{i}]: {r.status} but reviewed_at is None'
                assert r.reviewed_at.tzinfo is not None, f'Reservation[{i}]: reviewed_at not tz-aware'
            else:
                assert r.reviewed_by is None, f'Reservation[{i}]: {r.status} but reviewed_by is set'

            if r.status == Reservation.Status.REJECTED:
                assert r.rejection_reason and r.rejection_reason.strip(), f'Reservation[{i}]: REJECTED but no reason'
            if r.status in (Reservation.Status.PENDING, Reservation.Status.CANCELLED):
                assert not (r.rejection_reason and r.rejection_reason.strip()), f'Reservation[{i}]: {r.status} but reason set'

    # ------------------------------------------------------------------
    # Data generation: Notifications (Phase 5.6 — optional)
    # ------------------------------------------------------------------

    def _generate_notifications(self, rng, options):
        """
        Generate synthetic notifications for APPROVED and REJECTED
        synthetic reservations. Only called when --with-notifications is set.

        Design:
        - One notification per synthetic APPROVED or REJECTED reservation
        - Recipient = reservation.requested_by (the REQUESTER)
        - Message matches production format exactly (from reservations/views.py)
        - created_at = reservation.reviewed_at (the review event timestamp)
        - is_read: based on age relative to reference_date (synthetic assumption)
        - is_synthetic=True on all records
        - Uses bulk_create() + LAST_INSERT_ID backfill (same as reservations)
        - No external delivery (no email/SMS/push)

        NOTE: Read probabilities are synthetic assumptions, not DSSC data.
        Older notifications: ~80% read. Recent: ~20-40% read.
        """
        from notifications.models import Notification
        from reservations.models import Reservation

        alias = self._db_alias
        ref_date = options['_reference_date']

        # Fetch all synthetic APPROVED and REJECTED reservations
        eligible = list(
            Reservation.objects.using(alias).filter(
                is_synthetic=True,
                status__in=[Reservation.Status.APPROVED, Reservation.Status.REJECTED],
            ).select_related('requested_by', 'facility')
        )

        if not eligible:
            return 0

        notifications = []
        ts_data = []  # parallel list of synthetic created_at values

        for res in eligible:
            # Build exact production message
            if res.status == Reservation.Status.APPROVED:
                message = (
                    f'Your reservation for {res.facility.name} on '
                    f'{res.reservation_date} has been approved.'
                )
            else:  # REJECTED
                message = (
                    f'Your reservation for {res.facility.name} on '
                    f'{res.reservation_date} was rejected. '
                    f'Reason: {res.rejection_reason}'
                )

            # is_read: based on notification age relative to reference_date
            # NOTE: Synthetic assumption — not DSSC user behavior data.
            age_days = (ref_date - res.reviewed_at.date()).days
            if age_days > 30:
                read_prob = 0.80    # older: ~80% read
            elif age_days > 7:
                read_prob = 0.50    # moderate age: ~50% read
            else:
                read_prob = 0.20    # recent: ~20% read
            is_read = rng.random() < read_prob

            # created_at = reviewed_at (the moment the notification was created)
            created_at_val = res.reviewed_at

            notifications.append(Notification(
                recipient=res.requested_by,
                reservation=res,
                message=message,
                is_read=is_read,
                is_synthetic=True,
            ))
            ts_data.append(created_at_val)

        # Validate all notification objects before bulk_create
        for i, n in enumerate(notifications):
            assert n.recipient is not None,                    f'Notification[{i}]: recipient is None'
            assert n.reservation is not None,                   f'Notification[{i}]: reservation is None'
            assert n.message and n.message.strip(),             f'Notification[{i}]: blank message'
            assert n.is_synthetic,                              f'Notification[{i}]: is_synthetic not set'
            assert n.reservation.is_synthetic,                  f'Notification[{i}]: linked to non-synthetic reservation'
            assert n.recipient.role == 'REQUESTER',             f'Notification[{i}]: recipient is not REQUESTER'

        # Batch insert with timestamp backfill
        BATCH_SIZE = 500
        total = 0
        for i in range(0, len(notifications), BATCH_SIZE):
            batch = notifications[i:i + BATCH_SIZE]
            batch_ts = ts_data[i:i + BATCH_SIZE]
            total += self._flush_notifications_batch(batch, batch_ts, Notification)
        return total

    def _flush_notifications_batch(self, batch, ts_data, NotificationModel):
        """
        Insert notification batch via bulk_create(), then backfill created_at
        via LAST_INSERT_ID + Case/When (same pattern as reservations).
        """
        from django.db.models import Case, DateTimeField, When

        alias = self._db_alias
        n = len(batch)
        NotificationModel.objects.using(alias).bulk_create(batch, batch_size=n)

        # LAST_INSERT_ID() is connection-scoped; must use the same alias
        # connection that bulk_create used above.
        with connections[alias].cursor() as cursor:
            cursor.execute('SELECT LAST_INSERT_ID()')
            first_pk = cursor.fetchone()[0]

        if not first_pk:
            raise CommandError(
                'LAST_INSERT_ID() returned 0 after notification bulk_create.'
            )

        expected_pks = list(range(first_pk, first_pk + n))

        actual_pks = list(
            NotificationModel.objects.using(alias).filter(
                pk__in=expected_pks,
                is_synthetic=True,
            ).order_by('pk').values_list('pk', flat=True)
        )

        if len(actual_pks) != n:
            raise CommandError(
                f'Notification backfill PK mismatch: expected {n}, '
                f'found {len(actual_pks)} in range starting at {first_pk}.'
            )

        created_cases = [
            When(pk=pk, then=ts) for pk, ts in zip(expected_pks, ts_data)
        ]

        NotificationModel.objects.using(alias).filter(
            pk__in=expected_pks,
            is_synthetic=True,
        ).update(
            created_at=Case(*created_cases, output_field=DateTimeField()),
        )
        return n

    # ------------------------------------------------------------------
    # Dry-run
    # ------------------------------------------------------------------

    def _plan_generation(self, options):
        count   = options['count']
        n_req   = max(10, count // 30)
        n_staff = max(2, n_req // 20)
        n_admin = 1
        n_ft    = 6
        n_fac   = max(8, count // 500)
        n_maint = max(10, count // 60)
        self.stdout.write(self.style.SUCCESS(
            'Dry-run validation successful. The following WOULD be generated:'
        ))
        self.stdout.write(f'  Users (REQUESTER)  : {n_req}')
        self.stdout.write(f'  Users (STAFF)      : {n_staff}')
        self.stdout.write(f'  Users (ADMIN)      : {n_admin}')
        self.stdout.write(f'  Facility Types     : {n_ft}')
        self.stdout.write(f'  Facilities         : {n_fac}')
        self.stdout.write(f'  Maintenance windows: ~{n_maint} (estimated)')
        self.stdout.write(f'  Reservations       : exactly {count}')
        if options.get('with_notifications'):
            n_notif = int(count * 0.70)  # ~70% are APPROVED+REJECTED
            self.stdout.write(f'  Notifications       : ~{n_notif} (estimated; APPROVED + REJECTED only)')
        else:
            self.stdout.write(f'  Notifications       : 0 (use --with-notifications to enable)')
        self.stdout.write(self.style.SUCCESS('No database writes were performed.'))
        self.stdout.write('')

    # ------------------------------------------------------------------
    # Analytics target validation (Phase 6.3)
    # ------------------------------------------------------------------

    def _check_analytics_target(self):
        """
        Validate the 'analytics' database alias before routing generation to it.

        Raises CommandError when:
          - The 'analytics' alias is not configured in settings.DATABASES.
          - The analytics database already contains non-synthetic (real) data.
          - The analytics database already contains synthetic data (rerun guard).

        This ensures --analytics-db is an explicit, safe opt-in that never
        contaminates a database holding real records.
        """
        from django.contrib.auth import get_user_model
        from facilities.models import Facility, FacilityMaintenance, FacilityType
        from reservations.models import Reservation

        if 'analytics' not in settings.DATABASES:
            raise CommandError(
                'Refused: --analytics-db requested but the "analytics" database '
                'alias is not configured. Set ANALYTICS_DB_* environment '
                'variables (see .env.example) and ensure TLS CA is provided '
                'for remote hosts.'
            )

        User = get_user_model()
        alias = 'analytics'
        models_to_check = [
            ('User', User), ('FacilityType', FacilityType), ('Facility', Facility),
            ('FacilityMaintenance', FacilityMaintenance), ('Reservation', Reservation),
        ]

        # 1. Reject if any non-synthetic (real) records exist.
        real_existing = {
            label: m.objects.using(alias).filter(is_synthetic=False).count()
            for label, m in models_to_check
            if m.objects.using(alias).filter(is_synthetic=False).count() > 0
        }
        if real_existing:
            summary = '\n'.join(f'  {lbl}: {cnt} real records' for lbl, cnt in real_existing.items())
            raise CommandError(
                'Refused: analytics database contains non-synthetic (real) records:\n'
                f'{summary}\n\n'
                'The analytics target must be empty of real data. Use a dedicated '
                'analytics database, not a copy of production.'
            )

        # 2. Reject if synthetic records already exist (rerun guard).
        synth_existing = {
            label: m.objects.using(alias).filter(is_synthetic=True).count()
            for label, m in models_to_check
            if m.objects.using(alias).filter(is_synthetic=True).count() > 0
        }
        if synth_existing:
            summary = '\n'.join(f'  {lbl}: {cnt} synthetic records' for lbl, cnt in synth_existing.items())
            raise CommandError(
                'Refused: Synthetic records already exist in the analytics database.\n'
                f'{summary}\n\n'
                'Remove synthetic records (is_synthetic=True) from the analytics '
                'database manually, then re-run.'
            )

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def handle(self, *args, **options):
        # Determine the target database alias.
        # --analytics-db is an explicit opt-in; default behavior is unchanged.
        if options.get('analytics_db'):
            self._db_alias = 'analytics'
            self._check_analytics_target()
        else:
            self._db_alias = 'default'
            self._check_environment()

        self._validate_arguments(options)
        self._report_current_state(options)
        self._report_generation_plan(options)

        if options['dry_run']:
            self._plan_generation(options)
            return

        self._check_synthetic_records_exist()

        self.stdout.write(self.style.SUCCESS('Generating synthetic records...'))
        self.stdout.write('')

        fake = Faker()
        fake.seed_instance(options['seed'])
        rng  = random.Random(options['seed'])

        try:
            with transaction.atomic(using=self._db_alias):
                users = self._generate_users(fake, rng, options)
                self.stdout.write(self.style.SUCCESS(f'Generated {len(users)} users'))

                facilities = self._generate_facilities(fake, rng, options)
                self.stdout.write(self.style.SUCCESS(f'Generated {len(facilities)} facilities'))

                tracker = self._build_availability_tracker()

                maint_count = self._generate_maintenance(fake, rng, options, tracker)
                self.stdout.write(self.style.SUCCESS(f'Generated {maint_count} maintenance windows'))

                res_count = self._generate_reservations(fake, rng, options, tracker)
                self.stdout.write(self.style.SUCCESS(f'Generated {res_count} reservations'))

                if options.get('with_notifications'):
                    notif_count = self._generate_notifications(rng, options)
                    self.stdout.write(self.style.SUCCESS(
                        f'Generated {notif_count} notifications'
                    ))
                else:
                    self.stdout.write(self.style.HTTP_INFO(
                        'Notifications: skipped (use --with-notifications to enable)'
                    ))

            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS(
                'Synthetic data generation completed successfully. '
                'All records marked with is_synthetic=True.'
            ))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Generation failed -- transaction rolled back: {e}'))
            raise
