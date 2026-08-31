"""Long-lived Temporal worker entrypoint."""
from __future__ import annotations

import asyncio
import os

from temporalio.client import Client, TLSConfig
from temporalio.worker import Worker

from .temporal_activities import execute_shot_operation
from .temporal_workflows import ProjectWorkflow, ShotWorkflow


async def run_worker() -> None:
    target = os.getenv("TEMPORAL_TARGET", "127.0.0.1:7233")
    namespace = os.getenv("TEMPORAL_NAMESPACE", "default")
    task_queue = os.getenv("TEMPORAL_TASK_QUEUE", "ai-drama-projects")
    tls = TLSConfig() if os.getenv("TEMPORAL_TLS", "false").lower() == "true" else False
    client = await Client.connect(target, namespace=namespace, tls=tls)
    worker = Worker(
        client,
        task_queue=task_queue,
        workflows=[ProjectWorkflow, ShotWorkflow],
        activities=[execute_shot_operation],
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(run_worker())
