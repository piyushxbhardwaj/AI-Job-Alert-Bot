"""SQLite storage helpers for AI-Job-Alert-Bot."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Any


DEFAULT_DATABASE_PATH = Path("state") / "jobs.db"


@dataclass(slots=True)
class JobRecord:
    """Normalized representation of a discovered job posting."""

    job_id: str | None
    company: str
    title: str
    url: str
    source: str
    date_found: str
    timestamp: str
    job_hash: str | None = None


def _database_path(db_path: str | Path | None = None) -> Path:
    path = Path(db_path) if db_path is not None else DEFAULT_DATABASE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def get_connection(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Open a SQLite connection with row access enabled."""

    connection = sqlite3.connect(_database_path(db_path))
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database(db_path: str | Path | None = None) -> None:
    """Create the SQLite schema if it does not already exist."""

    with get_connection(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS companies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT UNIQUE,
                company TEXT NOT NULL,
                title TEXT NOT NULL,
                url TEXT NOT NULL UNIQUE,
                source TEXT NOT NULL,
                date_found TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                job_hash TEXT UNIQUE
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT,
                channel TEXT NOT NULL,
                status TEXT NOT NULL,
                payload TEXT,
                created_at TEXT NOT NULL,
                sent_at TEXT,
                FOREIGN KEY(job_id) REFERENCES jobs(job_id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS job_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT,
                action TEXT NOT NULL,
                note TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(job_id) REFERENCES jobs(job_id)
            )
            """
        )


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_record(job: JobRecord | dict[str, Any]) -> JobRecord:
    if isinstance(job, JobRecord):
        return job

    return JobRecord(
        job_id=job.get("job_id"),
        company=job["company"],
        title=job["title"],
        url=job["url"],
        source=job["source"],
        date_found=job.get("date_found", _now_utc()),
        timestamp=job.get("timestamp", _now_utc()),
        job_hash=job.get("job_hash"),
    )


def job_exists(
    *,
    db_path: str | Path | None = None,
    job_id: str | None = None,
    url: str | None = None,
    company: str | None = None,
    title: str | None = None,
    job_hash: str | None = None,
) -> bool:
    """Return True when a job matching any provided identifier already exists."""

    conditions: list[str] = []
    parameters: list[str] = []

    if job_id:
        conditions.append("job_id = ?")
        parameters.append(job_id)
    if url:
        conditions.append("url = ?")
        parameters.append(url)
    if job_hash:
        conditions.append("job_hash = ?")
        parameters.append(job_hash)
    if company and title:
        conditions.append("company = ? AND title = ?")
        parameters.extend([company, title])

    if not conditions:
        raise ValueError("At least one lookup field is required")

    query = f"SELECT 1 FROM jobs WHERE {' OR '.join(conditions)} LIMIT 1"
    with get_connection(db_path) as connection:
        row = connection.execute(query, parameters).fetchone()
    return row is not None


def insert_job(
    job: JobRecord | dict[str, Any],
    db_path: str | Path | None = None,
) -> int:
    """Insert a new job and return the inserted row id."""

    initialize_database(db_path)
    record = _normalize_record(job)

    if record.job_hash is None:
        from hashlib import sha256

        record = JobRecord(
            job_id=record.job_id,
            company=record.company,
            title=record.title,
            url=record.url,
            source=record.source,
            date_found=record.date_found,
            timestamp=record.timestamp,
            job_hash=sha256(f"{record.company}|{record.title}|{record.url}".encode("utf-8")).hexdigest(),
        )

    with get_connection(db_path) as connection:
        company_created_at = _now_utc()
        connection.execute(
            "INSERT OR IGNORE INTO companies (name, created_at) VALUES (?, ?)",
            (record.company, company_created_at),
        )
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO jobs (
                job_id, company, title, url, source, date_found, timestamp, job_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.job_id,
                record.company,
                record.title,
                record.url,
                record.source,
                record.date_found,
                record.timestamp,
                record.job_hash,
            ),
        )
        if cursor.lastrowid:
            return int(cursor.lastrowid)

        existing = connection.execute(
            """
            SELECT id FROM jobs
            WHERE job_id = ? OR url = ? OR job_hash = ? OR (company = ? AND title = ?)
            LIMIT 1
            """,
            (record.job_id, record.url, record.job_hash, record.company, record.title),
        ).fetchone()
        if existing is None:
            raise RuntimeError("Job insert was ignored but no existing row was found")
        return int(existing["id"])


def get_job(job_id: str, db_path: str | Path | None = None) -> dict[str, Any] | None:
    """Fetch a job by job_id and return it as a dictionary."""

    with get_connection(db_path) as connection:
        row = connection.execute(
            "SELECT * FROM jobs WHERE job_id = ? LIMIT 1",
            (job_id,),
        ).fetchone()
    return dict(row) if row is not None else None


def is_duplicate_job(job: JobRecord | dict[str, Any], db_path: str | Path | None = None) -> bool:
    """Return True when the job already exists by id, URL, title/company, or hash."""

    record = _normalize_record(job)
    return job_exists(
        db_path=db_path,
        job_id=record.job_id,
        url=record.url,
        company=record.company,
        title=record.title,
        job_hash=record.job_hash,
    )


def record_alert(
    *,
    job_id: str | None,
    channel: str,
    status: str,
    payload: str | None = None,
    sent_at: str | None = None,
    db_path: str | Path | None = None,
) -> int:
    """Persist an alert delivery record."""

    initialize_database(db_path)
    created_at = _now_utc()
    with get_connection(db_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO alerts (job_id, channel, status, payload, created_at, sent_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (job_id, channel, status, payload, created_at, sent_at),
        )
        return int(cursor.lastrowid)


def alert_already_sent(
    *,
    job_id: str | None,
    channel: str = "telegram",
    db_path: str | Path | None = None,
) -> bool:
    """Return True when an alert has already been recorded as sent."""

    with get_connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT 1 FROM alerts
            WHERE job_id = ? AND channel = ? AND status = 'sent'
            LIMIT 1
            """,
            (job_id, channel),
        ).fetchone()
    return row is not None


def record_job_history(
    *,
    job_id: str | None,
    action: str,
    note: str | None = None,
    db_path: str | Path | None = None,
) -> int:
    """Persist a manual job-history action for dashboard tracking."""

    initialize_database(db_path)
    created_at = _now_utc()
    with get_connection(db_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO job_history (job_id, action, note, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (job_id, action, note, created_at),
        )
        return int(cursor.lastrowid)


def fetch_job_history(
    job_id: str | None = None,
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Return recorded job history rows, optionally filtered by job id."""

    query = "SELECT * FROM job_history"
    parameters: tuple[Any, ...] = ()
    if job_id:
        query += " WHERE job_id = ?"
        parameters = (job_id,)
    query += " ORDER BY created_at DESC, id DESC"

    with get_connection(db_path) as connection:
        rows = connection.execute(query, parameters).fetchall()
    return [dict(row) for row in rows]


def fetch_recent_jobs(
    *,
    limit: int = 100,
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Return the most recently stored jobs."""

    with get_connection(db_path) as connection:
        rows = connection.execute(
            "SELECT * FROM jobs ORDER BY timestamp DESC, id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def fetch_dashboard_summary(db_path: str | Path | None = None) -> dict[str, int]:
    """Return aggregate counts used by the dashboard."""

    with get_connection(db_path) as connection:
        jobs_count = connection.execute("SELECT COUNT(*) AS count FROM jobs").fetchone()["count"]
        companies_count = connection.execute("SELECT COUNT(*) AS count FROM companies").fetchone()["count"]
        alerts_count = connection.execute("SELECT COUNT(*) AS count FROM alerts").fetchone()["count"]
        history_count = connection.execute("SELECT COUNT(*) AS count FROM job_history").fetchone()["count"]
        recent_alerts_count = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM alerts
            WHERE date(created_at) = date('now')
            """
        ).fetchone()["count"]

    return {
        "jobs": int(jobs_count),
        "companies": int(companies_count),
        "alerts": int(alerts_count),
        "history": int(history_count),
        "today_alerts": int(recent_alerts_count),
    }