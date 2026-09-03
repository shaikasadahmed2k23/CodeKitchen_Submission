"""
Decouples "webhook received" from "review executed" so a burst of PRs
(e.g. a mass rebase across a monorepo) doesn't block the Cloud Run request
thread or hit Gemini rate limits synchronously. In production this enqueues
onto Cloud Tasks, which calls back into /internal/run-review with retry +
backoff built in. Locally it just schedules an asyncio task.
"""
import asyncio
import json
from typing import Awaitable, Callable

ReviewJob = dict


class TaskQueue:
    async def enqueue(self, job: ReviewJob) -> None:
        raise NotImplementedError


class InProcessQueue(TaskQueue):
    """Local/dev fallback -- runs the job on the event loop almost immediately."""

    def __init__(self, handler: Callable[[ReviewJob], Awaitable[None]]):
        self._handler = handler

    async def enqueue(self, job: ReviewJob) -> None:
        asyncio.create_task(self._handler(job))


class CloudTasksQueue(TaskQueue):
    """Production backend targeting a Cloud Run endpoint via Cloud Tasks."""

    def __init__(self, project_id: str, region: str, queue_name: str, target_url: str, service_account_email: str):
        from google.cloud import tasks_v2  # lazy import, optional dependency at runtime
        self._client = tasks_v2.CloudTasksAsyncClient()
        self._parent = self._client.queue_path(project_id, region, queue_name)
        self._target_url = target_url
        self._service_account_email = service_account_email

    async def enqueue(self, job: ReviewJob) -> None:
        from google.cloud import tasks_v2
        task = tasks_v2.Task(
            http_request=tasks_v2.HttpRequest(
                http_method=tasks_v2.HttpMethod.POST,
                url=self._target_url,
                headers={"Content-Type": "application/json"},
                body=json.dumps(job).encode(),
                oidc_token=tasks_v2.OidcToken(service_account_email=self._service_account_email),
            )
        )
        await self._client.create_task(parent=self._parent, task=task)
