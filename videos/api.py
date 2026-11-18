from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, serializers, viewsets

from accounts.services import visible_workspaces
from .models import Video


class VideoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Video
        fields = ("public_id", "title", "status", "duration", "width", "height", "created_at")


class VideoViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = VideoSerializer
    lookup_field = "public_id"
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ("status",)
    search_fields = ("title",)
    ordering_fields = ("created_at", "duration", "title")
    ordering = ("-created_at",)

    def get_queryset(self):
        return Video.objects.filter(workspace__in=visible_workspaces(self.request.user))
