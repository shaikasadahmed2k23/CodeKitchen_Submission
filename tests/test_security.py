from app.security import redact, truncate


def test_redact_github_token():
    text = "token = ghp_1234567890abcdefghijklmnopqrstuv"
    cleaned, found = redact(text)
    assert "ghp_" not in cleaned
    assert "gh_token" in found


def test_redact_aws_key():
    text = "AWS_KEY=AKIAABCDEFGHIJKLMNOP"
    cleaned, found = redact(text)
    assert "AKIA" not in cleaned
    assert "aws_key" in found


def test_redact_private_key_block():
    text = "-----BEGIN RSA PRIVATE KEY-----\nMIIB...\n-----END RSA PRIVATE KEY-----"
    cleaned, found = redact(text)
    assert "MIIB" not in cleaned
    assert "private_key_block" in found


def test_redact_email():
    text = "contact me at asad@example.com for details"
    cleaned, found = redact(text)
    assert "asad@example.com" not in cleaned
    assert "email" in found


def test_redact_leaves_clean_diff_untouched():
    text = "def add(a, b):\n    return a + b\n"
    cleaned, found = redact(text)
    assert cleaned == text
    assert found == []


def test_truncate_under_limit_unchanged():
    text = "x" * 100
    result, was_truncated = truncate(text, 1000)
    assert result == text
    assert was_truncated is False


def test_truncate_over_limit():
    text = "x" * 100
    result, was_truncated = truncate(text, 50)
    assert was_truncated is True
    assert len(result) < len(text) + 100
    assert result.startswith("x" * 50)
