import hashlib
import hmac

import pytest

from app.webhook_handler import (
    InvalidSignatureError,
    parse_pull_request_event,
    verify_signature,
)

SECRET = "test-secret"


def _sign(body: bytes) -> str:
    return "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()


def test_verify_signature_accepts_valid_signature():
    body = b'{"hello": "world"}'
    verify_signature(body, _sign(body), SECRET)  # should not raise


def test_verify_signature_rejects_missing_header():
    with pytest.raises(InvalidSignatureError):
        verify_signature(b"{}", None, SECRET)


def test_verify_signature_rejects_tampered_body():
    body = b'{"hello": "world"}'
    sig = _sign(body)
    with pytest.raises(InvalidSignatureError):
        verify_signature(b'{"hello": "tampered"}', sig, SECRET)


def test_verify_signature_rejects_wrong_scheme():
    with pytest.raises(InvalidSignatureError):
        verify_signature(b"{}", "sha1=deadbeef", SECRET)


def test_parse_pull_request_event_opened():
    payload = {
        "action": "opened",
        "pull_request": {"number": 42, "user": {"login": "asad"}, "diff_url": "https://x/y.diff"},
        "repository": {"full_name": "asad/repo"},
    }
    event = parse_pull_request_event(payload)
    assert event is not None
    assert event.pr_number == 42
    assert event.author == "asad"
    assert event.repo_full_name == "asad/repo"


def test_parse_pull_request_event_ignores_closed():
    payload = {"action": "closed", "pull_request": {}, "repository": {}}
    assert parse_pull_request_event(payload) is None


def test_parse_pull_request_event_handles_missing_data():
    assert parse_pull_request_event({"action": "opened"}) is None
