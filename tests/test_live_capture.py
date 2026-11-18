import shutil
from pathlib import Path

import pytest
from django.urls import reverse

from core.celery import app
from streams.models import Stream
from videos.models import Video


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("url,platform", [
    ("https://www.youtube.com/live/abcdefghijk", "youtube"),
    ("https://www.twitch.tv/test_channel", "twitch"),
])
def test_live_url_through_export(url, platform, client, django_user_model, monkeypatch, tmp_path, settings):
    import subprocess

    sample = tmp_path / "sample.mkv"
    subprocess.run([
        "ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=15",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=16000", "-t", "4",
        "-c:v", "libx264", "-threads", "1", "-c:a", "aac", str(sample),
    ], check=True)
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.IMPORT_PROXY = "http://proxy.example.test:8080"
    monkeypatch.setitem(app.conf, "task_always_eager", True)
    monkeypatch.setattr("videos.services.live_status", lambda _: "is_live")
    monkeypatch.setattr("videos.tasks.recognize", lambda path, language: ("pt", .95, [{
        "start": 0.2, "end": 3.5, "text": "Trecho da transmissão!", "confidence": .9, "words": [],
    }]))

    def record(command, video, timeout):
        assert "ffmpeg_o:-t 60 -fs " + str(settings.MAX_UPLOAD_BYTES) in command
        assert "is_live" in command
        assert timeout == 180
        assert video.origin.kind == "live"
        assert client.get(reverse("video-progress", args=[video.public_id])).content.find(b"Gravando ao vivo") >= 0
        template = command[command.index("-o") + 1]
        shutil.copyfile(sample, Path(template.replace("%(ext)s", "mkv")))
        return 0

    monkeypatch.setattr("streams.services.record", record)
    client.force_login(django_user_model.objects.create_user("stream-user"))
    response = client.post(reverse("video-create"), {
        "title": "Live de teste", "url": url, "capture_minutes": 1, "count": 1, "minimum": 3,
        "maximum": 4, "aspect": "9:16", "quality": "720", "authorized": "on",
    })
    assert response.status_code == 302
    video = Video.objects.get()
    assert video.status == Video.State.DONE, video.error
    assert Stream.objects.get(video=video).platform == platform
    clip = video.clips.get()
    response = client.get(reverse("clip-asset", args=[clip.public_id, "download"]))
    assert response.status_code == 200
    assert "attachment" in response.headers["Content-Disposition"]
    response.close()
