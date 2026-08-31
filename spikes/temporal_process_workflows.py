"""Deterministic workflow definitions for the cross-process Temporal spikes."""
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy


@workflow.defn(name="spike-01-project")
class DurabilityWorkflow:
    def __init__(self) -> None:
        self.paused = False
        self.third_gate_open = False

    @workflow.signal
    def pause(self) -> None:
        self.paused = True

    @workflow.signal
    def resume(self) -> None:
        self.paused = False

    @workflow.signal
    def open_third_gate(self) -> None:
        self.third_gate_open = True

    @workflow.run
    async def run(self) -> list[str]:
        results = []
        for shot in ("shot-1", "shot-2"):
            results.append(
                await workflow.execute_activity(
                    "durability_paid_operation",
                    shot,
                    start_to_close_timeout=timedelta(seconds=120),
                    heartbeat_timeout=timedelta(seconds=2),
                    retry_policy=RetryPolicy(maximum_attempts=3, initial_interval=timedelta(seconds=1)),
                )
            )
        await workflow.wait_condition(lambda: self.third_gate_open)
        await workflow.wait_condition(lambda: not self.paused)
        results.append(
            await workflow.execute_activity(
                "durability_paid_operation",
                "shot-3",
                start_to_close_timeout=timedelta(seconds=120),
                heartbeat_timeout=timedelta(seconds=2),
                retry_policy=RetryPolicy(maximum_attempts=3, initial_interval=timedelta(seconds=1)),
            )
        )
        return results


@workflow.defn(name="spike-02-versioned")
class VersionWorkflowV1:
    def __init__(self) -> None:
        self.release = False

    @workflow.signal
    def continue_workflow(self) -> None:
        self.release = True

    @workflow.run
    async def run(self, label: str) -> str:
        await workflow.execute_activity(
            "record_version_wait",
            label,
            start_to_close_timeout=timedelta(seconds=30),
        )
        await workflow.wait_condition(lambda: self.release)
        return "v1-compatible-path"


@workflow.defn(name="spike-02-versioned")
class VersionWorkflowV2:
    def __init__(self) -> None:
        self.release = False

    @workflow.signal
    def continue_workflow(self) -> None:
        self.release = True

    @workflow.run
    async def run(self, label: str) -> str:
        # This marker must be evaluated before the persisted wait so old histories replay false.
        use_v2_path = workflow.patched("spike-02-v2-path")
        await workflow.execute_activity(
            "record_version_wait",
            label,
            start_to_close_timeout=timedelta(seconds=30),
        )
        await workflow.wait_condition(lambda: self.release)
        return "v2-path" if use_v2_path else "v1-compatible-path"
