from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import RegisterForm


@login_required
def home_view(request):
    """
    Authenticated landing view / placeholder dashboard.

    Backend-Frontend Contract:
    - Template: 'home.html'
    - Context:
        - user: request.user (accounts.User instance with username, role, department, etc.)
    """
    context = {
        'user': request.user,
    }
    return render(request, 'home.html', context)


def register_view(request):
    """
    Public self-registration for REQUESTER accounts.

    New accounts are always created with role=REQUESTER.
    Role elevation (STAFF / ADMIN) is handled by an Admin via /admin/.

    GET:  Display blank RegisterForm.
    POST: Validate, save, log the user in, redirect to home.
    """
    # Already logged-in users have no reason to register again
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')
    else:
        form = RegisterForm()

    return render(request, 'accounts/register.html', {'form': form})
