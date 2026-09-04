"""
Wraps Gemini for structured, multi-language code review. Asks for strict
JSON output so we can parse it into ReviewResult without any regex-scraping
of free text.
"""
import json
import re

import google.generativeai as genai

from app.models import ReviewComment, ReviewResult

_SYSTEM_PROMPT = """You are a senior staff software engineer performing a code review \
on a pull request diff. Review for: bugs, security vulnerabilities, performance issues, \
style violations, and maintainability concerns. Support any language present in the diff.

Respond with ONLY valid JSON, no markdown fences, no commentary, matching exactly:
{
  "quality_score": <int 0-100>,
  "summary": "<2-3 sentence overview of the change and its risk level>",
  "comments": [
    {"file": "<path>", "line": <int or null>, "severity": "critical|major|minor|nit",
     "category": "bug|security|performance|style|maintainability", "message": "<specific, actionable>"}
  ]
}

Score 90-100 for clean, well-tested, idiomatic code. Score below 50 if there are \
critical bugs or security issues. Be specific -- cite the actual file and reasoning, \
never generic advice."""


class GeminiReviewer:
    def __init__(self, api_key: str, model_name: str = "gemini-3.5-flash"):
        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=_SYSTEM_PROMPT,
        )
        self.model_name = model_name

    def review(self, *, repo: str, pr_number: int, author: str, diff_text: str, files: list[str]) -> ReviewResult:
        prompt = (
            f"Repository: {repo}\nPR #{pr_number} by {author}\n"
            f"Files changed ({len(files)}): {', '.join(files[:50])}\n\n"
            f"Diff:\n{diff_text}"
        )
        raw = self._model.generate_content(prompt).text
        data = _parse_json_response(raw)

        comments = [ReviewComment(**c) for c in data.get("comments", [])]
        return ReviewResult(
            repo=repo,
            pr_number=pr_number,
            author=author,
            quality_score=int(data["quality_score"]),
            summary=data["summary"],
            comments=comments,
            files_reviewed=len(files),
            model=self.model_name,
        )


def _parse_json_response(raw: str) -> dict:
    """Gemini occasionally wraps JSON in ```json fences despite instructions -- strip them."""
    cleaned = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    return json.loads(cleaned)
