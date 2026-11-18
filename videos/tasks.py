import logging
import tempfile
from pathlib import Path

from celery import shared_task
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from ai_engine.models import AIAnalysis, Highlight
from ai_engine.services import audio_energy, suggestions, visual_signals
from clips.models import Clip
from clips.services import version_for
from core.jobs import claim, release
from core.media import materialize
from notifications.models import Notification
from subscriptions.services import reserve
from transcriptions.models import Transcription, TranscriptionSegment
from transcriptions.services import recognize
from .events import changed
from .models import ProcessingJob, Video
from .services import enqueue, prepare

logger = logging.getLogger(__name__)
State = Video.State


def execute(task, video_id, accepted, active, next_status, operation, following=None):
    job = claim(ProcessingJob.objects.filter(video_id=video_id), "video", accepted, active)
    if not job:
        return
    video = job.video
    changed(video.public_id)
    try:
        fields = operation(video) or {}
        with transaction.atomic():
            if Video.objects.filter(pk=video.pk, status=active, job__lease=job.lease).update(
                status=next_status, updated_at=timezone.now(), error="", **fields
            ):
                changed(video.public_id)
                if following:
                    enqueue(following, video.pk)
            release(job, reset=True)
    except Exception as error:
        logger.warning("pipeline_failed video=%s stage=%s error_type=%s", video.public_id, active, type(error).__name__)
        with transaction.atomic():
            if isinstance(error, ValueError) or job.attempts >= 3:
                updated = Video.objects.filter(pk=video.pk, status=active, job__lease=job.lease).update(
                    status=State.FAILED, updated_at=timezone.now(),
                    error=str(error)[:300] if isinstance(error, ValueError) else "Falha durante o processamento.",
                )
                if updated:
                    changed(video.public_id)
                    Notification.objects.create(workspace=video.workspace, message=f"Falha ao processar {video.title}.")
                release(job, reset=True)
                return
            release(job)
        raise task.retry(countdown=15 * 2 ** (job.attempts - 1))


def ingest_media(video):
    with tempfile.TemporaryDirectory() as directory:
        return prepare(video, Path(directory))


def transcribe_media(video):
    if Transcription.objects.filter(video=video).exists():
        return
    with tempfile.TemporaryDirectory() as directory:
        audio = materialize(video.audio, Path(directory) / "audio.wav")
        language, confidence, segments = recognize(audio, video.options.get("language"))
    with transaction.atomic():
        transcript = Transcription.objects.create(video=video, language=language, confidence=confidence)
        TranscriptionSegment.objects.bulk_create([TranscriptionSegment(transcription=transcript, **segment) for segment in segments])


def analyze_media(video):
    if AIAnalysis.objects.filter(video=video).exists():
        return
    with tempfile.TemporaryDirectory() as directory:
        folder = Path(directory)
        source = materialize(video.source, folder / "source")
        audio = materialize(video.audio, folder / "audio.wav")
        energy = audio_energy(audio)
        movement, faces, scenes = visual_signals(source, video.duration)
    results = suggestions(video, list(video.transcription.segments.all()), energy, movement)
    reserve(video, clips=len(results))
    with transaction.atomic():
        analysis = AIAnalysis.objects.create(video=video, signals={"energy": energy, "faces": faces, "scenes": scenes, "motion": movement})
        Highlight.objects.bulk_create([Highlight(analysis=analysis, rank=rank, **result) for rank, result in enumerate(results, 1)])


def generate_clips(video):
    for highlight in video.aianalysis.highlights.all():
        with transaction.atomic():
            clip, created = Clip.objects.get_or_create(video=video, highlight=highlight, defaults={"title": f"{video.title[:160]} · Corte {highlight.rank}"})
            if created:
                version_for(clip, highlight.start, highlight.end, video.options["aspect"], {"color": "#FFFFFF", "position": 74})


@shared_task(bind=True, max_retries=3)
def ingest(self, video_id):
    execute(self, video_id, [State.PENDING, State.IMPORTING], State.IMPORTING, State.TRANSCRIBING, ingest_media, transcribe)


@shared_task(bind=True, max_retries=3)
def transcribe(self, video_id):
    execute(self, video_id, [State.TRANSCRIBING], State.TRANSCRIBING, State.ANALYZING, transcribe_media, analyze)


@shared_task(bind=True, max_retries=3)
def analyze(self, video_id):
    execute(self, video_id, [State.ANALYZING], State.ANALYZING, State.GENERATING, analyze_media, generate)


@shared_task(bind=True, max_retries=3)
def generate(self, video_id):
    execute(self, video_id, [State.GENERATING], State.GENERATING, State.RENDERING, generate_clips)
    from rendering.tasks import settle_video

    settle_video(video_id)


@shared_task
def recover():
    from rendering.tasks import render_clip

    stages = {State.PENDING: ingest, State.IMPORTING: ingest, State.TRANSCRIBING: transcribe,
              State.ANALYZING: analyze, State.GENERATING: generate}
    available = Q(locked_until__isnull=True) | Q(locked_until__lt=timezone.now())
    jobs = ProcessingJob.objects.filter(available, video__status__in=stages).values_list("video_id", "video__status")
    for video_id, status in jobs.iterator():
        stages[status].delay(video_id)
    from rendering.models import RenderJob

    renders = RenderJob.objects.filter(available, status__in=["pending", "running"], version__clip__deleted_at__isnull=True)
    for version_id in renders.exclude(version__clip__video__status=State.CANCELED).values_list("version_id", flat=True).iterator():
        render_clip.delay(version_id)


@shared_task
def purge_expired():
    from datetime import timedelta

    from django.conf import settings

    from .retention import expire_media

    if settings.VIDEO_RETENTION_DAYS <= 0:
        return
    cutoff = timezone.now() - timedelta(days=settings.VIDEO_RETENTION_DAYS)
    videos = Video.objects.filter(
        updated_at__lt=cutoff, status__in=[State.DONE, State.FAILED, State.CANCELED],
    ).exclude(source="", audio="")
    for video_id in videos.values_list("pk", flat=True).iterator():
        expire_media(video_id)
