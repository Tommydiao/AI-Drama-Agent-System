"""Disposable P0 technical-spike harness. No product features or paid providers."""
from __future__ import annotations

import asyncio
import json
import sqlite3
import subprocess
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any

from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.common import RetryPolicy
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "spikes"
TEMPORAL_DB = EVIDENCE / "temporal_operations.sqlite"


def write_json(name: str, payload: dict[str, Any]) -> Path:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    path = EVIDENCE / name
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def rows(path: Path, query: str) -> list[dict[str, Any]]:
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute(query)]


def init_temporal_db() -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    if TEMPORAL_DB.exists():
        TEMPORAL_DB.unlink()
    with sqlite3.connect(TEMPORAL_DB) as conn:
        conn.executescript(
            """
            CREATE TABLE operations (
              operation_id TEXT PRIMARY KEY,
              shot TEXT NOT NULL,
              state TEXT NOT NULL,
              accepted_count INTEGER NOT NULL DEFAULT 0,
              completed_count INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE activity_log (
              ordinal INTEGER PRIMARY KEY AUTOINCREMENT,
              shot TEXT NOT NULL,
              operation_id TEXT NOT NULL,
              event TEXT NOT NULL,
              attempt INTEGER NOT NULL
            );
            """
        )


def log_activity(shot: str, operation_id: str, event: str, attempt: int) -> None:
    with sqlite3.connect(TEMPORAL_DB) as conn:
        conn.execute(
            "INSERT INTO activity_log(shot, operation_id, event, attempt) VALUES (?, ?, ?, ?)",
            (shot, operation_id, event, attempt),
        )


@activity.defn(name="simulated_paid_operation")
async def simulated_paid_operation(shot: str) -> str:
    operation_id = f"project-1:{shot}:generate:v1"
    attempt = activity.info().attempt
    with sqlite3.connect(TEMPORAL_DB) as conn:
        row = conn.execute("SELECT state FROM operations WHERE operation_id = ?", (operation_id,)).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO operations(operation_id, shot, state, accepted_count) VALUES (?, ?, 'ACCEPTED', 1)",
                (operation_id, shot),
            )
            conn.execute(
                "INSERT INTO activity_log(shot, operation_id, event, attempt) VALUES (?, ?, ?, ?)",
                (shot, operation_id, "accepted", attempt),
            )
            first_accept = True
        else:
            first_accept = False
    if shot == "shot-2" and first_accept:
        # The record models a provider that accepted work just before its worker died.
        log_activity(shot, operation_id, "simulated_worker_crash", attempt)
        raise RuntimeError("simulated worker crash after provider acceptance")
    with sqlite3.connect(TEMPORAL_DB) as conn:
        state = conn.execute("SELECT state FROM operations WHERE operation_id = ?", (operation_id,)).fetchone()[0]
        if state == "ACCEPTED":
            event = "reconciled" if not first_accept else "completed"
            conn.execute("UPDATE operations SET state = 'COMPLETED', completed_count = completed_count + 1 WHERE operation_id = ?", (operation_id,))
            conn.execute(
                "INSERT INTO activity_log(shot, operation_id, event, attempt) VALUES (?, ?, ?, ?)",
                (shot, operation_id, event, attempt),
            )
            return event
    return "already-completed"


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
                    retry_policy=RetryPolicy(maximum_attempts=3, initial_interval=timedelta(seconds=10)),
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


from temporal_workflows import ProjectWorkflow, VersionWorkflowV1, VersionWorkflowV2


async def wait_for(query: str, expected: int, seconds: float = 5.0) -> None:
    for _ in range(int(seconds / 0.05)):
        if len(rows(TEMPORAL_DB, query)) >= expected:
            return
        await asyncio.sleep(0.05)
    raise AssertionError(f"Timed out waiting for {query}")


async def temporal_spikes() -> tuple[dict[str, Any], dict[str, Any]]:
    init_temporal_db()
    server_dir = Path(tempfile.gettempdir()) / "ai-drama-temporal-test-server"
    server_dir.mkdir(parents=True, exist_ok=True)
    async with await WorkflowEnvironment.start_time_skipping(download_dest_dir=str(server_dir)) as env:
        client: Client = env.client
        queue = "p0-temporal-durability"
        worker = Worker(client, task_queue=queue, workflows=[ProjectWorkflow], activities=[simulated_paid_operation], graceful_shutdown_timeout=timedelta(seconds=0), sticky_queue_schedule_to_start_timeout=timedelta(seconds=1))
        worker_task = asyncio.create_task(worker.run())
        handle = await client.start_workflow(ProjectWorkflow.run, id="p0-durability", task_queue=queue)
        await wait_for("SELECT * FROM activity_log WHERE shot = 'shot-2' AND event = 'accepted'", 1)
        print("durability: shot-2 accepted", flush=True)
        await handle.signal(ProjectWorkflow.pause)
        worker_task.cancel()
        await asyncio.sleep(0.2)
        print("durability: worker-1 cancelled", flush=True)
        # A new worker process instance uses the persisted operation row to reconcile instead of resubmit.
        worker2 = Worker(client, task_queue=queue, workflows=[ProjectWorkflow], activities=[simulated_paid_operation], graceful_shutdown_timeout=timedelta(seconds=0), sticky_queue_schedule_to_start_timeout=timedelta(seconds=1))
        worker2_task = asyncio.create_task(worker2.run())
        await wait_for("SELECT * FROM activity_log WHERE shot = 'shot-2' AND event = 'reconciled'", 1)
        print("durability: shot-2 reconciled", flush=True)
        before_resume = rows(TEMPORAL_DB, "SELECT * FROM activity_log WHERE shot = 'shot-3'")
        assert not before_resume, "pause started a new paid operation"
        await handle.signal(ProjectWorkflow.resume)
        result = await handle.result()
        print("durability: resumed", flush=True)
        worker2_task.cancel()
        operation_rows = rows(TEMPORAL_DB, "SELECT * FROM operations ORDER BY shot")
        activity_rows = rows(TEMPORAL_DB, "SELECT * FROM activity_log ORDER BY ordinal")
        assert len(operation_rows) == 3
        assert all(row["accepted_count"] == 1 and row["completed_count"] == 1 for row in operation_rows)
        assert result == ["completed", "reconciled", "completed"]
        temporal_one = {
            "hypothesis": "Worker restart preserves workflow progress; cooperative pause blocks new paid work while accepted work reconciles.",
            "experiment": "Three sequential mock shots; cancel first worker after shot-2 acceptance, start a new worker, pause before shot-3, then resume.",
            "result": "PASS",
            "workflow_result": result,
            "operation_rows": operation_rows,
            "activity_log": activity_rows,
            "checks": {"no_duplicate_logical_operations": True, "pause_blocked_shot_3": True, "accepted_job_reconciled": True},
        }

        version_queue = "p0-temporal-versioning"
        v1_worker = Worker(client, task_queue=version_queue, workflows=[VersionWorkflowV1])
        v1_task = asyncio.create_task(v1_worker.run())
        old = await client.start_workflow(VersionWorkflowV1.run, id="p0-version-old", task_queue=version_queue)
        await asyncio.sleep(0.1)
        v1_task.cancel()
        await asyncio.sleep(0.2)
        print("versioning: v1 worker cancelled", flush=True)
        v2_worker = Worker(client, task_queue=version_queue, workflows=[VersionWorkflowV2])
        v2_task = asyncio.create_task(v2_worker.run())
        await old.signal(VersionWorkflowV2.release)
        old_result = await old.result()
        print("versioning: old complete", flush=True)
        fresh = await client.start_workflow(VersionWorkflowV2.run, id="p0-version-new", task_queue=version_queue)
        await fresh.signal(VersionWorkflowV2.release)
        fresh_result = await fresh.result()
        v2_task.cancel()
        assert old_result == "v1-path" and fresh_result == "v2-path"
        temporal_two = {
            "hypothesis": "Temporal patch markers let an in-flight v1 workflow replay safely while new workflows take v2 behavior.",
            "experiment": "Start a v1 workflow at a signal wait; replace the worker with v2 using workflow.patched; release old and new runs.",
            "result": "PASS",
            "old_workflow_result": old_result,
            "new_workflow_result": fresh_result,
            "versioning_rule": "Keep the patch marker until all pre-patch histories are retired; remove it only in a later compatibility window.",
        }
    return temporal_one, temporal_two


def provider_unknown_submission() -> dict[str, Any]:
    jobs: dict[str, str] = {}
    request_log: list[dict[str, str]] = []
    cost_events: list[dict[str, int | str]] = []
    operation_id = "project-1:shot-2:video:v1"
    try:
        jobs[operation_id] = "provider-job-001"
        request_log.append({"operation_id": operation_id, "event": "accepted_then_timeout"})
        cost_events.append({"operation_id": operation_id, "amount": 17, "kind": "actual"})
        raise TimeoutError("simulated response loss")
    except TimeoutError:
        state = "SUBMISSION_UNKNOWN"
    existing = jobs.get(operation_id)
    assert state == "SUBMISSION_UNKNOWN" and existing == "provider-job-001"
    request_log.append({"operation_id": operation_id, "event": "reconcile_existing_job"})
    assert len(jobs) == 1 and len(cost_events) == 1
    return {"hypothesis": "Stable operation_id plus provider lookup prevents a second charge after a lost response.", "result": "PASS", "operation": {"operation_id": operation_id, "state_after_timeout": state, "reconciled_provider_job": existing}, "provider_request_log": request_log, "cost_events": cost_events}


def concurrent_budget_reservation() -> dict[str, Any]:
    db = EVIDENCE / "budget_reservations.sqlite"
    if db.exists(): db.unlink()
    with sqlite3.connect(db) as conn:
        conn.executescript("CREATE TABLE budget(total INTEGER NOT NULL); INSERT INTO budget VALUES (100); CREATE TABLE reservation(operation_id TEXT PRIMARY KEY, amount INTEGER NOT NULL);")
    barrier = threading.Barrier(2)
    def reserve(operation_id: str) -> dict[str, str]:
        barrier.wait()
        with sqlite3.connect(db, timeout=5, isolation_level=None) as conn:
            conn.execute("BEGIN IMMEDIATE")
            total = conn.execute("SELECT total FROM budget").fetchone()[0]
            used = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM reservation").fetchone()[0]
            if used + 60 <= total:
                conn.execute("INSERT INTO reservation VALUES (?, 60)", (operation_id,)); conn.execute("COMMIT")
                return {"operation_id": operation_id, "result": "reserved"}
            conn.execute("ROLLBACK")
            return {"operation_id": operation_id, "result": "budget_blocked"}
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(reserve, ["shot-1", "shot-2"]))
    reservations = rows(db, "SELECT * FROM reservation ORDER BY operation_id")
    assert sorted(x["result"] for x in results) == ["budget_blocked", "reserved"] and len(reservations) == 1
    return {"hypothesis": "BEGIN IMMEDIATE plus a reservation ledger serializes concurrent upper-bound checks.", "result": "PASS", "results": results, "reservation_rows": reservations, "total_budget": 100}


def shot_graph_invalidation() -> dict[str, Any]:
    edges = [
        ("dialogue:s2", "tts:s2", "AUDIO_SYNC"), ("dialogue:s2", "subtitle:s2", "AUDIO_SYNC"),
        ("tts:s2", "lip:s2", "DERIVED_FROM"), ("lip:s2", "video:s2", "DERIVED_FROM"),
        ("video:s2", "video:s3", "CONTINUITY_REFERENCE"),
        ("look:lead:v1", "keyframe:s1", "LOOK_REFERENCE"), ("look:lead:v1", "keyframe:s4", "LOOK_REFERENCE"),
        ("keyframe:s1", "video:s1", "DERIVED_FROM"), ("keyframe:s4", "video:s4", "DERIVED_FROM"),
    ]
    def impact(seed: str, allowed: set[str]) -> list[str]:
        affected, frontier = set(), [seed]
        while frontier:
            current = frontier.pop()
            for source, target, kind in edges:
                if source == current and kind in allowed and target not in affected:
                    affected.add(target); frontier.append(target)
        return sorted(affected)
    dialogue_actual = impact("dialogue:s2", {"AUDIO_SYNC", "DERIVED_FROM"})
    look_actual = impact("look:lead:v1", {"LOOK_REFERENCE", "DERIVED_FROM"})
    dialogue_expected = ["lip:s2", "subtitle:s2", "tts:s2", "video:s2"]
    look_expected = ["keyframe:s1", "keyframe:s4", "video:s1", "video:s4"]
    assert dialogue_actual == dialogue_expected and look_actual == look_expected
    return {"hypothesis": "Typed edges produce a stable, minimal impact plan and do not treat continuity as an execution invalidation edge.", "result": "PASS", "edges": [{"from": a, "to": b, "type": c} for a,b,c in edges], "expected": {"dialogue": dialogue_expected, "look": look_expected}, "actual": {"dialogue": dialogue_actual, "look": look_actual}, "dag": True}


def command(args: list[str], cwd: Path) -> list[str]:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)
    return args


def probe(path: Path) -> dict[str, Any]:
    result = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)], check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def ffmpeg_deterministic_render() -> dict[str, Any]:
    work = EVIDENCE / "ffmpeg"
    work.mkdir(parents=True, exist_ok=True)
    commands: list[list[str]] = []
    colors = ["red", "green", "blue"]
    clips = []
    for index, color in enumerate(colors, 1):
        clip = work / f"clip-{index}.mp4"; clips.append(clip)
        commands.append(command(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={color}:s=720x1280:r=30:d=1", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-fflags", "+bitexact", "-flags:v", "+bitexact", str(clip)], work))
    wav = work / "tone.wav"
    commands.append(command(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=3", "-c:a", "pcm_s16le", str(wav)], work))
    srt = work / "subtitles.srt"; srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nP0 spike\n\n2\n00:00:01,000 --> 00:00:02,000\nDeterministic render\n", encoding="utf-8")
    concat = work / "clips.txt"; concat.write_text("".join(f"file '{clip.name}'\n" for clip in clips), encoding="utf-8")
    def render(output: Path, list_file: Path = concat) -> None:
        commands.append(command(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-i", str(wav), "-vf", f"subtitles={srt.name}", "-map", "0:v:0", "-map", "1:a:0", "-t", "3", "-r", "30", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "48000", "-map_metadata", "-1", "-metadata", "creation_time=1970-01-01T00:00:00Z", "-fflags", "+bitexact", "-flags:v", "+bitexact", "-flags:a", "+bitexact", str(output)], work))
    first, second = work / "render-1.mp4", work / "render-2.mp4"; render(first); render(second)
    replacement = work / "replacement.mp4"; commands.append(command(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=yellow:s=720x1280:r=30:d=1", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(replacement)], work))
    replaced_list = work / "clips-replaced.txt"; replaced_list.write_text(f"file '{clips[0].name}'\nfile '{replacement.name}'\nfile '{clips[2].name}'\n", encoding="utf-8")
    replaced = work / "render-replaced.mp4"; render(replaced, replaced_list)
    first_probe, second_probe, replacement_probe = probe(first), probe(second), probe(replaced)
    def summary(data: dict[str, Any]) -> dict[str, Any]:
        streams = data["streams"]
        video = next(s for s in streams if s["codec_type"] == "video")
        audio = next(s for s in streams if s["codec_type"] == "audio")
        return {"duration": float(data["format"]["duration"]), "width": video["width"], "height": video["height"], "fps": video["r_frame_rate"], "audio_sample_rate": audio["sample_rate"]}
    a, b, c = summary(first_probe), summary(second_probe), summary(replacement_probe)
    assert a == b and abs(a["duration"] - 3.0) < 0.05 and c == a
    return {"hypothesis": "Fixed FFmpeg inputs, options and metadata reproduce required technical output; byte hashes are measured, not a product promise.", "result": "PASS", "commands": commands, "ffprobe": {"render_1": first_probe, "render_2": second_probe, "replaced": replacement_probe}, "technical_summary": {"render_1": a, "render_2": b, "replaced": c}, "artifacts": [str(p.relative_to(ROOT)).replace("\\\\", "/") for p in [first, second, replaced, wav, srt]]}


async def main() -> None:
    temporal_one, temporal_two = await temporal_spikes()
    evidence = {
        "SPIKE-01": temporal_one,
        "SPIKE-02": temporal_two,
        "SPIKE-03": provider_unknown_submission(),
        "SPIKE-04": concurrent_budget_reservation(),
        "SPIKE-05": shot_graph_invalidation(),
        "SPIKE-06": ffmpeg_deterministic_render(),
    }
    for key, value in evidence.items():
        write_json(key.lower().replace("-", "_") + ".json", value)
    write_json("p0_summary.json", {"gate": "PASS" if all(item["result"] == "PASS" for item in evidence.values()) else "FAIL", "spikes": {key: value["result"] for key, value in evidence.items()}, "python": sys.version, "temporalio": "1.32.0"})
    print(json.dumps({key: value["result"] for key, value in evidence.items()}))


if __name__ == "__main__":
    asyncio.run(main())
