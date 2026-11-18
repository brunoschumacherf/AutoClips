from secrets import compare_digest

from django.conf import settings
from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F
from django.http import Http404, HttpResponse
from django.views.decorators.http import require_safe

from rendering.models import RenderJob
from videos.models import Video


@require_safe
def prometheus(request):
    token = settings.METRICS_TOKEN
    if not token or not compare_digest(
        request.headers.get("Authorization", "").encode(), f"Bearer {token}".encode()
    ):
        raise Http404
    lines = ["# TYPE cortalives_processing_jobs gauge"]
    jobs = dict(Video.objects.values("status").annotate(total=Count("pk")).values_list("status", "total"))
    for state in Video.State.values:
        lines.append(f'cortalives_processing_jobs{{status="{state}"}} {jobs.get(state, 0)}')
    lines.append("# TYPE cortalives_render_jobs gauge")
    renders = dict(RenderJob.objects.values("status").annotate(total=Count("pk")).values_list("status", "total"))
    for state in ("pending", "running", "done", "failed", "canceled"):
        lines.append(f'cortalives_render_jobs{{status="{state}"}} {renders.get(state, 0)}')
    mean = Video.objects.filter(status=Video.State.DONE).aggregate(value=Avg(
        ExpressionWrapper(F("updated_at") - F("created_at"), output_field=DurationField())
    ))["value"]
    lines.extend((
        "# TYPE cortalives_processing_mean_seconds gauge",
        f"cortalives_processing_mean_seconds {mean.total_seconds() if mean else 0}",
    ))
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain; version=0.0.4; charset=utf-8",
                        headers={"Cache-Control": "no-store"})
