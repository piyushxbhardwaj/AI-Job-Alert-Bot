"""Streamlit dashboard for AI-Job-Alert-Bot."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import streamlit as st

from database import (
    fetch_dashboard_summary,
    fetch_job_history,
    fetch_recent_jobs,
    initialize_database,
    record_job_history,
)
from utils import load_priority_companies, load_resume_text, score_job, score_resume_match

DB_PATH = Path(os.getenv("DATABASE_PATH", "state/jobs.db"))
PRIORITY_COMPANIES = load_priority_companies()
RESUME_TEXT = load_resume_text(os.getenv("RESUME_PATH", "").strip() or None)
DEFAULT_HISTORY_ACTIONS = ("applied", "ignored", "saved", "bookmarked", "rejected")


st.set_page_config(page_title="AI Job Intelligence Platform", page_icon="📈", layout="wide")


def _load_jobs() -> list[dict[str, Any]]:
    """Load the latest jobs from SQLite."""

    initialize_database(DB_PATH)
    return fetch_recent_jobs(limit=500, db_path=DB_PATH)


def _load_alert_status(job_id: str | None) -> str:
    if not job_id:
        return ""

    history = fetch_job_history(job_id, DB_PATH)
    if not history:
        return ""
    return history[0]["action"]


def _is_priority_company(company: str) -> bool:
    normalized_company = company.strip().lower()
    return any(normalized_company == item.strip().lower() for item in PRIORITY_COMPANIES)


@st.cache_data(ttl=60)
def _cached_summary() -> dict[str, int]:
    return fetch_dashboard_summary(DB_PATH)


@st.cache_data(ttl=30)
def _cached_jobs() -> list[dict[str, Any]]:
    return _load_jobs()


def _render_metric_cards(summary: dict[str, int], relevant_count: int) -> None:
    columns = st.columns(5)
    metrics = [
        ("Jobs Found", summary["jobs"]),
        ("Relevant Jobs", relevant_count),
        ("Today\'s Jobs", summary["today_alerts"]),
        ("Priority Companies", len(PRIORITY_COMPANIES)),
        ("History Events", summary["history"]),
    ]
    for column, (label, value) in zip(columns, metrics, strict=False):
        with column:
            st.metric(label, value)


def _build_rows(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for job in jobs:
        scoring = score_job(
            title=job.get("title", ""),
            company=job.get("company", ""),
            description=job.get("description", ""),
            location=job.get("location", ""),
        )
        resume_score = None
        missing_skills: tuple[str, ...] = tuple()
        if RESUME_TEXT:
            resume_result = score_resume_match(
                job_description=f"{job.get('title', '')} {job.get('description', '')}",
                resume_text=RESUME_TEXT,
            )
            resume_score = resume_result.resume_match_score
            missing_skills = resume_result.missing_skills

        rows.append(
            {
                "Job ID": job.get("job_id") or "",
                "Company": job.get("company", ""),
                "Title": job.get("title", ""),
                "Source": job.get("source", ""),
                "Location": job.get("location", "Remote"),
                "Match Score": scoring.match_score,
                "Resume Match": resume_score if resume_score is not None else "-",
                "Priority": "Yes" if _is_priority_company(job.get("company", "")) else "No",
                "Apply": job.get("url", ""),
                "Status": _load_alert_status(job.get("job_id")),
                "Reasons": ", ".join(scoring.reasons[:4]),
                "Missing Skills": ", ".join(missing_skills[:5]) if missing_skills else "",
                "Timestamp": job.get("timestamp", ""),
            }
        )
    return rows


def _filter_rows(rows: list[dict[str, Any]], query: str, source: str, priority_only: bool, minimum_score: int) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    query_lower = query.strip().lower()
    source_lower = source.strip().lower()
    for row in rows:
        if query_lower:
            searchable = " ".join(str(value) for key, value in row.items() if key not in {"Apply", "Timestamp"}).lower()
            if query_lower not in searchable:
                continue
        if source_lower and row["Source"].lower() != source_lower:
            continue
        if priority_only and row["Priority"] != "Yes":
            continue
        if int(row["Match Score"]) < minimum_score:
            continue
        filtered.append(row)
    return filtered


def _record_action(job_id: str | None, action: str, note: str) -> None:
    if not job_id:
        st.error("This job does not have an ID to record history against.")
        return
    record_job_history(job_id=job_id, action=action, note=note or None, db_path=DB_PATH)
    st.cache_data.clear()


def main() -> None:
    st.title("AI Job Intelligence Platform")
    st.caption("Monitor multiple job sources, score relevance, and track manual history from one place.")

    summary = _cached_summary()
    jobs = _cached_jobs()
    rows = _build_rows(jobs)

    with st.sidebar:
        st.header("Filters")
        search_query = st.text_input("Search", placeholder="Python, OpenAI, remote, FastAPI")
        source_options = sorted({row["Source"] for row in rows if row["Source"]})
        source_filter = st.selectbox("Source", ["All", *source_options])
        minimum_score = st.slider("Minimum match score", 0, 100, 50)
        priority_only = st.toggle("Priority companies only", value=False)
        st.divider()
        st.subheader("Priority Companies")
        if PRIORITY_COMPANIES:
            for company in PRIORITY_COMPANIES[:12]:
                st.write(f"• {company}")
        else:
            st.write("No priority company file found.")

    filtered_rows = _filter_rows(
        rows,
        query=search_query,
        source="" if source_filter == "All" else source_filter,
        priority_only=priority_only,
        minimum_score=minimum_score,
    )
    relevant_count = len([row for row in rows if int(row["Match Score"]) >= 60])
    _render_metric_cards(summary, relevant_count)

    st.subheader("Jobs")
    st.dataframe(filtered_rows, use_container_width=True, hide_index=True)

    if filtered_rows:
        selected_titles = [f"{row['Company']} - {row['Title']}" for row in filtered_rows]
        selected_index = st.selectbox("Select a job for details", range(len(filtered_rows)), format_func=lambda index: selected_titles[index])
        selected_row = filtered_rows[selected_index]

        detail_left, detail_right = st.columns([2, 1])
        with detail_left:
            st.markdown(f"### {selected_row['Title']}")
            st.write(f"**Company:** {selected_row['Company']}")
            st.write(f"**Source:** {selected_row['Source']}")
            st.write(f"**Location:** {selected_row['Location']}")
            st.write(f"**Match Score:** {selected_row['Match Score']}%")
            if selected_row["Resume Match"] != "-":
                st.write(f"**Resume Match:** {selected_row['Resume Match']}%")
            st.write(f"**Priority:** {selected_row['Priority']}")
            st.write(f"**Reasons:** {selected_row['Reasons'] or 'None'}")
            if selected_row["Missing Skills"]:
                st.write(f"**Missing Skills:** {selected_row['Missing Skills']}")
            st.link_button("Open application", selected_row["Apply"])

        with detail_right:
            st.markdown("### History")
            action = st.selectbox("Action", DEFAULT_HISTORY_ACTIONS, key=f"action-{selected_row['Job ID']}")
            note = st.text_area("Note", key=f"note-{selected_row['Job ID']}")
            if st.button("Save history", key=f"save-{selected_row['Job ID']}"):
                _record_action(selected_row["Job ID"], action, note)
                st.success("Saved history event.")

    st.divider()
    st.subheader("Recent history")
    st.dataframe(fetch_job_history(db_path=DB_PATH)[:100], use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
