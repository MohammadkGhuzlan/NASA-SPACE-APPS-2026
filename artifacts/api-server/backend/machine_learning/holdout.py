"""One-use geographic holdouts, independent of dataset version/output directory."""
import json
from pathlib import Path

from .common import digest, now
from .contract import TARGET, SCENARIO

# Shared for all research dataset/output versions in this workspace. Operator
# recovery must preserve this directory together with published run evidence.
LEDGER_ROOT = Path("docs/ml-recovery/holdout-ledger")


def reserve(blocks, *, seed, run_identity, root=None):
    """Reserve the whole partition atomically, not individual crops/dataset hash.

    The seed-42 geography is the SAME scientific holdout even as source rows,
    feature schemas and dataset hashes change. Refuse any overlapping prior
    reservation; never automatically delete a reservation after failure/crash.
    """
    import fcntl
    root = Path(root if root is not None else LEDGER_ROOT)
    root.mkdir(parents=True, exist_ok=True)
    identity = {"mapset": TARGET["mapset"], "period": TARGET["period"],
                "climate": TARGET["label_climate"], "scenario": SCENARIO}
    keys = {digest({**identity, "block": b}): b for b in sorted(set(blocks))}
    if not keys:
        raise ValueError("cannot_reserve_empty_holdout")
    with (root / ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        existing = list(root.glob("reservation-*.json"))
        for path in existing:
            previous = json.loads(path.read_text())
            if set(keys) & set(previous["geographic_keys"]):
                raise ValueError("geographic_holdout_already_consumed")
        # Exclusive creation while holding a cross-process lock. A crash after
        # this point requires an explicit audited recovery, not a silent retry.
        path = root / ("reservation-" + digest(sorted(keys)) + ".json")
        record = {"reserved_at": now(), "identity": identity, "geographic_keys": keys,
                  "split_seed": seed, "run_identity": run_identity}
        with path.open("x") as stream:
            json.dump(record, stream, indent=2, sort_keys=True)
        return record
