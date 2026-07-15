"""SQLite store for live TLE payloads, name-resolution drafts, and run state."""

from __future__ import annotations

import datetime as _dt
import json
import os
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any


PAYLOAD_TTL_MINUTES = 30
RUN_TTL_MINUTES = 30
RUN_TOUCH_THRESHOLD_MINUTES = 25
RUN_HARD_CAP_HOURS = 24
SQLITE_BUSY_TIMEOUT_MS = 30000
SQLITE_RETRY_DELAYS_S = (0.05, 0.1, 0.2, 0.4, 0.8)

_SCHEMA_READY = False
_SCHEMA_PATH: Path | None = None
_SCHEMA_LOCK = threading.Lock()


def utc_now() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


def isoformat_z(value: _dt.datetime) -> str:
    return (
        value.astimezone(_dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def parse_iso(value: str) -> _dt.datetime:
    return _dt.datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(
        _dt.timezone.utc
    )


def get_db_path() -> Path:
    data_dir = os.environ.get("ASTRA_DATA_DIR")
    if data_dir:
        base = Path(data_dir)
    else:
        base = Path(__file__).resolve().parents[2] / "astra-data"
    runtime = base / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    return runtime / "live_payloads.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(get_db_path()), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
    return conn


def _is_locked_error(exc: BaseException) -> bool:
    return isinstance(exc, sqlite3.OperationalError) and "locked" in str(exc).lower()


def _with_retry(operation):
    for index, delay_s in enumerate((0.0, *SQLITE_RETRY_DELAYS_S)):
        if delay_s:
            time.sleep(delay_s)
        try:
            return operation()
        except sqlite3.OperationalError as exc:
            if not _is_locked_error(exc) or index == len(SQLITE_RETRY_DELAYS_S):
                raise
    return None


def init_schema() -> None:
    global _SCHEMA_PATH, _SCHEMA_READY
    db_path = get_db_path()
    if _SCHEMA_READY and _SCHEMA_PATH == db_path:
        return
    with _SCHEMA_LOCK:
        if _SCHEMA_READY and _SCHEMA_PATH == db_path:
            return

        def _op() -> None:
            with _connect() as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS live_payloads (
                        payload_id TEXT PRIMARY KEY,
                        source TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        expires_at TEXT NOT NULL,
                        is_consumed INTEGER NOT NULL DEFAULT 0,
                        consumed_at TEXT,
                        consumed_by_run_id TEXT
                    );
                    CREATE TABLE IF NOT EXISTS live_resolution_drafts (
                        resolution_id TEXT PRIMARY KEY,
                        draft_json TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        expires_at TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS live_runs (
                        run_id TEXT PRIMARY KEY,
                        run_json TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        expires_at TEXT NOT NULL,
                        hard_expires_at TEXT NOT NULL
                    );
                    """
                )

        _with_retry(_op)
        _SCHEMA_PATH = db_path
        _SCHEMA_READY = True


def sweep_expired(now: _dt.datetime | None = None) -> None:
    init_schema()
    now_iso = isoformat_z(now or utc_now())

    def _op() -> None:
        with _connect() as conn:
            conn.execute("DELETE FROM live_payloads WHERE expires_at < ?", (now_iso,))
            conn.execute(
                "DELETE FROM live_resolution_drafts WHERE expires_at < ?", (now_iso,)
            )
            conn.execute(
                "DELETE FROM live_runs WHERE expires_at < ? OR hard_expires_at < ?",
                (now_iso, now_iso),
            )

    _with_retry(_op)


def store_payload(
    source: str, payload: dict[str, Any], ttl_minutes: int = PAYLOAD_TTL_MINUTES
) -> str:
    init_schema()
    now = utc_now()
    payload_id = uuid.uuid4().hex
    record = dict(payload)
    record.setdefault("source", source)
    record.setdefault("captured_at", isoformat_z(now))

    def _op() -> None:
        with _connect() as conn:
            conn.execute(
                """
                INSERT INTO live_payloads
                (payload_id, source, payload_json, created_at, expires_at, is_consumed)
                VALUES (?, ?, ?, ?, ?, 0)
                """,
                (
                    payload_id,
                    source,
                    json.dumps(record, separators=(",", ":")),
                    isoformat_z(now),
                    isoformat_z(now + _dt.timedelta(minutes=ttl_minutes)),
                ),
            )

    _with_retry(_op)
    return payload_id


def retrieve_payload(
    payload_id: str, *, include_consumed: bool = False
) -> dict[str, Any] | None:
    init_schema()
    now_iso = isoformat_z(utc_now())

    def _op():
        with _connect() as conn:
            return conn.execute(
                "SELECT * FROM live_payloads WHERE payload_id = ? AND expires_at >= ?",
                (payload_id, now_iso),
            ).fetchone()

    row = _with_retry(_op)
    if row is None:
        return None
    if row["is_consumed"] and not include_consumed:
        return None
    payload = json.loads(row["payload_json"])
    payload["_payload_id"] = row["payload_id"]
    payload["_is_consumed"] = bool(row["is_consumed"])
    return payload


def mark_payload_consumed(payload_id: str, run_id: str) -> None:
    init_schema()

    def _op() -> None:
        with _connect() as conn:
            conn.execute(
                """
                UPDATE live_payloads
                SET is_consumed = 1, consumed_at = ?, consumed_by_run_id = ?
                WHERE payload_id = ?
                """,
                (isoformat_z(utc_now()), run_id, payload_id),
            )

    _with_retry(_op)


def store_resolution_draft(
    draft: dict[str, Any], ttl_minutes: int = PAYLOAD_TTL_MINUTES
) -> str:
    init_schema()
    now = utc_now()
    resolution_id = uuid.uuid4().hex

    def _op() -> None:
        with _connect() as conn:
            conn.execute(
                """
                INSERT INTO live_resolution_drafts
                (resolution_id, draft_json, created_at, expires_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    resolution_id,
                    json.dumps(draft, separators=(",", ":")),
                    isoformat_z(now),
                    isoformat_z(now + _dt.timedelta(minutes=ttl_minutes)),
                ),
            )

    _with_retry(_op)
    return resolution_id


def retrieve_resolution_draft(resolution_id: str) -> dict[str, Any] | None:
    init_schema()
    now_iso = isoformat_z(utc_now())

    def _op():
        with _connect() as conn:
            return conn.execute(
                "SELECT draft_json FROM live_resolution_drafts WHERE resolution_id = ? AND expires_at >= ?",
                (resolution_id, now_iso),
            ).fetchone()

    row = _with_retry(_op)
    return json.loads(row["draft_json"]) if row else None


def store_run(run: dict[str, Any], run_id: str | None = None) -> str:
    init_schema()
    now = utc_now()
    rid = run_id or uuid.uuid4().hex

    def _op() -> None:
        with _connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO live_runs
                (run_id, run_json, created_at, expires_at, hard_expires_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    rid,
                    json.dumps(run, separators=(",", ":")),
                    isoformat_z(now),
                    isoformat_z(now + _dt.timedelta(minutes=RUN_TTL_MINUTES)),
                    isoformat_z(now + _dt.timedelta(hours=RUN_HARD_CAP_HOURS)),
                ),
            )

    _with_retry(_op)
    return rid


def retrieve_run(run_id: str) -> dict[str, Any] | None:
    init_schema()
    now = utc_now()
    now_iso = isoformat_z(now)

    def _op():
        with _connect() as conn:
            row = conn.execute(
                "SELECT * FROM live_runs WHERE run_id = ? AND expires_at >= ? AND hard_expires_at >= ?",
                (run_id, now_iso, now_iso),
            ).fetchone()
            if row is None:
                return None
            hard_expiry = parse_iso(row["hard_expires_at"])
            current_expiry = parse_iso(row["expires_at"])
            touch_threshold = now + _dt.timedelta(minutes=RUN_TOUCH_THRESHOLD_MINUTES)
            if current_expiry <= touch_threshold:
                next_expiry = min(
                    now + _dt.timedelta(minutes=RUN_TTL_MINUTES), hard_expiry
                )
                conn.execute(
                    "UPDATE live_runs SET expires_at = ? WHERE run_id = ?",
                    (isoformat_z(next_expiry), run_id),
                )
            return row

    row = _with_retry(_op)
    if row is None:
        return None
    run = json.loads(row["run_json"])
    run["_run_id"] = row["run_id"]
    return run


def update_run(run_id: str, run: dict[str, Any]) -> None:
    """Replace run_json without resetting created_at or the 24h hard cap."""
    init_schema()
    payload = dict(run)
    payload.pop("_run_id", None)

    def _op() -> None:
        with _connect() as conn:
            conn.execute(
                "UPDATE live_runs SET run_json = ? WHERE run_id = ?",
                (json.dumps(payload, separators=(",", ":")), run_id),
            )

    _with_retry(_op)
