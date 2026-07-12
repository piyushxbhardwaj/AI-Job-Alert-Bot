"""Database helpers for AI-Job-Alert-Bot."""

from .sqlite_store import (
	JobRecord,
	alert_already_sent,
	fetch_dashboard_summary,
	fetch_job_history,
	fetch_recent_jobs,
	get_job,
	initialize_database,
	insert_job,
	is_duplicate_job,
	job_exists,
	record_job_history,
	record_alert,
)

__all__ = [
	"JobRecord",
	"alert_already_sent",
	"fetch_dashboard_summary",
	"fetch_job_history",
	"fetch_recent_jobs",
	"get_job",
	"initialize_database",
	"insert_job",
	"is_duplicate_job",
	"job_exists",
	"record_job_history",
	"record_alert",
]