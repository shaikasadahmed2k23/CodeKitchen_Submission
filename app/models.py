from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field

Severity = Literal["critical", "major", "minor", "nit"]
Category = Literal["bug", "security", "performance", "style", "maintainability"]
TrustLevel = Literal["new", "building", "trusted", "needs_scrutiny"]


class ReviewComment(BaseModel):
    file: str
    line: int | None = None
    severity: Severity
    category: Category
    message: str


class ReviewResult(BaseModel):
    repo: str
    pr_number: int
    author: str
    quality_score: int = Field(ge=0, le=100)  # final score, after trust adjustment
    raw_score: int = Field(ge=0, le=100, default=0)  # Gemini's score before adjustment
    trust_level: TrustLevel = "new"
    trust_adjustment: int = 0  # +5 / -5 / 0, see app/trust.py
    summary: str
    comments: list[ReviewComment] = []
    files_reviewed: int = 0
    reviewed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    model: str = ""

    def to_pr_comment_markdown(self) -> str:
        lines = [
            f"### 🤖 24/7 Code Reviewer — Quality Score: **{self.quality_score}/100**",
        ]
        if self.trust_adjustment != 0:
            sign = "+" if self.trust_adjustment > 0 else ""
            lines.append(
                f"*Raw score {self.raw_score}/100, {sign}{self.trust_adjustment} for developer trust "
                f"level `{self.trust_level}` (based on review history in this repo).*"
            )
        else:
            lines.append(f"*Developer trust level: `{self.trust_level}`.*")
        lines += ["", self.summary, ""]
        if self.comments:
            lines.append("| Severity | Category | File | Line | Comment |")
            lines.append("|---|---|---|---|---|")
            for c in sorted(self.comments, key=lambda x: _severity_rank(x.severity)):
                lines.append(
                    f"| {c.severity} | {c.category} | `{c.file}` | {c.line or '-'} | {c.message} |"
                )
        else:
            lines.append("No issues found. Clean diff. ✅")
        return "\n".join(lines)


def _severity_rank(sev: Severity) -> int:
    return {"critical": 0, "major": 1, "minor": 2, "nit": 3}[sev]


class DeveloperTrend(BaseModel):
    developer: str
    repo: str
    review_count: int
    average_score: float
    trust_level: TrustLevel = "new"
    last_reviewed_at: datetime | None = None
