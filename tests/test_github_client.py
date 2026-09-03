import pytest
import httpx

from app.github_client import GitHubClient


@pytest.mark.asyncio
async def test_fetch_pr_diff(monkeypatch):
    async def mock_get(self, url, headers=None, params=None):
        return httpx.Response(200, text="diff --git a/x b/x", request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    client = GitHubClient(token="fake-token")
    diff = await client.fetch_pr_diff("asad/repo", 1)
    assert "diff --git" in diff


@pytest.mark.asyncio
async def test_fetch_pr_files(monkeypatch):
    async def mock_get(self, url, headers=None, params=None):
        return httpx.Response(200, json=[{"filename": "app/main.py"}, {"filename": "README.md"}],
                               request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    client = GitHubClient(token="fake-token")
    files = await client.fetch_pr_files("asad/repo", 1)
    assert files == ["app/main.py", "README.md"]


@pytest.mark.asyncio
async def test_post_pr_comment(monkeypatch):
    calls = {}

    async def mock_post(self, url, headers=None, json=None):
        calls["url"] = url
        calls["json"] = json
        return httpx.Response(201, json={}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    client = GitHubClient(token="fake-token")
    await client.post_pr_comment("asad/repo", 1, "Great PR!")
    assert calls["json"] == {"body": "Great PR!"}
    assert "issues/1/comments" in calls["url"]
