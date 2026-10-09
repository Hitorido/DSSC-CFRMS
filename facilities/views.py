from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import staff_or_admin_required
from .forms import FacilityMaintenanceForm
from .models import Facility, FacilityMaintenance, FacilityType


@login_required
def facility_list_view(request):
    """
    Authenticated list of campus facilities.

    Backend-Frontend Contract:
    - Template: 'facilities/facility_list.html'
    - Context:
        - facilities: QuerySet of all Facility records, ordered by name,
                      with facility_type pre-fetched via select_related
    """
    facilities = Facility.objects.select_related('facility_type').all()
    search = request.GET.get('search', '').strip()
    status = request.GET.get('status', '')
    facility_type = request.GET.get('facility_type', '')

    if search:
        facilities = facilities.filter(
            Q(name__icontains=search)
            | Q(location__icontains=search)
            | Q(facility_type__name__icontains=search)
        )
    if status in dict(Facility.Status.choices):
        facilities = facilities.filter(status=status)
    if facility_type:
        try:
            facilities = facilities.filter(facility_type_id=int(facility_type))
        except (TypeError, ValueError):
            facilities = facilities.none()

    facilities = facilities.order_by('name')
    context = {
        'facilities': facilities,
        'facility_statuses': Facility.Status.choices,
        'facility_types': FacilityType.objects.all(),
        'filters': {
            'search': search,
            'status': status,
            'facility_type': facility_type,
        },
    }
    return render(request, 'facilities/facility_list.html', context)


# ---------------------------------------------------------------------------
# Maintenance Management — STAFF / ADMIN only
# ---------------------------------------------------------------------------

@login_required
@staff_or_admin_required
def maintenance_list_view(request):
    """
    List all maintenance records, ordered by date descending.

    Backend-Frontend Contract:
    - Template: 'facilities/maintenance_list.html'
    - Context:
        - maintenance_records: QuerySet[FacilityMaintenance] with facility
                               pre-fetched, all statuses visible
    """
    maintenance_records = (
        FacilityMaintenance.objects
        .select_related('facility', 'created_by')
        .order_by('-maintenance_date', '-start_time')
    )
    return render(request, 'facilities/maintenance_list.html', {
        'maintenance_records': maintenance_records,
    })


@login_required
@staff_or_admin_required
def maintenance_create_view(request):
    """
    Allow STAFF / ADMIN to schedule a new facility maintenance window.

    GET:  Display blank FacilityMaintenanceForm.
    POST: Validate and save the maintenance record.

    Security:
    - created_by is ALWAYS assigned from request.user (server-side session).
    - status is NOT a form field; it defaults to SCHEDULED via the model.
    - form.save(commit=False) lets us inject created_by before the DB write.
    - All business-rule validation (time range, overlap with reservations,
      overlap with other maintenance) runs in FacilityMaintenance.clean()
      via model.save(). ValidationError is surfaced to the form.

    Backend-Frontend Contract:
    - Template: 'facilities/maintenance_form.html'
    - Context:
        - form: FacilityMaintenanceForm
    """
    if request.method == 'POST':
        form = FacilityMaintenanceForm(request.POST)
        if form.is_valid():
            maintenance = form.save(commit=False)
            maintenance.created_by = request.user
            try:
                maintenance.save()
                messages.success(
                    request,
                    f'Maintenance scheduled for {maintenance.facility.name} '
                    f'on {maintenance.maintenance_date}.'
                )
                return redirect('facilities:maintenance_detail', pk=maintenance.pk)
            except ValidationError as exc:
                form.add_error(None, exc)
    else:
        form = FacilityMaintenanceForm()

    return render(request, 'facilities/maintenance_form.html', {'form': form})


@login_required
@staff_or_admin_required
def maintenance_detail_view(request, pk):
    """
    Display full details of a single maintenance record.

    All STAFF and ADMIN users may view any maintenance record.

    Backend-Frontend Contract:
    - Template: 'facilities/maintenance_detail.html'
    - Context:
        - maintenance: FacilityMaintenance instance with facility and
                       created_by pre-fetched
    """
    maintenance = get_object_or_404(
        FacilityMaintenance.objects.select_related('facility', 'created_by'),
        pk=pk,
    )
    return render(request, 'facilities/maintenance_detail.html', {
        'maintenance': maintenance,
    })


@login_required
@staff_or_admin_required
def maintenance_complete_view(request, pk):
    """
    Mark a SCHEDULED maintenance window as COMPLETED.

    POST-only: GET returns 405. State-changing actions must not be triggered
    by link pre-fetching or GET navigation.

    Delegates entirely to FacilityMaintenance.complete(), which owns the
    lifecycle rule (only SCHEDULED → COMPLETED is valid). The view does not
    set status directly.

    Backend-Frontend Contract:
    - No dedicated template; POSTs from maintenance_detail.
    - On success: redirect to maintenance_detail with success message.
    - On invalid transition: redirect to maintenance_detail with error message.
    """
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    maintenance = get_object_or_404(FacilityMaintenance, pk=pk)

    try:
        maintenance.complete()
        messages.success(
            request,
            f'Maintenance #{maintenance.pk} marked as completed.'
        )
    except ValidationError as exc:
        messages.error(request, exc.message)

    return redirect('facilities:maintenance_detail', pk=pk)


@login_required
@staff_or_admin_required
def maintenance_cancel_view(request, pk):
    """
    Cancel a SCHEDULED maintenance window.

    POST-only: GET returns 405.

    Delegates entirely to FacilityMaintenance.cancel(), which owns the
    lifecycle rule (only SCHEDULED → CANCELLED is valid).

    Backend-Frontend Contract:
    - No dedicated template; POSTs from maintenance_detail.
    - On success: redirect to maintenance_list with success message.
    - On invalid transition: redirect to maintenance_detail with error message.
    """
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    maintenance = get_object_or_404(FacilityMaintenance, pk=pk)

    try:
        maintenance.cancel()
        messages.success(
            request,
            f'Maintenance #{maintenance.pk} has been cancelled.'
        )
        return redirect('facilities:maintenance_list')
    except ValidationError as exc:
        messages.error(request, exc.message)
        return redirect('facilities:maintenance_detail', pk=pk)
