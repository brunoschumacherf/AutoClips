from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver

from .models import TrackedSession


@receiver(user_logged_in)
def track_session(sender, request, user, **kwargs):
    key = request.session.session_key
    if key:
        TrackedSession.objects.update_or_create(session_key=key, defaults={
            "user": user, "user_agent": request.headers.get("User-Agent", "")[:200],
        })


@receiver(user_logged_out)
def forget_session(sender, request, user, **kwargs):
    if user and request.session.session_key:
        TrackedSession.objects.filter(user=user, session_key=request.session.session_key).delete()
