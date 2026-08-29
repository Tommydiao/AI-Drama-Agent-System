"""Controller process that proves cross-process recovery and version evolution."""
from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from temporalio.client import Client
from temporalio.testing import WorkflowEnvironment

from temporal_process_workflows import DurabilityWorkflow, VersionWorkflowV1, VersionWorkflowV2


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "spikes"
DB = EVIDENCE / "temporal_cross_process.sqlite"
WORKER = Path(__file__).with_name("temporal_process_worker.py")


def setup_db() -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    if DB.exists():
        DB.unlink()
    with sqlite3.connect(DB) as conn:
        conn.executescript(
            """
            CREATE TABLE operations (
              operation_id TEXT PRIMARY KEY, shot TEXT UNIQUE NOT NULL, state TEXT NOT NULL,
              submissions INTEGER NOT NULL, completions INTEGER NOT NULL
            );
            CREATE TABLE events (
              ordinal INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, subject TEXT NOT NULL,
              attempt INTEGER NOT NULL, pid INTEGER NOT NULL
            );
            """
        )


def db_rows(query: str) -> list[dict[str, Any]]:
    with sqlite3.connect(DB) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute(query)]


async def wait_for(query: str, minimum: int = 1, timeout: float = 30.0) -> None:
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        if len(db_rows(query)) >= minimum:
            return
        await asyncio.sleep(0.1)
    raise AssertionError(f"Timed out waiting for {query}")


def start_worker(role: str, target: str) -> tuple[subprocess.Popen[bytes], Path]:
    ready = Path(tempfile.gettempdir()) / f"{role}-{time.time_ns()}.json"
    env = dict(os.environ, SPIKE_DB=str(DB), TEMPORAL_TARGET=target, WORKER_READY=str(ready), PYTHONUNBUFFERED="1")
    process = subprocess.Popen([sys.executable, str(WORKER), "--role", role], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return process, ready


async def wait_ready(process: subprocess.Popen[bytes], ready: Path) -> dict[str, Any]:
    for _ in range(100):
        if ready.exists():
            data = json.loads(ready.read_text(encoding="utf-8"))
            data["controller_child_pid"] = process.pid
            return data
        if process.poll() is not None:
            raise AssertionError(f"{process.args} exited early with {process.returncode}")
        await asyncio.sleep(0.1)
    raise AssertionError(f"worker {process.pid} did not become ready")


def force_kill(process: subprocess.Popen[bytes]) -> dict[str, Any]:
    process.kill()
    return {"pid": process.pid, "forced": True, "returncode": process.wait(timeout=10)}


def write(name: str, payload: dict[str, Any]) -> None:
    (EVIDENCE / name).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


async def run() -> None:
    setup_db()
    server_dir = Path(tempfile.gettempdir()) / "ai-drama-temporal-test-server"
    server_dir.mkdir(parents=True, exist_ok=True)
    workers: list[subprocess.Popen[bytes]] = []
    try:
        async with await WorkflowEnvironment.start_time_skipping(download_dest_dir=str(server_dir)) as env:
            client: Client = env.client
            target = client.service_client.config.target_host

            w1, ready1 = start_worker("durability-v1", target); workers.append(w1)
            w1_info = await wait_ready(w1, ready1)
            durability = await client.start_workflow(DurabilityWorkflow.run, id="spike-01-cross-process", task_queue="spike-01-cross-process")
            await wait_for("SELECT * FROM events WHERE kind = 'provider_accepted' AND subject = 'shot-2'")
            killed1 = force_kill(w1)
            w2, ready2 = start_worker("durability-v2", target); workers.append(w2)
            w2_info = await wait_ready(w2, ready2)
            assert w1_info["pid"] != w2_info["pid"]
            await wait_for("SELECT * FROM events WHERE kind = 'reconciled' AND subject = 'shot-2'")
            await durability.signal(DurabilityWorkflow.pause)
            await durability.signal(DurabilityWorkflow.open_third_gate)
            await asyncio.sleep(1.5)
            paused_shot3 = db_rows("SELECT * FROM events WHERE subject = 'shot-3'")
            assert not paused_shot3
            await durability.signal(DurabilityWorkflow.resume)
            durability_result = await asyncio.wait_for(durability.result(), timeout=30)
            operations = db_rows("SELECT * FROM operations ORDER BY shot")
            assert durability_result == ["completed", "reconciled", "completed"]
            assert len(operations) == 3 and all(row["submissions"] == 1 and row["completions"] == 1 for row in operations)
            write("spike_01_cross_process.json", {
                "result": "PASS", "workflow_id": "spike-01-cross-process",
                "worker_v1": w1_info, "worker_v1_forced_termination": killed1, "worker_v2": w2_info,
                "workflow_result": durability_result, "operations": operations, "events": db_rows("SELECT * FROM events ORDER BY ordinal"),
                "checks": {"same_workflow_id": True, "no_duplicate_operation_id": True, "pause_blocked_shot_3": True, "resume_completed": True},
            })

            v1, v1_ready = start_worker("version-v1", target); workers.append(v1)
            v1_info = await wait_ready(v1, v1_ready)
            old = await client.start_workflow(VersionWorkflowV1.run, "old", id="spike-02-old", task_queue="spike-02-cross-process")
            await wait_for("SELECT * FROM events WHERE kind = 'version_wait' AND subject = 'old'")
            killed_v1 = force_kill(v1)
            v2, v2_ready = start_worker("version-v2", target); workers.append(v2)
            v2_info = await wait_ready(v2, v2_ready)
            assert v1_info["pid"] != v2_info["pid"]
            await old.signal(VersionWorkflowV2.continue_workflow)
            old_result = await asyncio.wait_for(old.result(), timeout=30)
            new = await client.start_workflow(VersionWorkflowV2.run, "new", id="spike-02-new", task_queue="spike-02-cross-process")
            await wait_for("SELECT * FROM events WHERE kind = 'version_wait' AND subject = 'new'")
            await new.signal(VersionWorkflowV2.continue_workflow)
            new_result = await asyncio.wait_for(new.result(), timeout=30)
            assert old_result == "v1-compatible-path" and new_result == "v2-path"
            write("spike_02_cross_process.json", {
                "result": "PASS", "old_workflow_id": "spike-02-old", "new_workflow_id": "spike-02-new",
                "worker_v1": v1_info, "worker_v1_forced_termination": killed_v1, "worker_v2": v2_info,
                "old_workflow_result": old_result, "new_workflow_result": new_result,
                "checks": {"old_v1_compatible": True, "new_v2_path": True, "separate_worker_processes": True, "no_replay_failure": True},
            })
    finally:
        for worker in workers:
            if worker.poll() is None:
                worker.kill()


if __name__ == "__main__":
    asyncio.run(run())
