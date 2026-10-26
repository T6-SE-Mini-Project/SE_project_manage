from django.db import models


class BackupRun(models.Model):
    """One execution of the order and inventory backup (issue #18).

    Every run writes a row here whether it succeeds or fails, so the
    backup schedule can be audited after the fact: this table *is* the
    backup execution record that OBS-NF-006 and TC-OBS-024 require to be
    inspectable. ``manage.py verify_backups`` reads it to assert that a
    successful backup exists within the required interval.
    """

    STATUS_SUCCESS = "SUCCESS"
    STATUS_FAILED = "FAILED"

    STATUS_CHOICES = [
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
    ]

    TRIGGER_SCHEDULED = "SCHEDULED"
    TRIGGER_MANUAL = "MANUAL"

    TRIGGER_CHOICES = [
        (TRIGGER_SCHEDULED, "Scheduled"),
        (TRIGGER_MANUAL, "Manual"),
    ]

    started_at = models.DateTimeField()
    finished_at = models.DateTimeField(blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        db_index=True,
    )
    trigger = models.CharField(
        max_length=20,
        choices=TRIGGER_CHOICES,
        default=TRIGGER_MANUAL,
    )
    # Directory holding this run's JSON fixtures and manifest.
    location = models.CharField(max_length=500, blank=True)
    size_bytes = models.PositiveBigIntegerField(default=0)
    # Row counts per dataset, e.g. {"orders.order": 12, "books.book": 7}.
    record_counts = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-started_at", "-pk"]
        indexes = [
            models.Index(
                fields=["status", "-started_at"],
                name="backup_status_started_idx",
            ),
        ]

    def __str__(self):
        return f"Backup {self.pk} {self.status} at {self.started_at:%Y-%m-%d %H:%M}"

    @property
    def succeeded(self):
        return self.status == self.STATUS_SUCCESS

    @property
    def duration_seconds(self):
        if self.finished_at is None:
            return None
        return round((self.finished_at - self.started_at).total_seconds(), 3)

    @property
    def total_records(self):
        return sum(self.record_counts.values()) if self.record_counts else 0
