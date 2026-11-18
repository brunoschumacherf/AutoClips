import base64
import hashlib
import secrets
import time

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.services import personal_workspace
from clips.views import lookup
from subscriptions.services import LimitExceeded
from . import instagram, tiktok, youtube
from .models import Publication, PublicationSchedule, SocialAccount
from .services import connect, serialize_tiktok_grant


@login_required
@require_POST
def youtube_connect(request):
    if not youtube.enabled():
        raise Http404
    state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    request.session["youtube_oauth"] = {"state": state, "verifier": verifier, "expires": time.time() + 600}
    return redirect(youtube.authorization_url(state, challenge))


@login_required
def youtube_callback(request):
    flow = request.session.pop("youtube_oauth", None)
    code = request.GET.get("code")
    if not youtube.enabled() or not flow or not code or flow["expires"] < time.time() or not secrets.compare_digest(flow["state"], request.GET.get("state", "")):
        messages.error(request, "A autorização expirou ou foi recusada.")
        return redirect("publications")
    try:
        from django.conf import settings

        grant = youtube.token(grant_type="authorization_code", code=code, redirect_uri=settings.YOUTUBE_REDIRECT_URI,
                              code_verifier=flow["verifier"])
        external_id, label = youtube.channel(grant["access_token"])
        connect(personal_workspace(request.user), external_id, label, grant["refresh_token"])
    except LimitExceeded as error:
        messages.error(request, str(error))
    except (OSError, ValueError, KeyError, IndexError):
        messages.error(request, "O YouTube não confirmou a conexão da conta.")
    else:
        messages.success(request, "Conta do YouTube conectada.")
    return redirect("publications")


@login_required
@require_POST
def instagram_connect(request):
    if not instagram.enabled():
        raise Http404
    state = secrets.token_urlsafe(32)
    request.session["instagram_oauth"] = {"state": state, "expires": time.time() + 600}
    return redirect(instagram.authorization_url(state))


@login_required
def instagram_callback(request):
    flow = request.session.pop("instagram_oauth", None)
    code = request.GET.get("code")
    if not instagram.enabled() or not flow or not code or flow["expires"] < time.time() or not secrets.compare_digest(flow["state"], request.GET.get("state", "")):
        messages.error(request, "A autorização expirou ou foi recusada.")
        return redirect("publications")
    try:
        external_id, label, grant = instagram.grant_for_code(code)
        connect(personal_workspace(request.user), external_id, label, grant, provider="instagram")
    except LimitExceeded as error:
        messages.error(request, str(error))
    except (OSError, ValueError, KeyError):
        messages.error(request, "O Instagram não confirmou a conexão da conta.")
    else:
        messages.success(request, "Conta do Instagram conectada.")
    return redirect("publications")


@login_required
@require_POST
def tiktok_connect(request):
    if not tiktok.enabled():
        raise Http404
    state = secrets.token_urlsafe(32)
    request.session["tiktok_oauth"] = {"state": state, "expires": time.time() + 600}
    return redirect(tiktok.authorization_url(state))


@login_required
def tiktok_callback(request):
    flow = request.session.pop("tiktok_oauth", None)
    code = request.GET.get("code")
    if not tiktok.enabled() or not flow or not code or flow["expires"] < time.time() or not secrets.compare_digest(flow["state"], request.GET.get("state", "")):
        messages.error(request, "A autorização expirou ou foi recusada.")
        return redirect("publications")
    try:
        external_id, label, grant = tiktok.grant_for_code(code)
        connect(personal_workspace(request.user), external_id, label, serialize_tiktok_grant(grant), provider="tiktok")
    except LimitExceeded as error:
        messages.error(request, str(error))
    except (OSError, ValueError, KeyError):
        messages.error(request, "O TikTok não confirmou a conexão da conta.")
    else:
        messages.success(request, "Conta do TikTok conectada.")
    return redirect("publications")


class ScheduleForm(forms.Form):
    account = forms.ModelChoiceField(label="Conta", queryset=SocialAccount.objects.none())
    title = forms.CharField(label="Título", max_length=100)
    description = forms.CharField(label="Descrição", max_length=5000, required=False, widget=forms.Textarea)
    authorized = forms.BooleanField(label="Autorizo o envio deste corte. No Instagram o Reel será público.")
    run_at = forms.DateTimeField(label="Horário UTC (em branco envia assim que possível)", required=False,
                                 widget=forms.DateTimeInput(attrs={"type": "datetime-local"}))

    def __init__(self, accounts, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["account"].queryset = accounts
        self.fields["account"].label_from_instance = lambda account: f"{account.label} · {account.provider}"


@login_required
def schedule(request, public_id):
    clip = lookup(request.user, public_id)
    version = clip.current_version
    providers = [name for name, adapter in (("youtube", youtube), ("instagram", instagram), ("tiktok", tiktok)) if adapter.enabled()]
    if not providers or not version or not version.output or clip.video.workspace.owner_id != request.user.pk:
        raise Http404
    accounts = SocialAccount.objects.filter(workspace=clip.video.workspace, provider__in=providers)
    form = ScheduleForm(accounts, request.POST or None, initial={"title": clip.title[:100]})
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        with transaction.atomic():
            publication = Publication.objects.create(account=data["account"], version=version, title=data["title"], description=data["description"])
            PublicationSchedule.objects.create(publication=publication, run_at=data["run_at"] or timezone.now())
        return redirect("publications")
    return render(request, "form.html", {"form": form, "title": "Agendar publicação", "button": "Agendar envio"})
