"""
Tests for Facility Admin Interface.

Validates that the FacilityAdmin correctly displays and manages facility fields including:
- Basic information (name, location, capacity, facility_type, status)
- Equipment & amenities (equipment_list, noise_level, has_wheelchair_access)
- Location details (floor_number, building_code, hours_of_operation)
- Computed fields (avg_reservation_duration)
- Backward compatibility with existing facilities
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.contrib.admin.sites import AdminSite
from datetime import datetime, timedelta
from decimal import Decimal

from facilities.models import Facility, FacilityType, FacilityMaintenance
from facilities.admin import FacilityAdmin
from reservations.models import Reservation

User = get_user_model()


class FacilityAdminTestCase(TestCase):
    """Test suite for FacilityAdmin interface."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a facility type
        self.facility_type = FacilityType.objects.create(
            name='Computer Laboratory',
            description='Computer lab with networked workstations'
        )

        # Create an admin user
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='password123',
            role='ADMIN'
        )

        # Create test users for reservations
        self.requester = User.objects.create_user(
            username='requester',
            email='requester@test.com',
            password='password123',
            role='REQUESTER'
        )

        self.reviewer = User.objects.create_user(
            username='reviewer',
            email='reviewer@test.com',
            password='password123',
            role='STAFF'
        )

        # Create a test facility
        self.facility = Facility.objects.create(
            facility_type=self.facility_type,
            name='IT ComLab 1',
            location='Admin Building 2nd Floor',
            capacity=30,
            description='Main computer laboratory for IT courses',
            status=Facility.Status.AVAILABLE,
            equipment_list='Projector, Whiteboard, A/C, Computers',
            hours_of_operation='8am-6pm weekdays, 9am-5pm weekends',
            noise_level=Facility.NoiseLevel.MEDIUM,
            floor_number=2,
            building_code='ADMIN',
            has_wheelchair_access=True,
            is_synthetic=False
        )

        # Create a synthetic facility
        self.synthetic_facility = Facility.objects.create(
            facility_type=self.facility_type,
            name='Synthetic Lab 1',
            location='Campus',
            capacity=25,
            status=Facility.Status.AVAILABLE,
            equipment_list='Computers, Projector, Internet',
            hours_of_operation='8am-6pm',
            noise_level=Facility.NoiseLevel.LOW,
            floor_number=1,
            building_code='SCI',
            has_wheelchair_access=False,
            is_synthetic=True
        )

        # Create admin client
        self.client = Client()
        self.client.login(username='admin', password='password123')

    def test_facility_admin_list_display(self):
        """Test that FacilityAdmin list_display shows required columns."""
        admin = FacilityAdmin(Facility, AdminSite())
        self.assertEqual(
            admin.list_display,
            ('name', 'capacity', 'equipment_truncated', 'status')
        )

    def test_facility_admin_list_filter(self):
        """Test that FacilityAdmin list_filter includes required filters."""
        admin = FacilityAdmin(Facility, AdminSite())
        expected_filters = ('facility_type', 'status', 'noise_level', 'has_wheelchair_access')
        self.assertEqual(admin.list_filter, expected_filters)

    def test_facility_admin_fieldsets(self):
        """Test that FacilityAdmin fieldsets are properly organized."""
        admin = FacilityAdmin(Facility, AdminSite())
        fieldsets = admin.fieldsets
        
        # Should have 6 fieldsets
        self.assertEqual(len(fieldsets), 6)
        
        # Check fieldset names
        fieldset_names = [fs[0] for fs in fieldsets]
        expected_names = [
            'Basic Information',
            'Details',
            'Equipment & Amenities',
            'Location',
            'Computed Analytics',
            'System'
        ]
        self.assertEqual(fieldset_names, expected_names)

    def test_basic_information_fieldset(self):
        """Test 'Basic Information' fieldset contains correct fields."""
        admin = FacilityAdmin(Facility, AdminSite())
        basic_info = admin.fieldsets[0]
        fields = basic_info[1]['fields']
        
        expected_fields = ('facility_type', 'name', 'location', 'status')
        self.assertEqual(fields, expected_fields)

    def test_details_fieldset(self):
        """Test 'Details' fieldset contains correct fields."""
        admin = FacilityAdmin(Facility, AdminSite())
        details = admin.fieldsets[1]
        fields = details[1]['fields']
        
        expected_fields = ('capacity', 'description', 'noise_level', 'has_wheelchair_access')
        self.assertEqual(fields, expected_fields)

    def test_equipment_amenities_fieldset(self):
        """Test 'Equipment & Amenities' fieldset contains correct fields."""
        admin = FacilityAdmin(Facility, AdminSite())
        equipment = admin.fieldsets[2]
        fields = equipment[1]['fields']
        
        expected_fields = ('equipment_list', 'hours_of_operation')
        self.assertEqual(fields, expected_fields)

    def test_location_fieldset(self):
        """Test 'Location' fieldset contains correct fields."""
        admin = FacilityAdmin(Facility, AdminSite())
        location = admin.fieldsets[3]
        fields = location[1]['fields']
        
        expected_fields = ('floor_number', 'building_code')
        self.assertEqual(fields, expected_fields)

    def test_computed_analytics_fieldset(self):
        """Test 'Computed Analytics' fieldset contains read-only field."""
        admin = FacilityAdmin(Facility, AdminSite())
        computed = admin.fieldsets[4]
        fields = computed[1]['fields']
        
        expected_fields = ('avg_reservation_duration_display',)
        self.assertEqual(fields, expected_fields)
        self.assertIn('Read-only values computed from reservation data', 
                      computed[1].get('description', ''))

    def test_system_fieldset(self):
        """Test 'System' fieldset contains system fields."""
        admin = FacilityAdmin(Facility, AdminSite())
        system = admin.fieldsets[5]
        fields = system[1]['fields']
        
        expected_fields = ('created_at', 'updated_at', 'is_synthetic')
        self.assertEqual(fields, expected_fields)
        self.assertIn('collapse', system[1].get('classes', []))

    def test_readonly_fields(self):
        """Test that readonly fields are properly configured."""
        admin = FacilityAdmin(Facility, AdminSite())
        expected_readonly = ('created_at', 'updated_at', 'avg_reservation_duration_display')
        self.assertEqual(admin.readonly_fields, expected_readonly)

    def test_equipment_truncated_method(self):
        """Test equipment_truncated display method."""
        admin = FacilityAdmin(Facility, AdminSite())
        
        # Test with equipment
        result = admin.equipment_truncated(self.facility)
        self.assertEqual(result, 'Projector, Whiteboard, A/C, Computers')
        
        # Test with long equipment list (truncate at 50 chars)
        long_equipment = 'A' * 60
        self.facility.equipment_list = long_equipment
        result = admin.equipment_truncated(self.facility)
        self.assertEqual(result, 'A' * 50 + '...')
        
        # Test with no equipment
        self.facility.equipment_list = ''
        result = admin.equipment_truncated(self.facility)
        self.assertEqual(result, '(none)')

    def test_avg_reservation_duration_display_no_reservations(self):
        """Test avg_reservation_duration_display with no reservations."""
        admin = FacilityAdmin(Facility, AdminSite())
        result = admin.avg_reservation_duration_display(self.facility)
        self.assertEqual(result, '(no reservations)')

    def test_avg_reservation_duration_display_with_reservations(self):
        """Test avg_reservation_duration_display with existing reservations."""
        from datetime import date, timedelta
        # Create some approved reservations using future dates
        future_date1 = date.today() + timedelta(days=30)
        future_date2 = date.today() + timedelta(days=31)
        
        Reservation.objects.create(
            requested_by=self.requester,
            facility=self.facility,
            purpose='Study session',
            reservation_date=future_date1,
            start_time='09:00',
            end_time='11:00',
            status='APPROVED',
            reviewed_by=self.reviewer,
            reviewed_at=datetime.now()
        )
        
        Reservation.objects.create(
            requested_by=self.requester,
            facility=self.facility,
            purpose='Lab work',
            reservation_date=future_date2,
            start_time='14:00',
            end_time='15:00',
            status='APPROVED',
            reviewed_by=self.reviewer,
            reviewed_at=datetime.now()
        )
        
        admin = FacilityAdmin(Facility, AdminSite())
        result = admin.avg_reservation_duration_display(self.facility)
        
        # Average of 2 hours and 1 hour = 1.5 hours
        self.assertIn('1h 30m', result)

    def test_create_facility_with_all_fields(self):
        """Test creating a facility through admin with all new fields."""
        new_facility = Facility.objects.create(
            facility_type=self.facility_type,
            name='New Facility',
            location='Building A',
            capacity=20,
            description='Test facility',
            status=Facility.Status.AVAILABLE,
            equipment_list='Projector, Whiteboard',
            hours_of_operation='9am-5pm',
            noise_level=Facility.NoiseLevel.LOW,
            floor_number=3,
            building_code='BLDG_A',
            has_wheelchair_access=True,
            is_synthetic=False
        )
        
        self.assertEqual(new_facility.name, 'New Facility')
        self.assertEqual(new_facility.equipment_list, 'Projector, Whiteboard')
        self.assertEqual(new_facility.noise_level, Facility.NoiseLevel.LOW)
        self.assertEqual(new_facility.floor_number, 3)
        self.assertEqual(new_facility.building_code, 'BLDG_A')
        self.assertTrue(new_facility.has_wheelchair_access)

    def test_update_facility_new_fields(self):
        """Test updating facility with new fields."""
        self.facility.equipment_list = 'Updated Equipment List'
        self.facility.noise_level = Facility.NoiseLevel.HIGH
        self.facility.floor_number = 5
        self.facility.building_code = 'NEW_BUILDING'
        self.facility.has_wheelchair_access = False
        self.facility.save()
        
        updated_facility = Facility.objects.get(pk=self.facility.pk)
        self.assertEqual(updated_facility.equipment_list, 'Updated Equipment List')
        self.assertEqual(updated_facility.noise_level, Facility.NoiseLevel.HIGH)
        self.assertEqual(updated_facility.floor_number, 5)
        self.assertEqual(updated_facility.building_code, 'NEW_BUILDING')
        self.assertFalse(updated_facility.has_wheelchair_access)

    def test_backward_compatibility_old_facility(self):
        """Test that old facilities without new fields still display correctly."""
        # Simulate an old facility (created before new fields)
        old_facility = Facility.objects.create(
            facility_type=self.facility_type,
            name='Old Facility',
            location='Old Building',
            capacity=15,
            status=Facility.Status.AVAILABLE,
            # New fields will use defaults
        )
        
        # Should not raise any errors
        admin = FacilityAdmin(Facility, AdminSite())
        equipment_display = admin.equipment_truncated(old_facility)
        self.assertEqual(equipment_display, '(none)')
        
        # Should display defaults
        self.assertEqual(old_facility.equipment_list, '')
        self.assertEqual(old_facility.noise_level, Facility.NoiseLevel.LOW)
        self.assertTrue(old_facility.has_wheelchair_access)

    def test_facility_admin_search_fields(self):
        """Test that admin search fields include building_code."""
        admin = FacilityAdmin(Facility, AdminSite())
        expected_search = ('name', 'location', 'description', 'building_code')
        self.assertEqual(admin.search_fields, expected_search)

    def test_all_facility_fields_optional(self):
        """Test that new facility fields are optional."""
        # Create facility with minimal required fields
        minimal_facility = Facility.objects.create(
            facility_type=self.facility_type,
            name='Minimal Facility',
            location='Test Location',
            capacity=10,
            status=Facility.Status.AVAILABLE,
            # All new fields omitted, should use defaults
        )
        
        self.assertEqual(minimal_facility.equipment_list, '')
        self.assertEqual(minimal_facility.hours_of_operation, '8am-6pm')
        self.assertEqual(minimal_facility.noise_level, Facility.NoiseLevel.LOW)
        self.assertIsNone(minimal_facility.floor_number)
        self.assertEqual(minimal_facility.building_code, '')
        self.assertTrue(minimal_facility.has_wheelchair_access)


class FacilityMaintenanceAdminTestCase(TestCase):
    """Test suite for FacilityMaintenance admin interface."""

    def setUp(self):
        """Set up test fixtures."""
        # Create facility type and facility
        self.facility_type = FacilityType.objects.create(
            name='Auditorium',
            description='Large meeting space'
        )
        
        self.facility = Facility.objects.create(
            facility_type=self.facility_type,
            name='Main Auditorium',
            location='Main Building',
            capacity=100,
            status=Facility.Status.AVAILABLE,
        )
        
        # Create admin user
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='password123',
            role='ADMIN'
        )
        
        # Create admin client
        self.client = Client()
        self.client.login(username='admin', password='password123')

    def test_maintenance_admin_list_display(self):
        """Test that FacilityMaintenanceAdmin list_display shows required columns."""
        from facilities.admin import FacilityMaintenanceAdmin
        admin = FacilityMaintenanceAdmin(FacilityMaintenance, AdminSite())
        
        expected_display = (
            'pk', 'facility', 'title', 'maintenance_date',
            'start_time', 'end_time', 'status', 'created_by', 'created_at'
        )
        self.assertEqual(admin.list_display, expected_display)

    def test_maintenance_admin_readonly_fields(self):
        """Test that created_by is readonly in maintenance admin."""
        from facilities.admin import FacilityMaintenanceAdmin
        admin = FacilityMaintenanceAdmin(FacilityMaintenance, AdminSite())
        
        expected_readonly = ('created_by', 'created_at', 'updated_at')
        self.assertEqual(admin.readonly_fields, expected_readonly)
