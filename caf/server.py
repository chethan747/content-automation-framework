"""Servlet-style HTTP layer, stdlib only.

Endpoints (JSON):
    GET  /workflows            -- named workflows and their steps
    POST /workflows/run        -- {"workflow": str, "content": {...},
                                   "approved": bool} -> created + run job
    GET  /jobs                 -- all jobs
    GET  /jobs/<id>            -- one job (404 when missing)
    POST /jobs/<id>/approve    -- approve and resume a paused job

Run:  python3 -m caf.server [--port 8000] [--db caf_jobs.db]
"""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .engine import WORKFLOWS, Engine
from .store import Store


def job_to_json(job):
    return {
        "id": job.id,
        "workflow": job.workflow_name,
        "status": job.status,
        "approved": job.approved,
        "content": job.content,
        "steps": job.steps,
    }


def make_handler(engine: Engine):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: int, payload) -> None:
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _read_json(self) -> dict:
            length = int(self.headers.get("Content-Length") or 0)
            if not length:
                return {}
            return json.loads(self.rfile.read(length) or b"{}")

        def do_GET(self):  # noqa: N802 - http.server naming
            if self.path == "/workflows":
                self._send(
                    200,
                    {
                        name: [s.name for s in wf.steps]
                        for name, wf in WORKFLOWS.items()
                    },
                )
            elif self.path == "/jobs":
                self._send(200, [job_to_json(j) for j in engine.list_jobs()])
            elif self.path.startswith("/jobs/"):
                try:
                    job_id = int(self.path.split("/")[2])
                except (IndexError, ValueError):
                    self._send(404, {"error": "job not found"})
                    return
                job = engine.get_job(job_id)
                if job is None:
                    self._send(404, {"error": "job not found"})
                else:
                    self._send(200, job_to_json(job))
            else:
                self._send(404, {"error": "unknown endpoint"})

        def do_POST(self):  # noqa: N802 - http.server naming
            if self.path == "/workflows/run":
                try:
                    body = self._read_json()
                    job = engine.create_job(
                        body["workflow"],
                        body.get("content", {}),
                        approved=bool(body.get("approved", False)),
                    )
                except KeyError:
                    self._send(404, {"error": "unknown workflow"})
                    return
                except (TypeError, ValueError):
                    self._send(400, {"error": "invalid request body"})
                    return
                job = engine.run_job(job.id)
                self._send(201, job_to_json(job))
            elif self.path.startswith("/jobs/") and self.path.endswith("/approve"):
                try:
                    job_id = int(self.path.split("/")[2])
                except (IndexError, ValueError):
                    self._send(404, {"error": "job not found"})
                    return
                job = engine.approve_job(job_id)
                if job is None:
                    self._send(404, {"error": "job not found"})
                else:
                    self._send(200, job_to_json(job))
            else:
                self._send(404, {"error": "unknown endpoint"})

        def log_message(self, *args):  # keep test/demo output clean
            pass

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description="Content Automation Framework server")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--db", default="caf_jobs.db")
    args = parser.parse_args()
    engine = Engine(Store(args.db))
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(engine))
    print(f"Content Automation Framework listening on http://127.0.0.1:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
