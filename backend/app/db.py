from __future__ import annotations

import difflib
import sqlite3
import threading
import time
from contextlib import contextmanager
from typing import Optional

from .config import DB_PATH

_lock = threading.Lock()


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


@contextmanager
def _cursor():
    with _lock:
        conn = _connect()
        try:
            yield conn.cursor()
            conn.commit()
        finally:
            conn.close()


def init_db() -> None:
    with _cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                description TEXT NOT NULL,
                norm        TEXT NOT NULL,
                score       INTEGER,
                loops       INTEGER,
                created_at  REAL NOT NULL,
                pinned      INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_history_norm ON history(norm);")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS models (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                history_id  INTEGER,
                xml         TEXT NOT NULL,
                score       INTEGER,
                band        TEXT,
                created_at  REAL NOT NULL
            );
            """
        )


def _norm(text: str) -> str:
    return " ".join((text or "").lower().split())


def add_history(description: str, score: Optional[int] = None, loops: Optional[int] = None) -> int:
    desc = (description or "").strip()
    if not desc:
        return -1
    norm = _norm(desc)
    with _cursor() as cur:
        row = cur.execute("SELECT id FROM history WHERE norm = ? LIMIT 1", (norm,)).fetchone()
        if row:
            cur.execute(
                "UPDATE history SET created_at = ?, score = COALESCE(?, score), loops = COALESCE(?, loops) WHERE id = ?",
                (time.time(), score, loops, row["id"]),
            )
            return row["id"]
        cur.execute(
            "INSERT INTO history (description, norm, score, loops, created_at) VALUES (?,?,?,?,?)",
            (desc, norm, score, loops, time.time()),
        )
        return cur.lastrowid


def list_history(limit: int = 100) -> list[dict]:
    with _cursor() as cur:
        rows = cur.execute(
            "SELECT * FROM history ORDER BY pinned DESC, created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [_history_row(r) for r in rows]


def delete_history(hid: int) -> None:
    with _cursor() as cur:
        cur.execute("DELETE FROM history WHERE id = ?", (hid,))


def clear_history() -> None:
    with _cursor() as cur:
        cur.execute("DELETE FROM history WHERE pinned = 0")


def toggle_pin(hid: int) -> None:
    with _cursor() as cur:
        cur.execute("UPDATE history SET pinned = 1 - pinned WHERE id = ?", (hid,))


def suggest(query: str, limit: int = 5, cutoff: float = 0.45) -> list[dict]:
    q = _norm(query)
    if len(q) < 4:
        return []
    q_tokens = set(q.split())
    scored = []
    with _cursor() as cur:
        rows = cur.execute("SELECT * FROM history").fetchall()
    for r in rows:
        cand = r["norm"]
        ratio = difflib.SequenceMatcher(None, q, cand).ratio()
        c_tokens = set(cand.split())
        overlap = len(q_tokens & c_tokens) / max(1, len(q_tokens | c_tokens))
        sim = max(ratio, overlap)
        if sim >= cutoff and cand != q:
            item = _history_row(r)
            item["similarity"] = round(sim, 3)
            scored.append(item)
    scored.sort(key=lambda x: x["similarity"], reverse=True)
    return scored[:limit]


def _history_row(r: sqlite3.Row) -> dict:
    return {
        "id": r["id"],
        "description": r["description"],
        "score": r["score"],
        "loops": r["loops"],
        "pinned": bool(r["pinned"]),
        "createdAt": r["created_at"],
    }


def save_model(xml: str, score: Optional[int], band: Optional[str], history_id: Optional[int] = None) -> int:
    with _cursor() as cur:
        cur.execute(
            "INSERT INTO models (history_id, xml, score, band, created_at) VALUES (?,?,?,?,?)",
            (history_id, xml, score, band, time.time()),
        )
        return cur.lastrowid
