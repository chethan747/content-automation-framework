"""Tests: job persistence across Store instances."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from caf.engine import Engine
from caf.store import Store


class TestPersistence(unittest.TestCase):
    def test_job_and_step_results_survive_reopen(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        engine = Engine(Store(tmp.name))
        job = engine.create_job("quick-publish", {"title": "T", "body": "B"})
        engine.run_job(job.id)

        reopened = Store(tmp.name)
        record = reopened.get_job(job.id)
        self.assertIsNotNone(record)
        self.assertEqual(record["status"], "published")
        self.assertEqual(record["content"]["title"], "T")
        self.assertEqual(
            [s["step"] for s in record["steps"]],
            ["validate", "transform", "publish"],
        )
        self.assertEqual(len(reopened.list_jobs()), 1)

    def test_missing_job_returns_none(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        self.assertIsNone(Store(tmp.name).get_job(9999))


if __name__ == "__main__":
    unittest.main()
