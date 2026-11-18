from django import forms
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .models import UserProfile


class ProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ["display_name"]
        labels = {"display_name": "Nome de exibição"}


@login_required
def settings_page(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    form = ProfileForm(request.POST or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("settings")
    return render(request, "form.html", {"form": form, "title": "Configurações", "button": "Salvar perfil", "profile": True})


@login_required
def sessions(request):
    from django.contrib.sessions.models import Session
    from django.utils import timezone

    from .models import TrackedSession

    active = Session.objects.filter(expire_date__gt=timezone.now()).values("session_key")
    tracked = TrackedSession.objects.filter(user=request.user)
    tracked.exclude(session_key__in=active).delete()
    return render(request, "sessions.html", {
        "sessions": tracked.order_by("-created_at"), "current_key": request.session.session_key,
    })


@login_required
def revoke_session(request, public_id):
    from django.contrib.sessions.models import Session
    from django.db import transaction
    from django.http import HttpResponseNotAllowed
    from django.shortcuts import get_object_or_404

    from .models import TrackedSession

    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    with transaction.atomic():
        tracked = get_object_or_404(TrackedSession, user=request.user, public_id=public_id)
        Session.objects.filter(session_key=tracked.session_key).delete()
        tracked.delete()
    if tracked.session_key == request.session.session_key:
        request.session.flush()
        return redirect("landing")
    return redirect("sessions")
