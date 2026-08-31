"""Provider-neutral durable orchestration boundary."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from uuid import NAMESPACE_URL, uuid5


@dataclass(frozen=True)
class ShotOperation:
    shot_id: str
    operation_id: str


@dataclass(frozen=True)
class ProjectOrchestrationRequest:
    project_id: str
    shot_operations: list[ShotOperation]


def build_project_request(project_id: str, shot_ids: list[str]) -> ProjectOrchestrationRequest:
    return ProjectOrchestrationRequest(
        project_id=project_id,
        shot_operations=[
            ShotOperation(
                shot_id=shot_id,
                operation_id=str(uuid5(NAMESPACE_URL, f"ai-drama:{project_id}:{shot_id}:v1")),
            )
            for shot_id in shot_ids
        ],
    )


class OrchestrationPort(ABC):
    @abstractmethod
    async def start_project(self, request: ProjectOrchestrationRequest) -> str: ...

    @abstractmethod
    async def pause_project(self, project_id: str) -> None: ...

    @abstractmethod
    async def resume_project(self, project_id: str) -> None: ...

    @abstractmethod
    async def cancel_project(self, project_id: str) -> None: ...

    @abstractmethod
    async def project_status(self, project_id: str) -> dict: ...
