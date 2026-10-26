from django.contrib import admin

from .models import BackupRun


@admin.register(BackupRun)
class BackupRunAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "started_at",
        "status",
        "trigger",
        "total_records",
        "size_bytes",
        "location",
    )
    list_filter = ("status", "trigger", "started_at")
    readonly_fields = (
        "started_at",
        "finished_at",
        "status",
        "trigger",
        "location",
        "size_bytes",
        "record_counts",
        "error_message",
        "created_at",
    )
