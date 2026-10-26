def serialize_backup_run(run):
    """A backup execution record as exposed to administrators (issue #18)."""
    return {
        "id": run.id,
        "status": run.status,
        "trigger": run.trigger,
        "started_at": run.started_at.isoformat(),
        "finished_at": (
            run.finished_at.isoformat() if run.finished_at else None
        ),
        "duration_seconds": run.duration_seconds,
        "location": run.location,
        "size_bytes": run.size_bytes,
        "record_counts": run.record_counts,
        "total_records": run.total_records,
        "error_message": run.error_message,
    }


def serialize_backup_freshness(freshness):
    """The 24-hour backup check (TC-OBS-024) as a JSON payload."""
    latest = freshness["latest"]

    return {
        "fresh": freshness["fresh"],
        "max_age_hours": freshness["max_age_hours"],
        "age_hours": freshness["age_hours"],
        "detail": freshness["detail"],
        "latest": serialize_backup_run(latest) if latest else None,
    }
