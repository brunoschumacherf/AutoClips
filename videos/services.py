import subprocess
from pathlib import Path

from django.conf import settings
from django.db import transaction

from accounts.models import AuditLog
from core.media import MediaError, materialize, probe, run_media, save_artifact
from subscriptions.services import adjust_storage, reserve
from .forms import canonical_url
from .models import ProcessingJob, Video, VideoSource


def enqueue(task, *args):
    transaction.on_commit(lambda: task.delay(*args), robust=True)


def submit(workspace, data):
    from .tasks import ingest

    upload = data["file"]
    stored = None
    try:
        with transaction.atomic():
            video = Video.objects.create(workspace=workspace, title=data["title"], options={
                key: data[key] for key in ("count", "minimum", "maximum", "aspect", "quality", "language")
            })
            reserve(video, size=upload.size if upload else 0)
            VideoSource.objects.create(video=video, url=data["url"], kind="upload" if upload else "link")
            if upload:
                video.source.save(f"{video.public_id}{Path(upload.name).suffix.lower()}", upload, save=False)
                stored = video.source
                video.save(update_fields=["source"])
            ProcessingJob.objects.create(video=video)
            AuditLog.objects.create(workspace=workspace, action="video.submitted", resource_id=video.public_id)
            enqueue(ingest, video.pk)
    except Exception:
        if stored:
            stored.storage.delete(stored.name)
        raise
    return video


def download(video, folder):
    if not settings.IMPORT_PROXY:
        raise MediaError("O proxy de importação não está configurado.")
    url = canonical_url(video.origin.url)
    limit = int(video.options["quality"])
    target = folder / "source.mkv"
    try:
        subprocess.run([
            "yt-dlp", "--ignore-config", "--no-playlist", "--no-live-from-start", "--restrict-filenames",
            "--socket-timeout", "15", "--no-progress", "--proxy", settings.IMPORT_PROXY,
            "--match-filter", f"!is_live & duration <= {settings.MAX_VIDEO_SECONDS}",
            "--max-filesize", str(settings.MAX_UPLOAD_BYTES), "--merge-output-format", "mkv",
            "--remux-video", "mkv", "-f", f"bv*[height<={limit}]+ba/b[height<={limit}]",
            "-o", str(folder / "source.%(ext)s"), "--", url,
        ], check=True, capture_output=True, timeout=900)
    except (subprocess.SubprocessError, OSError) as error:
        raise MediaError("Não foi possível importar o vídeo pela plataforma de origem.") from error
    if not target.is_file() or target.stat().st_size > settings.MAX_UPLOAD_BYTES:
        raise MediaError("O vídeo importado não atende aos requisitos de tamanho ou formato.")
    return target


def prepare(video, folder):
    if video.audio:
        return
    source = materialize(video.source, folder / "source") if video.source else download(video, folder)
    duration, width, height = probe(source)
    reserve(video, duration=duration, size=source.stat().st_size)
    audio = folder / "audio.wav"
    run_media("ffmpeg", "-nostdin", "-v", "error", "-protocol_whitelist", "file",
              "-format_whitelist", "mov,matroska", "-i", source,
              "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", audio)
    fields = {"duration": duration, "width": width, "height": height}
    stored = []
    try:
        with transaction.atomic():
            locked = Video.objects.select_for_update().get(pk=video.pk)
            if locked.status != Video.State.IMPORTING:
                return
            adjust_storage(video, audio.stat().st_size)
            if not video.source:
                save_artifact(video.source, source, video.public_id)
                stored.append(video.source)
                fields["source"] = video.source.name
            save_artifact(video.audio, audio, video.public_id)
            stored.append(video.audio)
            fields["audio"] = video.audio.name
            Video.objects.filter(pk=video.pk).update(**fields)
    except Exception:
        for asset in stored:
            asset.storage.delete(asset.name)
        raise
