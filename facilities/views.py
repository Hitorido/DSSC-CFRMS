from django.contrib.auth.decorators import login_required
from django.shortcuts import render
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
