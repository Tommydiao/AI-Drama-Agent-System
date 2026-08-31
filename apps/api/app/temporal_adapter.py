"""Temporal implementation of OrchestrationPort."""
from __future__ import annotations

from temporalio.client import Client
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy

from .orchestration import OrchestrationPort, ProjectOrchestrationRequest
from .temporal_workflows import ProjectWorkflow


def project_workflow_id(project_id: str) -> str:
    return f"project:{project_id}"


class TemporalOrchestrationAdapter(OrchestrationPort):
    def __init__(self, client: Client, task_queue: str = "ai-drama-projects") -> None:
        self.client = client
        self.task_queue = task_queue

    async def start_project(self, request: ProjectOrchestrationRequest) -> str:
        workflow_id = project_workflow_id(request.project_id)
        await self.client.start_workflow(
            ProjectWorkflow.run,
            request,
            id=workflow_id,
            task_queue=self.task_queue,
            id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
            id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
        )
        return workflow_id

    async def pause_project(self, project_id: str) -> None:
        await self.client.get_workflow_handle(project_workflow_id(project_id)).signal("pause")

    async def resume_project(self, project_id: str) -> None:
        await self.client.get_workflow_handle(project_workflow_id(project_id)).signal("resume")

    async def cancel_project(self, project_id: str) -> None:
        await self.client.get_workflow_handle(project_workflow_id(project_id)).signal("request_cancel")

    async def project_status(self, project_id: str) -> dict:
        return await self.client.get_workflow_handle(project_workflow_id(project_id)).query("status")
