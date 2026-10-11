from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect, render

from accounts.decorators import admin_required
from .forms import FacilityCreateForm
from .models import Facility


@login_required
def facility_list_view(request):
    """
    Authenticated list of campus facilities.

    Backend-Frontend Contract:
    - Template: 'facilities/facility_list.html'
    - Context:
        - facilities: QuerySet of all Facility records, ordered by name, with facility_type selected
    """
    facilities = Facility.objects.select_related('facility_type').all().order_by('name')
    context = {
        'facilities': facilities,
    }
    return render(request, 'facilities/facility_list.html', context)


@admin_required
@transaction.atomic
def facility_create_view(request):
    form = FacilityCreateForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        facility = form.save()
        messages.success(request, f'{facility.name} has been added to campus facilities.')
        return redirect('facilities:facility_list')

    return render(request, 'facilities/facility_form.html', {
        'form': form,
        'facility_types': form.facility_types,
    })
