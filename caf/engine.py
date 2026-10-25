"""Workflow engine: chain steps into named workflows and run jobs.

Job statuses:
    pending            -- created, not yet run
    running            -- steps are executing
    awaiting_approval  -- paused at the approval gate (not a failure;
                          the job can be approved and resumed)
    approved           -- all steps passed and no publish step ran
    published          -- the publish step succeeded
    failed             -- a step failed; later steps did not run
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .steps import (
    ApprovalGateStep,
    PublishStep,
    StepResult,
    TransformStep,
    ValidateStep,
    WorkflowStep,
)
from .store import Store


@dataclass
class Job:
    id: int
    workflow_name: str
    status: str
    content: dict
    approved: bool = False
    requires_approval: bool = True
    steps: list = field(default_factory=list)


@dataclass
class Workflow:
    name: str
    steps: list[WorkflowStep]
    requires_approval: bool = True


# Named, reusable workflows. Only steps from this module are used.
WORKFLOWS: dict[str, Workflow] = {
    "standard-publish": Workflow(
        "standard-publish",
        [ValidateStep(), TransformStep(), ApprovalGateStep(), PublishStep()],
        requires_approval=True,
    ),
    "quick-publish": Workflow(
        "quick-publish",
        [ValidateStep(), TransformStep(), PublishStep()],
        requires_approval=False,
    ),
}


class Engine:
    def __init__(self, store: Store):
        self.store = store

    # -- job lifecycle --------------------------------------------------
    def create_job(
        self, workflow_name: str, content: dict, approved: bool = False
    ) -> Job:
        workflow = WORKFLOWS[workflow_name]  # KeyError for unknown workflows
        record = self.store.create_job(
            workflow_name, dict(content), workflow.requires_approval
        )
        if approved:
            record = self.store.update_job(record["id"], approved=True)
        return self._to_job(record)

    def get_job(self, job_id: int) -> Job | None:
        record = self.store.get_job(job_id)
        return self._to_job(record) if record else None

    def list_jobs(self) -> list[Job]:
        return [self._to_job(r) for r in self.store.list_jobs()]

    def approve_job(self, job_id: int) -> Job | None:
        """Approve a job and resume it from the step where it paused."""
        record = self.store.get_job(job_id)
        if record is None:
            return None
        self.store.update_job(job_id, approved=True)
        return self.run_job(job_id)

    # -- execution --------------------------------------------------------
    def run_job(self, job_id: int) -> Job | None:
        record = self.store.get_job(job_id)
        if record is None:
            return None
        job = self._to_job(record)
        workflow = WORKFLOWS[job.workflow_name]

        # Resume: skip steps that already succeeded in an earlier run.
        done = {
            s["step"]
            for s in record["steps"]
            if s["outcome"] == "success"
        }
        self.store.update_job(job_id, status="running", content=job.content)
        published = False
        for step in workflow.steps:
            if step.name in done:
                if step.name == "publish":
                    published = True
                continue
            try:
                result: StepResult = step.run(job, job.content)
            except Exception as exc:  # a step must never crash the engine
                result = StepResult(step.name, "failed", f"{type(exc).__name__}: {exc}")
            job.approved = self.store.get_job(job_id)["approved"]
            self.store.add_step_result(
                job_id, result.step, result.outcome, result.message
            )
            self.store.update_job(job_id, content=job.content)
            if result.outcome == "failed":
                self.store.update_job(job_id, status="failed")
                return self.get_job(job_id)
            if result.outcome == "blocked":
                self.store.update_job(job_id, status="awaiting_approval")
                return self.get_job(job_id)
            if step.name == "publish":
                published = True
        final = "published" if published else "approved"
        self.store.update_job(job_id, status=final)
        return self.get_job(job_id)

    # -- helpers ------------------------------------------------------------
    @staticmethod
    def _to_job(record: dict) -> Job:
        return Job(
            id=record["id"],
            workflow_name=record["workflow_name"],
            status=record["status"],
            content=record["content"],
            approved=record["approved"],
            requires_approval=record["requires_approval"],
            steps=record["steps"],
        )
