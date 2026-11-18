import uuid
from datetime import timedelta

from django.db import transaction
from django.utils import timezone


@transaction.atomic
def claim(query, status_owner, accepted, active, lease_seconds=3700):
    job = query.select_for_update().first()
    if job is None:
        return None
    owner = getattr(job, status_owner) if status_owner else job
    now = timezone.now()
    if owner.status not in accepted or (job.locked_until and job.locked_until > now):
        return None
    job.lease = uuid.uuid4()
    job.locked_until = now + timedelta(seconds=lease_seconds)
    job.attempts += 1
    job.save(update_fields=["lease", "locked_until", "attempts"])
    owner.status = active
    owner.save(update_fields=["status", "updated_at"])
    return job


def release(job, reset=False):
    values = {"lease": None, "locked_until": None}
    if reset:
        values["attempts"] = 0
    type(job).objects.filter(pk=job.pk, lease=job.lease).update(**values)
