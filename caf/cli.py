"""CLI demo: run a sample publishing workflow end to end.

Usage:
    python3 -m caf.cli [--db PATH]

The demo creates a piece of sample content, runs the standard-publish
workflow (validate -> transform -> approval gate -> publish), shows it
pausing at the approval gate, approves it, and resumes it to published.
"""

from __future__ import annotations

import argparse

from .engine import Engine
from .store import Store


def main() -> None:
    parser = argparse.ArgumentParser(description="Content Automation Framework demo")
    parser.add_argument("--db", default="caf_jobs.db")
    args = parser.parse_args()

    engine = Engine(Store(args.db))
    content = {
        "title": "  Launch   Announcement  ",
        "body": "  Our   new   guide   is   live.  ",
        "author": "Chethan",
    }
    job = engine.create_job("standard-publish", content)
    print(f"Created job {job.id} (workflow: standard-publish, status: {job.status})")

    job = engine.run_job(job.id)
    print(f"After first run: status={job.status}")
    for step in job.steps:
        print(f"  - {step['step']}: {step['outcome']} ({step['message']})")
    print(f"  content so far: title={job.content['title']!r}, slug={job.content.get('slug')!r}")

    if job.status == "awaiting_approval":
        print("Approval gate blocked publishing, as designed. Approving and resuming...")
        job = engine.approve_job(job.id)
        print(f"After approval: status={job.status}")
        for step in job.steps:
            print(f"  - {step['step']}: {step['outcome']} ({step['message']})")
        print(f"  published={job.content.get('published')}")
    print(f"Demo complete: job {job.id} is {job.status}.")


if __name__ == "__main__":
    main()
