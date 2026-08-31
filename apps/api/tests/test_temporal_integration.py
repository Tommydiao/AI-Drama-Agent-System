from __future__ import annotations

import asyncio
from pathlib import Path
import tempfile
import time
from uuid import uuid4

from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Replayer, Worker

from app.orchestration import ShotOperation, build_project_request
from app.temporal_adapter import TemporalOrchestrationAdapter, project_workflow_id
from app.temporal_workflows import ProjectWorkflow, ShotWorkflow


def test_temporal_pause_resume_cancel_children_history_and_replay():
    asyncio.run(_run_temporal_gate())


async def _run_temporal_gate() -> None:
    started: asyncio.Queue[str] = asyncio.Queue()
    releases: dict[str, asyncio.Event] = {}

    @activity.defn(name="execute-shot-operation")
    async def controlled_shot(request: ShotOperation) -> dict[str, str]:
        releases.setdefault(request.shot_id, asyncio.Event())
        await started.put(request.shot_id)
        await releases[request.shot_id].wait()
        return {"shot_id": request.shot_id, "operation_id": request.operation_id, "state": "SUCCEEDED"}

    server_dir = Path(tempfile.gettempdir()) / "ai-drama-temporal-test-server"
    server_dir.mkdir(parents=True, exist_ok=True)
    async with await WorkflowEnvironment.start_time_skipping(download_dest_dir=str(server_dir)) as environment:
        queue = f"test-{uuid4()}"
        adapter = TemporalOrchestrationAdapter(environment.client, task_queue=queue)
        async with Worker(
            environment.client,
            task_queue=queue,
            workflows=[ProjectWorkflow, ShotWorkflow],
            activities=[controlled_shot],
        ):
            paused_project = f"pause-{uuid4()}"
            await adapter.start_project(build_project_request(paused_project, ["shot-1", "shot-2", "shot-3"]))
            assert await asyncio.wait_for(started.get(), timeout=10) == "shot-1"
            await adapter.pause_project(paused_project)
            releases["shot-1"].set()
            await asyncio.sleep(0.25)
            status = await adapter.project_status(paused_project)
            assert status["paused"] is True
            assert status["completed_shot_ids"] == ["shot-1"]
            assert started.empty()
            await adapter.resume_project(paused_project)
            assert await asyncio.wait_for(started.get(), timeout=10) == "shot-2"
            releases["shot-2"].set()
            assert await asyncio.wait_for(started.get(), timeout=10) == "shot-3"
            releases["shot-3"].set()
            paused_result = await environment.client.get_workflow_handle(
                project_workflow_id(paused_project)
            ).result()
            assert paused_result["phase"] == "COMPLETED"

            cancelled_project = f"cancel-{uuid4()}"
            await adapter.start_project(build_project_request(cancelled_project, ["cancel-1", "cancel-2"]))
            assert await asyncio.wait_for(started.get(), timeout=10) == "cancel-1"
            await adapter.cancel_project(cancelled_project)
            releases["cancel-1"].set()
            cancelled_result = await environment.client.get_workflow_handle(
                project_workflow_id(cancelled_project)
            ).result()
            assert cancelled_result["phase"] == "CANCELLED"
            assert cancelled_result["completed_shot_ids"] == ["cancel-1"]
            assert started.empty()

            benchmark_project = f"benchmark-{uuid4()}"
            benchmark_request = build_project_request(
                benchmark_project, [f"shot-{index:02d}" for index in range(24)]
            )
            for shot_operation in benchmark_request.shot_operations:
                releases[shot_operation.shot_id] = asyncio.Event()
                releases[shot_operation.shot_id].set()
            await adapter.start_project(benchmark_request)
            benchmark_handle = environment.client.get_workflow_handle(project_workflow_id(benchmark_project))
            benchmark_result = await benchmark_handle.result()
            assert benchmark_result["phase"] == "COMPLETED"
            history = await benchmark_handle.fetch_history()
            assert len(history.events) < 10_000
            replay_started = time.monotonic()
            await Replayer(workflows=[ProjectWorkflow, ShotWorkflow]).replay_workflow(history)
            replay_seconds = time.monotonic() - replay_started
            assert replay_seconds < 5.0
            print(f"temporal_benchmark_events={len(history.events)} replay_seconds={replay_seconds:.3f}")
