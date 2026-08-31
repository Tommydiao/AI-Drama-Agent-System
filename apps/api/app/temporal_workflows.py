"""Deterministic Temporal Workflows. No database, filesystem, provider, or network I/O."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

from .orchestration import ProjectOrchestrationRequest, ShotOperation


@dataclass(frozen=True)
class ShotWorkflowResult:
    shot_id: str
    operation_id: str
    state: str


@workflow.defn(name="ai-drama-shot-v1")
class ShotWorkflow:
    @workflow.run
    async def run(self, request: ShotOperation) -> ShotWorkflowResult:
        result = await workflow.execute_activity(
            "execute-shot-operation",
            request,
            activity_id=request.operation_id,
            start_to_close_timeout=timedelta(minutes=30),
            heartbeat_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=1),
                maximum_interval=timedelta(minutes=1),
                maximum_attempts=5,
            ),
        )
        return ShotWorkflowResult(
            shot_id=request.shot_id,
            operation_id=request.operation_id,
            state=result["state"],
        )


@workflow.defn(name="ai-drama-project-v1")
class ProjectWorkflow:
    def __init__(self) -> None:
        self.project_id = ""
        self.paused = False
        self.cancel_requested = False
        self.phase = "CREATED"
        self.total_shots = 0
        self.completed_shots: list[str] = []
        self.in_flight_shot_id: str | None = None
        self.workflow_version = 1

    @workflow.signal
    def pause(self) -> None:
        self.paused = True

    @workflow.signal
    def resume(self) -> None:
        self.paused = False

    @workflow.signal
    def request_cancel(self) -> None:
        # Accepted provider work is allowed to reconcile. No new child starts afterward.
        self.cancel_requested = True

    @workflow.query
    def status(self) -> dict:
        return {
            "project_id": self.project_id,
            "phase": self.phase,
            "paused": self.paused,
            "cancel_requested": self.cancel_requested,
            "total_shots": self.total_shots,
            "completed_shot_ids": list(self.completed_shots),
            "in_flight_shot_id": self.in_flight_shot_id,
            "workflow_version": self.workflow_version,
        }

    @workflow.run
    async def run(self, request: ProjectOrchestrationRequest) -> dict:
        self.project_id = request.project_id
        self.total_shots = len(request.shot_operations)
        self.phase = "RUNNING"
        if workflow.patched("project-child-workflow-v1"):
            self.workflow_version = 2

        for shot_operation in request.shot_operations:
            await workflow.wait_condition(lambda: not self.paused or self.cancel_requested)
            if self.cancel_requested:
                self.phase = "CANCELLED"
                return self.status()
            self.in_flight_shot_id = shot_operation.shot_id
            result = await workflow.execute_child_workflow(
                ShotWorkflow.run,
                shot_operation,
                id=f"project:{request.project_id}:shot:{shot_operation.shot_id}",
                retry_policy=RetryPolicy(maximum_attempts=1),
            )
            self.completed_shots.append(result.shot_id)
            self.in_flight_shot_id = None

        self.phase = "COMPLETED"
        return self.status()
