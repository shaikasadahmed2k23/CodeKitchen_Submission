import httpx


class GitHubClient:
    """
    Thin wrapper around the GitHub REST API. Uses httpx directly (rather than
    PyGithub) for the two calls we actually need, so it's trivial to mock in
    tests without pulling in a full client library's internals.
    """

    def __init__(self, token: str, base_url: str = "https://api.github.com"):
        self._base_url = base_url
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def fetch_pr_diff(self, repo_full_name: str, pr_number: int) -> str:
        url = f"{self._base_url}/repos/{repo_full_name}/pulls/{pr_number}"
        headers = {**self._headers, "Accept": "application/vnd.github.v3.diff"}
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.text

    async def fetch_pr_files(self, repo_full_name: str, pr_number: int) -> list[str]:
        url = f"{self._base_url}/repos/{repo_full_name}/pulls/{pr_number}/files"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=self._headers, params={"per_page": 100})
            resp.raise_for_status()
            return [f["filename"] for f in resp.json()]

    async def post_pr_comment(self, repo_full_name: str, pr_number: int, body: str) -> None:
        url = f"{self._base_url}/repos/{repo_full_name}/issues/{pr_number}/comments"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, headers=self._headers, json={"body": body})
            resp.raise_for_status()
