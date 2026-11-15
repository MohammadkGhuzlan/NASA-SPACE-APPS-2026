"""Bounded HTTP acquisition with immutable cache checks and safe range resumption."""
import time
import fcntl
from pathlib import Path
from urllib.parse import urlparse

import httpx

from .common import read_json, sha256, write_json, now

ALLOWED = {"data.apps.fao.org", "storage.googleapis.com", "power.larc.nasa.gov",
           "rest.isric.org", "maps.isric.org", "files.isric.org",
           "raw.githubusercontent.com"}


def download(url, destination, *, max_bytes=30_000_000, attempts=3):
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Protect cache/resume files across threads and concurrent CLI processes.
    with path.with_suffix(path.suffix + ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return _download(url, destination, max_bytes=max_bytes, attempts=attempts)


def _download(url, destination, *, max_bytes=30_000_000, attempts=3):
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED:
        raise ValueError("Only documented official HTTPS sources are allowed")
    path = Path(destination)
    sidecar = path.with_suffix(path.suffix + ".source.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        evidence = read_json(sidecar)
        if evidence["url"] != url or evidence["sha256"] != sha256(path):
            raise ValueError("Cache provenance/hash mismatch; refusing reuse")
        return evidence
    part = path.with_suffix(path.suffix + ".part")
    state_path = part.with_suffix(part.suffix + ".json")
    for attempt in range(attempts):
        try:
            state = read_json(state_path) if state_path.exists() else {}
            offset = part.stat().st_size if part.exists() else 0
            resumable = offset and state.get("url") == url and state.get("etag")
            headers = {"User-Agent": "FieldShift-Research/phase4"}
            if resumable:
                headers.update(Range=f"bytes={offset}-", **{"If-Range": state["etag"]})
            with httpx.Client(timeout=httpx.Timeout(90, connect=15), follow_redirects=False) as client:
                with client.stream("GET", url, headers=headers) as response:
                    response.raise_for_status()
                    append = resumable and response.status_code == 206
                    if append and not response.headers.get("content-range", "").startswith(f"bytes {offset}-"):
                        raise ValueError("Invalid resumed Content-Range")
                    if not append:
                        offset = 0
                    if int(response.headers.get("content-length", 0)) + offset > max_bytes:
                        raise ValueError("Download exceeds explicit size budget")
                    write_json(state_path, {"url": url, "etag": response.headers.get("etag")})
                    count = offset
                    with part.open("ab" if append else "wb") as stream:
                        for chunk in response.iter_bytes(1024 * 128):
                            count += len(chunk)
                            if count > max_bytes:
                                raise ValueError("Download exceeds explicit size budget")
                            stream.write(chunk)
                    expected = response.headers.get("content-length")
                    if expected and count - offset != int(expected):
                        raise ValueError("Truncated download")
                    evidence = {"url": url, "sha256": sha256(part), "bytes": count,
                                "retrieved_at": now(), "etag": response.headers.get("etag")}
            part.replace(path)
            write_json(sidecar, evidence)
            state_path.unlink(missing_ok=True)
            time.sleep(.5)
            return evidence
        except (httpx.HTTPError, OSError) as exc:
            retryable = not isinstance(exc, httpx.HTTPStatusError) or exc.response.status_code in {429, 500, 502, 503, 504}
            if not retryable or attempt == attempts - 1:
                raise
            time.sleep(min(2 ** attempt * 2, 8))
    raise RuntimeError("unreachable")
