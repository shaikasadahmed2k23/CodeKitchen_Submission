"""
Redacts likely secrets/PII from a diff BEFORE it is sent to Gemini.
This is the privacy guardrail called out in the approach note's edge cases.
"""
import re

_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("aws_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("gh_token", re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}")),
    ("generic_api_key", re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{12,}['\"]?")),
    ("private_key_block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]+?-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("email", re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")),
    ("jwt", re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
]


def redact(diff_text: str) -> tuple[str, list[str]]:
    """Returns (redacted_text, list_of_redaction_types_found)."""
    found: list[str] = []
    cleaned = diff_text
    for name, pattern in _PATTERNS:
        if pattern.search(cleaned):
            found.append(name)
            cleaned = pattern.sub("[REDACTED]", cleaned)
    return cleaned, found


def truncate(diff_text: str, max_chars: int) -> tuple[str, bool]:
    """Guards against context-window blowout on very large diffs."""
    if len(diff_text) <= max_chars:
        return diff_text, False
    return diff_text[:max_chars] + "\n\n[... diff truncated, exceeded review size limit ...]", True
