import os
import subprocess

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from clips.models import Clip
from core.celery import app
from transcriptions.services import model
from videos.models import Video


@pytest.mark.skipif(not os.getenv("CORTALIVES_TEST_MODEL"), reason="requires a local faster-whisper model")
@pytest.mark.django_db(transaction=True)
def test_real_whisper_upload(client, django_user_model, settings, monkeypatch, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.WHISPER_MODEL = os.environ["CORTALIVES_TEST_MODEL"]
    model.cache_clear()
    monkeypatch.setitem(app.conf, "task_always_eager", True)
    video = tmp_path / "speech.mp4"
    subprocess.run([
        "ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=15",
        "-f", "lavfi", "-i", "flite=text=Hello everyone. Today I discovered a secret. It is a really interesting story.",
        "-shortest", "-c:v", "libx264", "-threads", "1", "-c:a", "aac", str(video),
    ], check=True)
    client.force_login(django_user_model.objects.create_user("real", email="real@example.test"))
    response = client.post(reverse("video-create"), {
        "title": "Speech test", "file": SimpleUploadedFile(video.name, video.read_bytes(), content_type="video/mp4"),
        "count": 1, "minimum": 3, "maximum": 10, "aspect": "9:16", "quality": "720", "language": "en", "authorized": "on",
    })
    assert response.status_code == 302
    video = Video.objects.get()
    assert video.status == Video.State.DONE, video.error
    assert video.transcription.segments.exists()
    clip = Clip.objects.get()
    assert clip.current_version.captions
    result = client.get(reverse("clip-asset", args=[clip.public_id, "download"]))
    assert result.status_code == 200
    result.close()
    model.cache_clear()
