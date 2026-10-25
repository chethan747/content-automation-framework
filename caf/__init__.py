"""Content Automation Framework: a small workflow engine for content operations."""

from .engine import Engine, Job, StepResult, Workflow
from .steps import ApprovalGateStep, PublishStep, TransformStep, ValidateStep
from .store import Store

__all__ = [
    "Engine",
    "Job",
    "StepResult",
    "Workflow",
    "ApprovalGateStep",
    "PublishStep",
    "TransformStep",
    "ValidateStep",
    "Store",
]
