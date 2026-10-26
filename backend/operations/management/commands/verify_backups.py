"""Verify the backup schedule (issue #18, TC-OBS-024).

Inspects the recorded backup executions and asserts that a successful
order and inventory backup exists within the required interval
(OBS-NF-006: at least once every 24 hours). Exits 1 when it does not, so
it can be used both as the manual validation step and as a monitoring
check.
"""

import json

from django.core.management.base import BaseCommand, CommandError

from operations.models import BackupRun
from operations.serializers import serialize_backup_run
from operations.services import backup_freshness


class Command(BaseCommand):
    help = "Check that a successful backup ran within the required interval."

    def add_arguments(self, parser):
        parser.add_argument(
            "--max-age-hours",
            type=float,
            default=None,
            help=(
                "Maximum accepted age of the newest successful backup. "
                "Defaults to BACKUP_MAX_AGE_HOURS (24)."
            ),
        )
        parser.add_argument(
            "--history",
            type=int,
            default=5,
            help="How many recent execution records to list.",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            dest="as_json",
            help="Print the result as JSON for evidence capture.",
        )

    def handle(self, *args, **options):
        freshness = backup_freshness(options["max_age_hours"])
        history = [
            serialize_backup_run(run)
            for run in BackupRun.objects.all()[: max(options["history"], 0)]
        ]

        if options["as_json"]:
            latest = freshness["latest"]
            self.stdout.write(
                json.dumps(
                    {
                        "fresh": freshness["fresh"],
                        "max_age_hours": freshness["max_age_hours"],
                        "age_hours": freshness["age_hours"],
                        "detail": freshness["detail"],
                        "latest": (
                            serialize_backup_run(latest) if latest else None
                        ),
                        "history": history,
                    },
                    indent=2,
                )
            )
        else:
            self.stdout.write(freshness["detail"])
            self.stdout.write("")
            self.stdout.write("Recent backup executions:")

            if not history:
                self.stdout.write("  (none recorded)")

            for record in history:
                self.stdout.write(
                    "  #{id} {status} {started_at} "
                    "{total_records} records -> {location}".format(**record)
                )

        if not freshness["fresh"]:
            raise CommandError(
                "No successful order and inventory backup within "
                f"{freshness['max_age_hours']} hours."
            )

        if not options["as_json"]:
            # Keep --json output parseable: the JSON payload already
            # carries the verdict in its "fresh" field.
            self.stdout.write(
                self.style.SUCCESS(
                    "Backup schedule satisfies OBS-NF-006 "
                    f"(at least one successful backup every "
                    f"{freshness['max_age_hours']} hours)."
                )
            )
