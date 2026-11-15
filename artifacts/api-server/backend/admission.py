"""Shared, transactionally admitted budgets for expensive work.

Uses private short-lived technical rows in the existing ingestion ledger;
no migration, model activation, raw owner identifier, or user-data deletion.
"""
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func, text, delete
from fastapi import HTTPException
from .models import IngestionReport

PREFIX = "FIELD_SHIFT_ADMISSION_V1:"


def admit(db, kind, limit, scope=None, scope_limit=None, now=None):
    if kind not in {"analysis", "nasa"}:
        raise ValueError("Unknown admission kind")
    now = now or datetime.now(timezone.utc)
    source = PREFIX + kind
    # Short lock + commit; never held while calling an external service.
    lock_key = 73651001 if kind == "analysis" else 73651002
    db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_key})
    recent = [IngestionReport.source == source,
              IngestionReport.started_at > now - timedelta(seconds=60)]
    total = db.scalar(select(func.count()).select_from(IngestionReport).where(*recent))
    own = db.scalar(select(func.count()).select_from(IngestionReport).where(
        *recent, IngestionReport.report["scope"].as_string() == scope)) if scope else 0
    if total >= limit or (scope_limit is not None and own >= scope_limit):
        # Do not leave an admission lock held until the request session closes.
        db.rollback()
        raise HTTPException(429, "The analysis/data service is busy. Please retry in a minute.",
                            headers={"Retry-After": "60"})
    # Only private technical admissions created by this service expire. Never
    # delete environmental observations, real import audits, or farmer records.
    db.execute(delete(IngestionReport).where(
        IngestionReport.source == source,
        IngestionReport.started_at < now - timedelta(days=1)))
    db.add(IngestionReport(source=source, status="internal_admission",
                           started_at=now, completed_at=now, report={"scope": scope}))
    db.commit()
