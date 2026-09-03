import pytest

from app.models import ReviewResult
from app.store import InMemoryReviewStore


def _result(score: int, pr: int) -> ReviewResult:
    return ReviewResult(repo="asad/repo", pr_number=pr, author="asad",
                         quality_score=score, summary="ok", files_reviewed=1)


@pytest.mark.asyncio
async def test_save_and_history():
    store = InMemoryReviewStore()
    await store.save(_result(80, 1))
    await store.save(_result(90, 2))

    history = await store.history_for_developer("asad/repo", "asad")
    assert len(history) == 2
    assert history[0].pr_number == 2  # most recent first


@pytest.mark.asyncio
async def test_trend_computation():
    store = InMemoryReviewStore()
    await store.save(_result(80, 1))
    await store.save(_result(90, 2))

    trend = await store.trend_for_developer("asad/repo", "asad")
    assert trend.review_count == 2
    assert trend.average_score == 85.0


@pytest.mark.asyncio
async def test_trend_with_no_history():
    store = InMemoryReviewStore()
    trend = await store.trend_for_developer("asad/repo", "nobody")
    assert trend.review_count == 0
    assert trend.average_score == 0.0


@pytest.mark.asyncio
async def test_all_recent_respects_limit():
    store = InMemoryReviewStore()
    for i in range(5):
        await store.save(_result(70, i))
    recent = await store.all_recent(limit=3)
    assert len(recent) == 3
