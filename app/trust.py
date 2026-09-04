"""
Developer trust profile: the "Historical Learning" requirement for this
track. A developer's track record in a repo genuinely shifts how their next
PR is scored -- it isn't just logged and ignored.

Adapted from a pattern proven out in a prior project (MergeGuard), with the
same safety rule carried over deliberately: trust can nudge a score by a
few points, but it can never launder a real problem. A critical-severity
finding in the CURRENT diff always blocks any positive adjustment,
regardless of how clean the developer's history is -- a good track record
buys benefit of the doubt on borderline style/quality calls, never on a
fresh security or correctness issue.
"""
from app.models import DeveloperTrend, ReviewComment, TrustLevel

TRUSTED_MIN_REVIEWS = 5
TRUSTED_MIN_AVG_SCORE = 80.0
NEEDS_SCRUTINY_MIN_REVIEWS = 3
NEEDS_SCRUTINY_MAX_AVG_SCORE = 50.0
TRUST_ADJUSTMENT = 5


def classify_trust_level(trend: DeveloperTrend) -> TrustLevel:
    if trend.review_count == 0:
        return "new"
    if trend.review_count >= NEEDS_SCRUTINY_MIN_REVIEWS and trend.average_score < NEEDS_SCRUTINY_MAX_AVG_SCORE:
        return "needs_scrutiny"
    if trend.review_count >= TRUSTED_MIN_REVIEWS and trend.average_score >= TRUSTED_MIN_AVG_SCORE:
        return "trusted"
    return "building"


def apply_trust_adjustment(
    raw_score: int, comments: list[ReviewComment], trend: DeveloperTrend
) -> tuple[int, TrustLevel, int]:
    """
    Returns (adjusted_score, trust_level, adjustment_applied).

    - trusted (5+ reviews, 80+ avg score) and no critical finding this PR -> +5
    - needs_scrutiny (3+ reviews, <50 avg score) -> -5, surfaces the pattern
      to the reviewer even if this particular diff looks fine in isolation
    - new / building -> no adjustment, not enough history to act on yet
    """
    trust_level = classify_trust_level(trend)
    has_critical = any(c.severity == "critical" for c in comments)

    adjustment = 0
    if trust_level == "trusted" and not has_critical:
        adjustment = TRUST_ADJUSTMENT
    elif trust_level == "needs_scrutiny":
        adjustment = -TRUST_ADJUSTMENT

    adjusted_score = max(0, min(100, raw_score + adjustment))
    return adjusted_score, trust_level, adjustment
