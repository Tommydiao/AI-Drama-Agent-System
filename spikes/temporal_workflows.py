"""Workflow-only definitions kept free of filesystem and provider I/O."""
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy


@workflow.defn(name="p0-project-workflow")
class ProjectWorkflow:
    def __init__(self) -> None:
        self.paused = False

    @workflow.signal
    def pause(self) -> None:
        self.paused = True

    @workflow.signal
    def resume(self) -> None:
        self.paused = False

    @workflow.run
    async def run(self) -> list[str]:
        results = []
        for shot in ("shot-1", "shot-2", "shot-3"):
            await workflow.wait_condition(lambda: not self.paused)
            results.append(
                await workflow.execute_activity(
                    "simulated_paid_operation",
                    shot,
                    start_to_close_timeout=timedelta(seconds=90),
                    retry_policy=RetryPolicy(maximum_attempts=3, initial_interval=timedelta(seconds=1)),
                )
            )
        return results


@workflow.defn(name="p0-versioned-workflow")
class VersionWorkflowV1:
    def __init__(self) -> None:
        self.released = False

    @workflow.signal
    def release(self) -> None:
        self.released = True

    @workflow.run
    async def run(self) -> str:
        await workflow.wait_condition(lambda: self.released)
        return "v1-path"


@workflow.defn(name="p0-versioned-workflow")
class VersionWorkflowV2:
    def __init__(self) -> None:
        self.released = False

    @workflow.signal
    def release(self) -> None:
        self.released = True

    @workflow.run
    async def run(self) -> str:
        await workflow.wait_condition(lambda: self.released)
        return "v2-path" if workflow.patched("p0-versioned-v2-path") else "v1-path"
