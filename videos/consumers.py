from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from accounts.services import visible_workspaces
from .events import group_name
from .models import Video


class VideoProgress(AsyncJsonWebsocketConsumer):
    @database_sync_to_async
    def can_read(self):
        user = self.scope["user"]
        return user.is_authenticated and Video.objects.filter(
            workspace__in=visible_workspaces(user), public_id=self.public_id,
        ).exists()

    async def connect(self):
        self.public_id = self.scope["url_route"]["kwargs"]["public_id"]
        if not await self.can_read():
            await self.close(code=4404)
            return
        self.group = group_name(self.public_id)
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, "group"):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def video_change(self, event):
        if not await self.can_read():
            await self.close(code=4404)
            return
        await self.send_json({"event": "changed"})
