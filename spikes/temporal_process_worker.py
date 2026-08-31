"""One independently launched worker OS process for a P0 Temporal spike."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sqlite3
from datetime import timedelta
from pathlib import Path

from temporalio import activity
from temporalio.client import Client
from temporalio.worker import Worker

from temporal_process_workflows import DurabilityWorkflow, VersionWorkflowV1, VersionWorkflowV2


DB = Path(os.environ["SPIKE_DB"])


def event(kind: str, subject: str, attempt: int = 0) -> None:
    with sqlite3.connect(DB) as conn:
        conn.execute("INSERT INTO events(kind, subject, attempt, pid) VALUES (?, ?, ?, ?)", (kind, subject, attempt, os.getpid()))


@activity.defn(name="durability_paid_operation")
async def durability_paid_operation(shot: str) -> str:
    operation_id = f"project-1:{shot}:generate:v1"
    attempt = activity.info().attempt
    with sqlite3.connect(DB) as conn:
        row = conn.execute("SELECT state FROM operations WHERE operation_id = ?", (operation_id,)).fetchone()
        if row is None:
            conn.execute("INSERT INTO operations(operation_id, shot, state, submissions, completions) VALUES (?, ?, 'ACCEPTED', 1, 0)", (operation_id, shot))
            conn.execute("INSERT INTO events(kind, subject, attempt, pid) VALUES ('provider_accepted', ?, ?, ?)", (shot, attempt, os.getpid()))
            first_accept = True
        else:
            first_accept = False
    activity.heartbeat({"operation_id": operation_id, "state": "ACCEPTED"})
    if shot == "shot-2" and first_accept:
        # Controller force-kills this worker process after this durable acceptance record.
        await asyncio.sleep(300)
    with sqlite3.connect(DB) as conn:
        state = conn.execute("SELECT state FROM operations WHERE operation_id = ?", (operation_id,)).fetchone()[0]
        if state == "ACCEPTED":
            result = "reconciled" if not first_accept else "completed"
            conn.execute("UPDATE operations SET state = 'COMPLETED', completions = completions + 1 WHERE operation_id = ?", (operation_id,))
            conn.execute("INSERT INTO events(kind, subject, attempt, pid) VALUES (?, ?, ?, ?)", (result, shot, attempt, os.getpid()))
            return result
    return "already-completed"


@activity.defn(name="record_version_wait")
async def record_version_wait(label: str) -> None:
    event("version_wait", label, activity.info().attempt)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", required=True, choices=("durability-v1", "durability-v2", "version-v1", "version-v2"))
    args = parser.parse_args()
    target = os.environ["TEMPORAL_TARGET"]
    ready = Path(os.environ["WORKER_READY"])
    client = await Client.connect(target)
    if args.role.startswith("durability"):
        workflows = [DurabilityWorkflow]
        queue = "spike-01-cross-process"
    elif args.role == "version-v1":
        workflows = [VersionWorkflowV1]
        queue = "spike-02-cross-process"
    else:
        workflows = [VersionWorkflowV2]
        queue = "spike-02-cross-process"
    async with Worker(
        client,
        task_queue=queue,
        workflows=workflows,
        activities=[durability_paid_operation, record_version_wait],
        sticky_queue_schedule_to_start_timeout=timedelta(seconds=1),
    ):
        ready.write_text(json.dumps({"pid": os.getpid(), "role": args.role, "queue": queue}), encoding="utf-8")
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
