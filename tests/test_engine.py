"""Tests: step chaining, approval gate, failed steps, normalisation."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from caf.engine import Engine
from caf.store import Store


def make_engine():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    return Engine(Store(tmp.name)), tmp.name


class TestStepChaining(unittest.TestCase):
    def test_quick_publish_runs_steps_in_order_and_publishes(self):
        engine, _ = make_engine()
        job = engine.create_job(
            "quick-publish",
            {"title": " Hello ", "body": " World "},
        )
        job = engine.run_job(job.id)
        self.assertEqual(job.status, "published")
        self.assertEqual(
            [s["step"] for s in job.steps], ["validate", "transform", "publish"]
        )
        self.assertTrue(job.content["published"])

    def test_transform_normalises_whitespace_and_builds_slug(self):
        engine, _ = make_engine()
        job = engine.create_job(
            "quick-publish",
            {"title": "  Launch   Announcement ", "body": "  A   B  "},
        )
        job = engine.run_job(job.id)
        self.assertEqual(job.content["title"], "Launch Announcement")
        self.assertEqual(job.content["body"], "A B")
        self.assertEqual(job.content["slug"], "launch-announcement")


class TestApprovalGate(unittest.TestCase):
    def test_gate_blocks_publish_until_approved(self):
        engine, _ = make_engine()
        job = engine.create_job(
            "standard-publish", {"title": "T", "body": "B"}
        )
        job = engine.run_job(job.id)
        self.assertEqual(job.status, "awaiting_approval")
        self.assertNotIn("publish", [s["step"] for s in job.steps])
        self.assertIsNone(job.content.get("published"))

    def test_approve_and_resume_publishes_without_rerunning_steps(self):
        engine, _ = make_engine()
        job = engine.create_job(
            "standard-publish", {"title": "T", "body": "B"}
        )
        engine.run_job(job.id)
        job = engine.approve_job(job.id)
        self.assertEqual(job.status, "published")
        self.assertTrue(job.content["published"])
        # validate/transform ran once each, not again on resume.
        # The approval step appears twice in the audit trail: once blocked,
        # once succeeding after approval.
        names = [s["step"] for s in job.steps]
        self.assertEqual(names.count("validate"), 1)
        self.assertEqual(names.count("transform"), 1)
        self.assertEqual(
            names, ["validate", "transform", "approval", "approval", "publish"]
        )
        self.assertEqual(
            [s["outcome"] for s in job.steps if s["step"] == "approval"],
            ["blocked", "success"],
        )


class TestFailedSteps(unittest.TestCase):
    def test_empty_title_fails_and_skips_later_steps(self):
        engine, _ = make_engine()
        job = engine.create_job(
            "quick-publish", {"title": "   ", "body": "B"}
        )
        job = engine.run_job(job.id)
        self.assertEqual(job.status, "failed")
        self.assertEqual([s["step"] for s in job.steps], ["validate"])
        self.assertIsNone(job.content.get("published"))

    def test_unknown_workflow_raises(self):
        engine, _ = make_engine()
        with self.assertRaises(KeyError):
            engine.create_job("no-such-workflow", {"title": "T", "body": "B"})


if __name__ == "__main__":
    unittest.main()
