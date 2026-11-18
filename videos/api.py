from rest_framework import serializers, viewsets

from accounts.services import visible_workspaces
from .models import Video


class VideoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Video
        fields = ("public_id", "title", "status", "duration", "width", "height", "created_at")


class VideoViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = VideoSerializer
    lookup_field = "public_id"

    def get_queryset(self):
        return Video.objects.filter(workspace__in=visible_workspaces(self.request.user))
