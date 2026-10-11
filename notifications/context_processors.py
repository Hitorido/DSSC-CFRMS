from .models import Notification


def unread_notification_count(request):
    """
    Context processor: injects 'unread_notification_count' into every
    template context for authenticated users.

    A context processor is a function that receives the current request and
    returns a dictionary. Django automatically merges this dictionary into
    every template context when the processor is listed in
    settings.TEMPLATES[...]['OPTIONS']['context_processors'].

    This allows base.html to display a notification badge on every page
    without each individual view having to query and pass the count manually.

    Returns 0 for anonymous users so templates can reference the variable
    safely without an {% if user.is_authenticated %} guard at every use.
    """
    if not request.user.is_authenticated:
        return {'unread_notification_count': 0}

    count = Notification.objects.filter(
        recipient=request.user,
        is_read=False,
    ).count()
    return {'unread_notification_count': count}
