"""Temporal Activities call application services; this default is a no-charge harness activity."""
from __future__ import annotations

from temporalio import activity

from .orchestration import ShotOperation


@activity.defn(name="execute-shot-operation")
async def execute_shot_operation(request: ShotOperation) -> dict[str, str]:
    # Real provider submission is wired here only after budget, rights, and Provider gates pass.
    activity.heartbeat({"shot_id": request.shot_id, "operation_id": request.operation_id})
    return {
        "shot_id": request.shot_id,
        "operation_id": request.operation_id,
        "state": "SUCCEEDED",
    }
