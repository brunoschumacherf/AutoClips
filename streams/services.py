import os
import signal
import subprocess
import time
from urllib.parse import urlsplit

from django.conf import settings

from core.media import MediaError
from .models import Stream


def downloader():
    return [
        "yt-dlp", "--ignore-config", "--no-playlist", "--no-live-from-start",
        "--use-extractors", "youtube,youtube:tab,twitch:stream,twitch:vod", "--js-runtimes", "node", "--compat-options", "no-certifi",
        "--socket-timeout", "15", "--retries", "2", "--proxy", settings.IMPORT_PROXY,
    ]


def live_status(url):
    try:
        result = subprocess.run(
            [*downloader(), "--skip-download", "--print", "%(live_status)s", "--", url],
            capture_output=True, text=True, check=True, timeout=60,
        )
    except (subprocess.SubprocessError, OSError) as error:
        raise MediaError("Não foi possível consultar o vídeo. Confira se o link está público e se o canal está ao vivo.") from error
    return result.stdout.strip()


def stop_group(process):
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            return
        process.wait()


def record(command, video, timeout):
    deadline = time.monotonic() + timeout
    with subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL, start_new_session=True) as process:
        try:
            while time.monotonic() < deadline:
                try:
                    return process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    if type(video).objects.filter(pk=video.pk, status=video.State.CANCELED).exists():
                        raise MediaError("A captura foi cancelada.")
            raise MediaError("A captura excedeu o tempo limite.")
        finally:
            if process.poll() is None:
                stop_group(process)


def capture(video, url, folder, quality):
    from videos.events import changed

    seconds = min(
        (video.options.get("capture_minutes") or min(5, settings.LIVE_CAPTURE_MAX_MINUTES)) * 60,
        settings.LIVE_CAPTURE_MAX_MINUTES * 60,
        settings.MAX_VIDEO_SECONDS,
    )
    host = urlsplit(url).hostname
    Stream.objects.get_or_create(video=video, defaults={
        "workspace": video.workspace, "platform": "twitch" if host == "www.twitch.tv" else "youtube",
        "url": url,
    })
    video.origin.kind = "live"
    video.origin.save(update_fields=["kind", "updated_at"])
    changed(video.public_id)
    target = folder / "source.mkv"
    command = [
        *downloader(), "--match-filter", "is_live", "--no-part", "--no-progress",
        "--downloader", "ffmpeg",
        "--downloader-args", "ffmpeg_i:-protocol_whitelist http,https,tcp,tls,crypto,httpproxy",
        "--downloader-args", f"ffmpeg_o:-t {seconds} -fs {settings.MAX_UPLOAD_BYTES}",
        "--merge-output-format", "mkv", "--remux-video", "mkv",
        "-f", f"b[protocol^=m3u8][height<={quality}]/bv*[height<={quality}]+ba/b[height<={quality}]",
        "-o", str(folder / "source.%(ext)s"), "--", url,
    ]
    try:
        if record(command, video, seconds + 120) != 0 or not target.is_file():
            raise MediaError("A gravação da live falhou. Confira se ela continua pública e tente novamente.")
    except OSError as error:
        raise MediaError("Não foi possível iniciar a gravação da live.") from error
    if target.stat().st_size > settings.MAX_UPLOAD_BYTES:
        raise MediaError("A gravação excedeu o limite de tamanho.")
    return target
