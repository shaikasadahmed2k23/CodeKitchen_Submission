"""
Review history persistence. Firestore is the production backend (schemaless,
low-latency reads -- fits sparse, evolving review metadata and cheap
per-developer/per-repo trend queries far better than a rigid relational
schema for a moderate-write, dashboard-read workload). An in-memory store
implements the same interface for local dev and unit tests, so the rest of
the app never needs to know which one it's talking to.
"""
from abc import ABC, abstractmethod
from collections import defaultdict

from app.models import DeveloperTrend, ReviewResult


class ReviewStore(ABC):
    @abstractmethod
    async def save(self, result: ReviewResult) -> None: ...

    @abstractmethod
    async def history_for_developer(self, repo: str, developer: str, limit: int = 20) -> list[ReviewResult]: ...

    @abstractmethod
    async def trend_for_developer(self, repo: str, developer: str) -> DeveloperTrend: ...

    @abstractmethod
    async def all_recent(self, limit: int = 50) -> list[ReviewResult]: ...


class InMemoryReviewStore(ReviewStore):
    """Used for local `uvicorn` runs without GCP creds, and in unit tests."""

    def __init__(self):
        self._by_dev: dict[tuple[str, str], list[ReviewResult]] = defaultdict(list)
        self._all: list[ReviewResult] = []

    async def save(self, result: ReviewResult) -> None:
        key = (result.repo, result.author)
        self._by_dev[key].append(result)
        self._all.append(result)

    async def history_for_developer(self, repo: str, developer: str, limit: int = 20) -> list[ReviewResult]:
        items = self._by_dev.get((repo, developer), [])
        return sorted(items, key=lambda r: r.reviewed_at, reverse=True)[:limit]

    async def trend_for_developer(self, repo: str, developer: str) -> DeveloperTrend:
        items = self._by_dev.get((repo, developer), [])
        if not items:
            return DeveloperTrend(developer=developer, repo=repo, review_count=0, average_score=0.0)
        avg = sum(r.quality_score for r in items) / len(items)
        last = max(r.reviewed_at for r in items)
        return DeveloperTrend(developer=developer, repo=repo, review_count=len(items),
                               average_score=round(avg, 1), last_reviewed_at=last)

    async def all_recent(self, limit: int = 50) -> list[ReviewResult]:
        return sorted(self._all, key=lambda r: r.reviewed_at, reverse=True)[:limit]


class FirestoreReviewStore(ReviewStore):
    """Production backend. Lazily imports google.cloud.firestore so local
    dev/tests never need the dependency wired up with real credentials."""

    def __init__(self, project_id: str, collection: str):
        from google.cloud import firestore  # local import: keeps this optional at runtime
        self._db = firestore.AsyncClient(project=project_id)
        self._collection = collection

    async def save(self, result: ReviewResult) -> None:
        doc_id = f"{result.repo.replace('/', '_')}_{result.pr_number}_{int(result.reviewed_at.timestamp())}"
        await self._db.collection(self._collection).document(doc_id).set(result.model_dump(mode="json"))

    async def history_for_developer(self, repo: str, developer: str, limit: int = 20) -> list[ReviewResult]:
        query = (
            self._db.collection(self._collection)
            .where("repo", "==", repo)
            .where("author", "==", developer)
            .order_by("reviewed_at", direction="DESCENDING")
            .limit(limit)
        )
        docs = [d async for d in query.stream()]
        return [ReviewResult(**d.to_dict()) for d in docs]

    async def trend_for_developer(self, repo: str, developer: str) -> DeveloperTrend:
        items = await self.history_for_developer(repo, developer, limit=1000)
        if not items:
            return DeveloperTrend(developer=developer, repo=repo, review_count=0, average_score=0.0)
        avg = sum(r.quality_score for r in items) / len(items)
        return DeveloperTrend(developer=developer, repo=repo, review_count=len(items),
                               average_score=round(avg, 1), last_reviewed_at=items[0].reviewed_at)

    async def all_recent(self, limit: int = 50) -> list[ReviewResult]:
        query = self._db.collection(self._collection).order_by("reviewed_at", direction="DESCENDING").limit(limit)
        docs = [d async for d in query.stream()]
        return [ReviewResult(**d.to_dict()) for d in docs]
