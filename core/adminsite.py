from secrets import compare_digest

from django.conf import settings
from django.contrib.admin import AdminSite
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.utils.crypto import salted_hmac

SESSION_MARK = "cortalives_admin"


def admin_account_name():
    return "admin_" + salted_hmac("cortalives.admin.user", settings.ADMIN_USER).hexdigest()[:32]


def credential_version():
    return salted_hmac("cortalives.admin.session", f"{settings.ADMIN_USER}\0{settings.ADMIN_PASSWORD}").hexdigest()


class EnvironmentAdminForm(AuthenticationForm):
    def clean(self):
        username = self.cleaned_data.get("username", "")
        password = self.cleaned_data.get("password", "")
        address = self.request.META.get("REMOTE_ADDR", "")
        key = "admin-login:" + salted_hmac("cortalives.admin.ip", address).hexdigest()
        cache.add(key, 0, 300)
        try:
            attempts = cache.incr(key)
        except ValueError:
            cache.set(key, 1, 300)
            attempts = 1
        if attempts > 12:
            raise ValidationError("Muitas tentativas. Tente novamente em cinco minutos.")
        username_matches = compare_digest(username.encode(), settings.ADMIN_USER.encode())
        password_matches = compare_digest(password.encode(), settings.ADMIN_PASSWORD.encode())
        if not (settings.ADMIN_USER and settings.ADMIN_PASSWORD and username_matches and password_matches):
            raise self.get_invalid_login_error()

        user, _ = get_user_model().objects.get_or_create(username=admin_account_name(), defaults={
            "password": make_password(None), "is_staff": True, "is_superuser": True, "is_active": True,
        })
        if user.has_usable_password() or not (user.is_staff and user.is_superuser and user.is_active):
            raise self.get_invalid_login_error()
        user.backend = "django.contrib.auth.backends.ModelBackend"
        self.user_cache = user
        self.request.environment_admin_verified = True
        cache.delete(key)
        return self.cleaned_data


class CortaAdminSite(AdminSite):
    site_header = "Administração CortaLives"
    site_title = "CortaLives Admin"
    index_title = "Visão geral"
    login_form = EnvironmentAdminForm
    index_template = "admin/cortalives_index.html"

    def has_permission(self, request):
        return bool(
            settings.ADMIN_USER and settings.ADMIN_PASSWORD and super().has_permission(request)
            and request.user.get_username() == admin_account_name()
            and compare_digest(request.session.get(SESSION_MARK, ""), credential_version())
        )

    def login(self, request, extra_context=None):
        response = super().login(request, extra_context)
        if getattr(request, "environment_admin_verified", False) and request.user.is_authenticated:
            request.session[SESSION_MARK] = credential_version()
        return response

    def index(self, request, extra_context=None):
        from django.db.models import Sum
        from subscriptions.models import PixOrder
        from videos.models import Video

        orders = PixOrder.objects.all()
        context = {
            "review_count": orders.filter(status=PixOrder.Status.REVIEW).count(),
            "approved_total": orders.filter(status=PixOrder.Status.APPROVED).aggregate(total=Sum("amount"))["total"] or 0,
            "workspace_count": get_user_model().objects.filter(workspace__isnull=False).count(),
            "completed_count": Video.objects.filter(status=Video.State.DONE).count(),
        }
        return super().index(request, {**context, **(extra_context or {})})
