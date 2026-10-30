"""Backup inspection for administrators (issue #18, TC-OBS-024).

Exposes the recorded backup executions so the 24-hour backup requirement
can be inspected from the running system instead of only from the
server's shell.
"""

from django.http import JsonResponse
from django.views.decorators.http import require_GET

from config.cache import BACKUPS, TTL_BACKUPS, cached_json
from config.http import staff_required_api
from operations.models import BackupRun
from operations.serializers import (
    serialize_backup_freshness,
    serialize_backup_run,
)
from operations.services import backup_freshness


@require_GET
@staff_required_api
@cached_json(TTL_BACKUPS, namespaces=[BACKUPS])
def backup_collection(request):
    """List recent backup runs with the 24-hour freshness verdict."""
    runs = BackupRun.objects.all()[:20]

    return JsonResponse(
        {
            "freshness": serialize_backup_freshness(backup_freshness()),
            "runs": [serialize_backup_run(run) for run in runs],
        }
    )
