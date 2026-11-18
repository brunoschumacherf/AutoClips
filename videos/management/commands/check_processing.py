from celery.exceptions import CeleryError
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from kombu.exceptions import KombuError

from core.celery import app


class Command(BaseCommand):
    help = "Verify that Celery workers consume all queues required by the video pipeline."

    def handle(self, *args, **options):
        expected = {"celery", *(route["queue"] for route in settings.CELERY_TASK_ROUTES.values())}
        try:
            workers = app.control.inspect(timeout=3).active_queues()
        except (OSError, CeleryError, KombuError) as error:
            raise CommandError(f"Celery inspection failed ({type(error).__name__}).") from error
        if not workers:
            raise CommandError("No Celery worker responded.")
        queues = {queue["name"] for assigned in workers.values() for queue in assigned}
        missing = expected - queues
        if missing:
            raise CommandError("Queues without a worker: " + ", ".join(sorted(missing)))
        self.stdout.write(self.style.SUCCESS(f"{len(workers)} worker(s) cover all required queues."))
