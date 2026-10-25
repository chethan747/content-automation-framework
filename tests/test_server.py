"""Tests: HTTP layer endpoints, using a real server on an ephemeral port."""

import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from caf.engine import Engine
from caf.server import make_handler
from caf.store import Store


class TestServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        cls.engine = Engine(Store(tmp.name))
        cls.server = ThreadingHTTPServer(
            ("127.0.0.1", 0), make_handler(cls.engine)
        )
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def _request(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read() or b"{}")

    def test_run_lists_and_gets_jobs(self):
        status, job = self._request(
            "POST",
            "/workflows/run",
            {"workflow": "quick-publish", "content": {"title": "T", "body": "B"}},
        )
        self.assertEqual(status, 201)
        self.assertEqual(job["status"], "published")

        status, jobs = self._request("GET", "/jobs")
        self.assertEqual(status, 200)
        self.assertTrue(any(j["id"] == job["id"] for j in jobs))

        status, one = self._request("GET", f"/jobs/{job['id']}")
        self.assertEqual(status, 200)
        self.assertEqual(one["id"], job["id"])

    def test_unknown_workflow_and_missing_job(self):
        status, _ = self._request(
            "POST",
            "/workflows/run",
            {"workflow": "nope", "content": {"title": "T", "body": "B"}},
        )
        self.assertEqual(status, 404)
        status, _ = self._request("GET", "/jobs/999999")
        self.assertEqual(status, 404)

    def test_approve_endpoint_resumes_paused_job(self):
        _, job = self._request(
            "POST",
            "/workflows/run",
            {"workflow": "standard-publish", "content": {"title": "T", "body": "B"}},
        )
        self.assertEqual(job["status"], "awaiting_approval")
        status, job = self._request("POST", f"/jobs/{job['id']}/approve")
        self.assertEqual(status, 200)
        self.assertEqual(job["status"], "published")


if __name__ == "__main__":
    unittest.main()
