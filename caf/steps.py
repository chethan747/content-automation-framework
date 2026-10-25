"""Reusable workflow steps.

Each step takes a job and a mutable content dict and returns a StepResult.
Outcomes are "success", "blocked" (a gate stopped the workflow without
failing it) or "failed" (an error stopped the workflow).
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class StepResult:
    step: str
    outcome: str  # "success" | "blocked" | "failed"
    message: str = ""
    data: dict | None = None


class WorkflowStep:
    """Base class for a single workflow step."""

    name = "step"

    def run(self, job, content: dict) -> StepResult:  # noqa: ARG002 - subclasses use job
        raise NotImplementedError


class ValidateStep(WorkflowStep):
    """Reject content that is missing a title or a body."""

    name = "validate"

    def run(self, job, content: dict) -> StepResult:
        title = (content.get("title") or "").strip()
        body = (content.get("body") or "").strip()
        if not title:
            return StepResult(self.name, "failed", "Content has no title.")
        if not body:
            return StepResult(self.name, "failed", "Content has no body.")
        return StepResult(self.name, "success", "Content is valid.")


class TransformStep(WorkflowStep):
    """Normalise content: trim, collapse whitespace, and build a slug."""

    name = "transform"

    def run(self, job, content: dict) -> StepResult:
        title = re.sub(r"\s+", " ", (content.get("title") or "")).strip()
        body = re.sub(r"\s+", " ", (content.get("body") or "")).strip()
        content["title"] = title
        content["body"] = body
        content["slug"] = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        return StepResult(
            self.name, "success", "Content normalised.", {"slug": content["slug"]}
        )


class ApprovalGateStep(WorkflowStep):
    """Block the workflow until the job has been approved.

    This is a gate, not a failure: an unapproved job pauses here and can
    be resumed after approval, without re-running earlier steps.
    """

    name = "approval"

    def run(self, job, content: dict) -> StepResult:
        if getattr(job, "approved", False):
            return StepResult(self.name, "success", "Approved.")
        return StepResult(
            self.name, "blocked", "Waiting for approval; publish is blocked."
        )


class PublishStep(WorkflowStep):
    """Publish content. Refuses to publish an unapproved job."""

    name = "publish"

    def run(self, job, content: dict) -> StepResult:
        if not getattr(job, "approved", False) and getattr(
            job, "requires_approval", True
        ):
            return StepResult(
                self.name, "blocked", "Publish blocked: job is not approved."
            )
        content["published"] = True
        return StepResult(self.name, "success", "Content published.")
