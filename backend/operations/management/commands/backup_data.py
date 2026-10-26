"""Back up order and inventory data (issue #18, OBS-NF-006).

Intended to be run by a scheduler at least once every 24 hours::

    # /etc/cron.d/online-book-store-backup
    0 2 * * * appuser cd /srv/online-book-store/backend && \
        /srv/online-book-store/.venv/bin/python manage.py backup_data \
        --trigger scheduled >> /var/log/obs-backup.log 2>&1

Exits with status 1 when the run fails, so the scheduler reports it.
"""

from django.core.management.base import BaseCommand, CommandError

from operations.models import BackupRun
from operations.services import run_backup


class Command(BaseCommand):
    help = "Back up order and inventory data to a timestamped directory."

    def add_arguments(self, parser):
        parser.add_argument(
            "--trigger",
            choices=["scheduled", "manual"],
            default="manual",
            help=(
                "How this run was started. Use 'scheduled' from cron so "
                "the execution records distinguish automated runs."
            ),
        )
        parser.add_argument(
            "--destination",
            default=None,
            help=(
                "Directory to write the backup into. Defaults to "
                "BACKUP_DIR from the central configuration."
            ),
        )
        parser.add_argument(
            "--keep-days",
            type=int,
            default=None,
            help=(
                "Delete backup directories older than this many days. "
                "Defaults to BACKUP_RETENTION_DAYS."
            ),
        )

    def handle(self, *args, **options):
        trigger = (
            BackupRun.TRIGGER_SCHEDULED
            if options["trigger"] == "scheduled"
            else BackupRun.TRIGGER_MANUAL
        )

        run = run_backup(
            trigger=trigger,
            root=options["destination"],
            keep_days=options["keep_days"],
        )

        if not run.succeeded:
            raise CommandError(
                f"Backup run {run.pk} failed: {run.error_message}"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Backup run {run.pk} succeeded in "
                f"{run.duration_seconds}s: {run.total_records} records "
                f"({run.size_bytes} bytes) written to {run.location}"
            )
        )

        for label, count in sorted(run.record_counts.items()):
            self.stdout.write(f"  {label}: {count} records")
