"""SQLite job store: jobs and their step results, persisted across runs.

ThreadingHTTPServer handles requests on worker threads, so the single
connection is created with check_same_thread=False and every operation
is serialised with a lock.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path


class Store:
    def __init__(self, path: str | Path = "caf_jobs.db"):
        self.path = str(path)
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workflow_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    content_json TEXT NOT NULL,
                    approved INTEGER NOT NULL DEFAULT 0,
                    requires_approval INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS step_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id INTEGER NOT NULL REFERENCES jobs(id),
                    seq INTEGER NOT NULL,
                    step TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    message TEXT NOT NULL DEFAULT ''
                );
                """
            )
            self.conn.commit()

    # -- jobs ---------------------------------------------------------
    def create_job(
        self, workflow_name: str, content: dict, requires_approval: bool = True
    ) -> dict:
        with self._lock:
            cur = self.conn.execute(
                "INSERT INTO jobs (workflow_name, status, content_json, approved,"
                " requires_approval) VALUES (?, 'pending', ?, 0, ?)",
                (workflow_name, json.dumps(content), int(requires_approval)),
            )
            self.conn.commit()
            job_id = cur.lastrowid
        return self.get_job(job_id)

    def get_job(self, job_id: int) -> dict | None:
        with self._lock:
            row = self.conn.execute(
                "SELECT * FROM jobs WHERE id = ?", (job_id,)
            ).fetchone()
            if row is None:
                return None
            job = dict(row)
            steps = self.conn.execute(
                "SELECT step, outcome, message FROM step_results"
                " WHERE job_id = ? ORDER BY seq",
                (job_id,),
            ).fetchall()
        job["content"] = json.loads(job.pop("content_json"))
        job["approved"] = bool(job["approved"])
        job["requires_approval"] = bool(job["requires_approval"])
        job["steps"] = [dict(r) for r in steps]
        return job

    def list_jobs(self) -> list[dict]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT id FROM jobs ORDER BY id"
            ).fetchall()
            ids = [r["id"] for r in rows]
        return [self.get_job(i) for i in ids]

    def update_job(
        self,
        job_id: int,
        *,
        status: str | None = None,
        content: dict | None = None,
        approved: bool | None = None,
    ) -> dict | None:
        with self._lock:
            if status is not None:
                self.conn.execute(
                    "UPDATE jobs SET status = ?, updated_at = datetime('now')"
                    " WHERE id = ?",
                    (status, job_id),
                )
            if content is not None:
                self.conn.execute(
                    "UPDATE jobs SET content_json = ?, updated_at = datetime('now')"
                    " WHERE id = ?",
                    (json.dumps(content), job_id),
                )
            if approved is not None:
                self.conn.execute(
                    "UPDATE jobs SET approved = ?, updated_at = datetime('now')"
                    " WHERE id = ?",
                    (int(approved), job_id),
                )
            self.conn.commit()
        return self.get_job(job_id)

    # -- step results ---------------------------------------------------
    def add_step_result(
        self, job_id: int, step: str, outcome: str, message: str = ""
    ) -> None:
        with self._lock:
            seq = self.conn.execute(
                "SELECT COALESCE(MAX(seq), -1) + 1 AS nxt FROM step_results"
                " WHERE job_id = ?",
                (job_id,),
            ).fetchone()["nxt"]
            self.conn.execute(
                "INSERT INTO step_results (job_id, seq, step, outcome, message)"
                " VALUES (?, ?, ?, ?, ?)",
                (job_id, seq, step, outcome, message),
            )
            self.conn.commit()

    def get_step_results(self, job_id: int) -> list[dict]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT step, outcome, message FROM step_results"
                " WHERE job_id = ? ORDER BY seq",
                (job_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def close(self) -> None:
        with self._lock:
            self.conn.close()
