import json
import shutil
import subprocess
from pathlib import Path

from django.conf import settings
from django.core.files import File


class MediaError(ValueError):
    pass


def run_media(program, *args, timeout=600):
    try:
        return subprocess.run(
            [program, *map(str, args)], check=True, capture_output=True, timeout=timeout,
        ).stdout
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        raise MediaError("O FFmpeg não conseguiu processar esta mídia.") from error


def probe(path):
    data = json.loads(run_media(
        "ffprobe", "-v", "error", "-protocol_whitelist", "file", "-format_whitelist", "mov,matroska",
        "-show_format", "-show_streams", "-of", "json", path, timeout=30,
    ))
    video = next((stream for stream in data["streams"] if stream["codec_type"] == "video"), None)
    if video is None or not any(stream["codec_type"] == "audio" for stream in data["streams"]):
        raise MediaError("Envie um vídeo com uma faixa de áudio.")
    duration = float(data["format"].get("duration", 0))
    if not 0 < duration <= settings.MAX_VIDEO_SECONDS:
        raise MediaError("Duração do vídeo fora dos limites.")
    if not 0 < video["width"] <= 7680 or not 0 < video["height"] <= 4320:
        raise MediaError("Resolução do vídeo fora dos limites.")
    return duration, video["width"], video["height"]


def materialize(field, path):
    with field.open("rb") as source, path.open("wb") as target:
        shutil.copyfileobj(source, target)
    return path


def save_artifact(field, path, key):
    with Path(path).open("rb") as source:
        field.save(f"{key}{path.suffix}", File(source), save=False)
