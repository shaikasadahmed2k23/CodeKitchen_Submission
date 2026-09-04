from app.models import DeveloperTrend, ReviewComment
from app.trust import apply_trust_adjustment, classify_trust_level


def _trend(review_count: int, average_score: float) -> DeveloperTrend:
    return DeveloperTrend(developer="asad", repo="asad/repo", review_count=review_count, average_score=average_score)


def test_classify_new_developer():
    assert classify_trust_level(_trend(0, 0.0)) == "new"


def test_classify_building_not_enough_reviews_yet():
    assert classify_trust_level(_trend(2, 95.0)) == "building"


def test_classify_trusted():
    assert classify_trust_level(_trend(6, 85.0)) == "trusted"


def test_classify_needs_scrutiny():
    assert classify_trust_level(_trend(4, 35.0)) == "needs_scrutiny"


def test_classify_building_mixed_history_not_trusted_or_scrutiny():
    # 5+ reviews but average score below the trusted bar, and not low enough for scrutiny
    assert classify_trust_level(_trend(6, 65.0)) == "building"


def test_trusted_developer_gets_positive_adjustment():
    trend = _trend(6, 90.0)
    adjusted, level, adj = apply_trust_adjustment(raw_score=80, comments=[], trend=trend)
    assert level == "trusted"
    assert adj == 5
    assert adjusted == 85


def test_needs_scrutiny_developer_gets_negative_adjustment():
    trend = _trend(4, 30.0)
    adjusted, level, adj = apply_trust_adjustment(raw_score=70, comments=[], trend=trend)
    assert level == "needs_scrutiny"
    assert adj == -5
    assert adjusted == 65


def test_new_developer_gets_no_adjustment():
    trend = _trend(0, 0.0)
    adjusted, level, adj = apply_trust_adjustment(raw_score=88, comments=[], trend=trend)
    assert level == "new"
    assert adj == 0
    assert adjusted == 88


def test_critical_finding_blocks_positive_adjustment_even_for_trusted_developer():
    trend = _trend(10, 95.0)  # excellent history
    critical_comment = ReviewComment(file="app/auth.py", line=1, severity="critical",
                                      category="security", message="Hardcoded secret")
    adjusted, level, adj = apply_trust_adjustment(raw_score=40, comments=[critical_comment], trend=trend)
    assert level == "trusted"
    assert adj == 0  # trust never buys leniency on a fresh critical finding
    assert adjusted == 40


def test_adjustment_never_pushes_score_above_100():
    trend = _trend(6, 90.0)
    adjusted, _, _ = apply_trust_adjustment(raw_score=98, comments=[], trend=trend)
    assert adjusted == 100


def test_adjustment_never_pushes_score_below_0():
    trend = _trend(4, 20.0)
    adjusted, _, _ = apply_trust_adjustment(raw_score=3, comments=[], trend=trend)
    assert adjusted == 0
