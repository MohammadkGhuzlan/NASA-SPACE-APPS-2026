"""Shared admission: browser-specific AND global limits survive worker changes."""
from hashlib import sha256
from ..admission import admit


def check_analysis_rate(owner, db):
    admit(db, "analysis", limit=24, scope=sha256(owner.encode()).hexdigest(), scope_limit=6)
