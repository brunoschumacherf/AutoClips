from django.conf import settings
from django.contrib import admin
from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.urls import include, path
from django.views.generic import TemplateView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter

from accounts.views import settings_page
from analytics.views import overview
from clips import views as clips
from dashboard import views as dashboard
from publishing import views as publishing
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
    path("", TemplateView.as_view(template_name="landing.html"), name="landing"),
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
    path("analytics/", overview, name="analytics"),
    path("publications/", dashboard.publications, name="publications"),
    path("publications/youtube/connect/", publishing.youtube_connect, name="youtube-connect"),
    path("publications/youtube/callback/", publishing.youtube_callback, name="youtube-callback"),
    path("clips/<uuid:public_id>/publish/", publishing.schedule, name="clip-publish"),
    path("settings/", settings_page, name="settings"),
    path("health/", health),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema")),
    path("api/", include(router.urls)),
]
