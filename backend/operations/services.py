"""Automated order and inventory backups (issue #18, OBS-NF-006).

``run_backup`` writes one directory per run containing a Django fixture
per dataset plus a ``manifest.json`` with row counts and SHA-256
checksums. Fixtures are written with Django's own serializer, so a
backup can be restored with::

    python manage.py loaddata <backup-dir>/books.book.json

The datasets cover the data OBS-NF-006 names: orders (orders, order
items and payments, which together are the order record) and inventory
(the book catalogue with its stock levels).

Scheduling lives outside Django — cron, a systemd timer or a container
scheduler calls ``manage.py backup_data --trigger scheduled``. Each run
records a :class:`operations.models.BackupRun` row, and
``manage.py verify_backups`` asserts that a successful run exists within
the required 24-hour interval.
"""

import hashlib
import json
import shutil
from pathlib import Path

from django.conf import settings
from django.core.serializers import serialize
from django.utils import timezone

from books.models import Book
from orders.models import Order, OrderItem
from payments.models import Payment

from .models import BackupRun

#: The datasets written by every backup run, in restore order (parents
#: before the rows that reference them).
BACKUP_DATASETS = [
    ("books.book", Book),
    ("orders.order", Order),
    ("orders.orderitem", OrderItem),
    ("payments.payment", Payment),
]


def _write_dataset(destination, label, queryset):
    """Write one dataset as a Django JSON fixture; return its metadata."""
    path = destination / f"{label}.json"
    payload = serialize("json", queryset.order_by("pk"), indent=2)
    path.write_text(payload, encoding="utf-8")

    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    return {
        "file": path.name,
        "records": queryset.count(),
        "bytes": path.stat().st_size,
        "sha256": digest,
    }


def prune_old_backups(root, keep_days):
    """Delete backup directories older than ``keep_days``.

    ``BackupRun`` rows are kept regardless: they are the execution
    records that must remain inspectable even after the artifacts are
    rotated away.
    """
    if keep_days is None or keep_days <= 0:
        return []

    cutoff = timezone.now() - timezone.timedelta(days=keep_days)
    removed = []

    for directory in sorted(root.glob("backup-*")):
        if not directory.is_dir():
            continue

        modified = timezone.datetime.fromtimestamp(
            directory.stat().st_mtime,
            tz=timezone.get_current_timezone(),
        )

        if modified < cutoff:
            shutil.rmtree(directory, ignore_errors=True)
            removed.append(directory.name)

    return removed


def run_backup(trigger=BackupRun.TRIGGER_MANUAL, root=None, keep_days=None):
    """Back up orders and inventory; return the recorded ``BackupRun``.

    A failure is recorded as a ``FAILED`` run with the error message
    rather than raised, so a scheduled job always leaves an execution
    record behind. The caller decides how to report it.
    """
    started_at = timezone.now()
    root = Path(root or settings.BACKUP_DIR)
    keep_days = (
        settings.BACKUP_RETENTION_DAYS if keep_days is None else keep_days
    )

    run = BackupRun.objects.create(
        started_at=started_at,
        status=BackupRun.STATUS_FAILED,
        trigger=trigger,
        error_message="Backup did not complete.",
    )

    destination = root / f"backup-{started_at:%Y%m%dT%H%M%SZ}-{run.pk}"

    try:
        destination.mkdir(parents=True, exist_ok=True)

        datasets = {}
        for label, model in BACKUP_DATASETS:
            datasets[label] = _write_dataset(
                destination,
                label,
                model.objects.all(),
            )

        manifest = {
            "created_at": started_at.isoformat(),
            "backup_run_id": run.pk,
            "trigger": trigger,
            "datasets": datasets,
        }
        manifest_path = destination / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2),
            encoding="utf-8",
        )

        total_bytes = sum(
            path.stat().st_size for path in destination.iterdir()
        )

        run.status = BackupRun.STATUS_SUCCESS
        run.finished_at = timezone.now()
        run.location = str(destination)
        run.size_bytes = total_bytes
        run.record_counts = {
            label: meta["records"] for label, meta in datasets.items()
        }
        run.error_message = ""
        run.save(
            update_fields=[
                "status",
                "finished_at",
                "location",
                "size_bytes",
                "record_counts",
                "error_message",
            ]
        )

        prune_old_backups(root, keep_days)

    except Exception as exc:  # noqa: BLE001 - recorded, then reported
        run.finished_at = timezone.now()
        run.error_message = f"{type(exc).__name__}: {exc}"[:2000]
        run.location = str(destination)
        run.save(
            update_fields=["finished_at", "error_message", "location"]
        )

    return run


def latest_successful_backup():
    """The most recent successful run, or ``None``."""
    return (
        BackupRun.objects.filter(status=BackupRun.STATUS_SUCCESS)
        .order_by("-started_at", "-pk")
        .first()
    )


def backup_freshness(max_age_hours=None):
    """Report whether a recent enough successful backup exists.

    This is the check behind TC-OBS-024: OBS-NF-006 requires order and
    inventory data to be backed up at least once every 24 hours.
    """
    max_age_hours = (
        settings.BACKUP_MAX_AGE_HOURS
        if max_age_hours is None
        else max_age_hours
    )

    latest = latest_successful_backup()
    now = timezone.now()

    if latest is None:
        return {
            "fresh": False,
            "max_age_hours": max_age_hours,
            "age_hours": None,
            "latest": None,
            "detail": "No successful backup has been recorded yet.",
        }

    age_hours = (now - latest.started_at).total_seconds() / 3600
    fresh = age_hours <= max_age_hours

    return {
        "fresh": fresh,
        "max_age_hours": max_age_hours,
        "age_hours": round(age_hours, 3),
        "latest": latest,
        "detail": (
            f"Last successful backup was {age_hours:.2f} hours ago "
            f"(limit {max_age_hours} hours)."
        ),
    }
