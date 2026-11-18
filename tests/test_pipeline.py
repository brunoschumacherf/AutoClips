import json
import subprocess

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from clips.models import Clip
from core.celery import app
from videos.models import Video


@pytest.fixture
def video_bytes(tmp_path):
    path = tmp_path / "sample.mp4"
    subprocess.run([
        "ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=15",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=16000", "-t", "4",
        "-c:v", "libx264", "-threads", "1", "-c:a", "aac", str(path),
    ], check=True)
    return path.read_bytes()


@pytest.mark.django_db(transaction=True)
def test_upload_to_vertical_export(client, django_user_model, monkeypatch, tmp_path, settings, video_bytes):
    settings.MEDIA_ROOT = tmp_path / "media"
    monkeypatch.setitem(app.conf, "task_always_eager", True)
    monkeypatch.setattr("videos.tasks.recognize", lambda path, language: ("pt", .95, [{
        "start": 0.2, "end": 3.2, "text": "Descobri um segredo!",
        "confidence": .9, "words": [{"start": .2, "end": .8, "text": "Descobri"},
                                  {"start": .8, "end": 1, "text": "um"},
                                  {"start": 1, "end": 3.2, "text": "segredo!"}],
    }]))
    owner = django_user_model.objects.create_user("owner", email="owner@example.test")
    client.force_login(owner)
    response = client.post(reverse("video-create"), {
        "title": "Minha live", "file": SimpleUploadedFile("sample.mp4", video_bytes, content_type="video/mp4"),
        "count": 1, "minimum": 3, "maximum": 4, "aspect": "9:16", "quality": "720", "authorized": "on",
    })
    assert response.status_code == 302
    video = Video.objects.get()
    assert video.status == Video.State.DONE, video.error
    clip = Clip.objects.select_related("current_version", "highlight").get()
    assert 0 <= clip.highlight.score <= 100
    version = clip.current_version
    assert version.render.status == "done", version.render.error
    metadata = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_streams", "-of", "json", version.output.path]))
    assert metadata["streams"][0]["height"] > metadata["streams"][0]["width"]
    assert {stream["codec_name"] for stream in metadata["streams"]} == {"h264", "aac"}
    preview = reverse("clip-asset", args=[clip.public_id, "preview"])
    response = client.get(preview, HTTP_RANGE="bytes=0-31")
    assert response.status_code == 206
    assert b"ftyp" in b"".join(response.streaming_content)
    srt = client.get(reverse("clip-asset", args=[clip.public_id, "srt"]))
    assert "Descobri um segredo!" in b"".join(srt.streaming_content).decode()
    assert client.get(reverse("video", args=[video.public_id])).status_code == 200
    assert client.get(reverse("clip", args=[clip.public_id])).status_code == 200
    response = client.post(reverse("clip", args=[clip.public_id]), {
        "title": "Versão editada", "start": ".20", "end": "3.20", "aspect": "9:16", "position": 75,
        "color": "#AAAAAA", "captions": "Uma legenda revisada", "center": 50,
        "webcam": "75,0,25,25", "font": "DejaVu Serif", "outline": 4, "shadow": 2,
    })
    assert response.status_code == 302
    clip.refresh_from_db()
    assert clip.current_version.output and clip.current_version.captions[0]["text"] == "Uma legenda revisada"
    assert clip.current_version.style["webcam"] == [75, 0, 25, 25]
    other = django_user_model.objects.create_user("other", email="other@example.test")
    client.force_login(other)
    assert client.get(preview).status_code == 404
    assert client.get(reverse("video", args=[video.public_id])).status_code == 404
    assert client.get(reverse("api-video-detail", args=[video.public_id])).status_code == 404
    assert client.get(reverse("api-video-list")).json()["count"] == 0
