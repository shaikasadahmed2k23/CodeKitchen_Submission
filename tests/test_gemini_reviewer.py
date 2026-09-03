import json
from unittest.mock import MagicMock, patch

from app.gemini_reviewer import GeminiReviewer, _parse_json_response


def test_parse_json_response_strips_markdown_fences():
    raw = '```json\n{"quality_score": 88, "summary": "ok", "comments": []}\n```'
    data = _parse_json_response(raw)
    assert data["quality_score"] == 88


def test_parse_json_response_plain_json():
    raw = json.dumps({"quality_score": 70, "summary": "fine", "comments": []})
    data = _parse_json_response(raw)
    assert data["summary"] == "fine"


@patch("app.gemini_reviewer.genai")
def test_reviewer_builds_review_result(mock_genai):
    fake_response = MagicMock()
    fake_response.text = json.dumps({
        "quality_score": 76,
        "summary": "Adds a helper function; looks fine.",
        "comments": [
            {"file": "app/utils.py", "line": 12, "severity": "minor",
             "category": "style", "message": "Prefer f-strings over .format()"}
        ],
    })
    mock_model = MagicMock()
    mock_model.generate_content.return_value = fake_response
    mock_genai.GenerativeModel.return_value = mock_model

    reviewer = GeminiReviewer(api_key="fake-key")
    result = reviewer.review(
        repo="asad/repo", pr_number=7, author="asad",
        diff_text="+def foo(): pass", files=["app/utils.py"],
    )

    assert result.quality_score == 76
    assert result.files_reviewed == 1
    assert len(result.comments) == 1
    assert result.comments[0].category == "style"
    assert "Quality Score" in result.to_pr_comment_markdown()
