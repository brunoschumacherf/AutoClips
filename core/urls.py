from django.conf import settings
from django.contrib import admin
from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter

from core.metrics import prometheus
from accounts.views import revoke_session, sessions, settings_page
from analytics.views import overview
from clips import views as clips
from dashboard import views as dashboard
from publishing import views as publishing
from subscriptions import views as billing
from videos import views as videos
from videos.api import VideoViewSet


def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        if settings.CACHES["default"]["BACKEND"] == "django.core.cache.backends.redis.RedisCache":
            cache.get("cortalives-health")
    except Exception:
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})


router = DefaultRouter()
router.register("videos", VideoViewSet, basename="api-video")
urlpatterns = [
    path("", dashboard.landing, name="landing"),
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("dashboard/", dashboard.home, name="dashboard"),
    path("videos/", dashboard.library, name="library"),
    path("videos/new/", videos.create, name="video-create"),
    path("videos/<uuid:public_id>/", videos.detail, name="video"),
    path("videos/<uuid:public_id>/progress/", videos.progress, name="video-progress"),
    path("videos/<uuid:public_id>/cancel/", videos.cancel, name="video-cancel"),
    path("videos/<uuid:public_id>/source/", clips.source, name="source"),
    path("clips/<uuid:public_id>/", clips.edit, name="clip"),
    path("clips/<uuid:public_id>/cancel/", clips.cancel_render, name="clip-cancel"),
    path("clips/<uuid:public_id>/delete/", clips.delete, name="clip-delete"),
    path("clips/<uuid:public_id>/file/<str:kind>/", clips.asset, name="clip-asset"),
    path("usage/", dashboard.usage, name="usage"),
    path("usage/pix/new/<uuid:public_id>/", billing.start, name="pix-start"),
    path("usage/pix/<uuid:public_id>/", billing.order_detail, name="pix-order"),
    path("usage/pix/<uuid:public_id>/qr/", billing.qr, name="pix-qr"),
    path("analytics/", overview, name="analytics"),
    path("publications/", dashboard.publications, name="publications"),
    path("publications/youtube/connect/", publishing.youtube_connect, name="youtube-connect"),
    path("publications/youtube/callback/", publishing.youtube_callback, name="youtube-callback"),
    path("publications/instagram/connect/", publishing.instagram_connect, name="instagram-connect"),
    path("publications/instagram/callback/", publishing.instagram_callback, name="instagram-callback"),
    path("publications/tiktok/connect/", publishing.tiktok_connect, name="tiktok-connect"),
    path("publications/tiktok/callback/", publishing.tiktok_callback, name="tiktok-callback"),
    path("clips/<uuid:public_id>/publish/", publishing.schedule, name="clip-publish"),
    path("settings/", settings_page, name="settings"),
    path("settings/sessions/", sessions, name="sessions"),
    path("settings/sessions/<uuid:public_id>/revoke/", revoke_session, name="session-revoke"),
    path("health/", health),
    path("metrics/", prometheus, name="metrics"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema")),
    path("api/", include(router.urls)),
]
