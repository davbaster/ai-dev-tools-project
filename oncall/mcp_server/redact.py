"""Redaction for every tool result and audit entry (#16, AGENTS.md).

Hides credentials and personal data; keeps what an investigation needs
(trace/span ids, commit SHAs, numeric ids, route templates, timestamps).
"""

import os
import re

MASK = "[REDACTED]"

# Order matters: the specific patterns run before the generic ones.
_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Render deploy hooks: the whole URL is the secret.
    (
        re.compile(r"https://api\.render\.com/deploy/srv-[A-Za-z0-9]+\?key=[\w-]+"),
        "https://api.render.com/deploy/" + MASK,
    ),
    # Authorization header values (any scheme), in headers, JSON or logs.
    (
        re.compile(r"(?i)(\bauthorization\b[\"']?\s*[:=]\s*[\"']?)[^\"'\\\r\n,}]+"),
        r"\1" + MASK,
    ),
    (re.compile(r"(?i)\b(bearer\s+)[A-Za-z0-9._~+/=-]+"), r"\1" + MASK),
    # user:password@ in URLs (postgresql://user:pass@host/db).
    (
        re.compile(r"\b([a-z][a-z0-9+.-]*://[^:/\s@\"']+:)[^@\s/\"']+@"),
        r"\1" + MASK + "@",
    ),
    # Well-known key formats.
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"), MASK),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"), MASK),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"), MASK),
    # key=value, "key": "value", key: value for names that end in a secret word
    # (password, POSTGRES_PASSWORD, MCP_TOKEN, ...); token_hash doesn't match.
    (
        re.compile(
            r"(?i)(\b[A-Za-z0-9_]*?(?:password|passwd|pwd|secret|token|api_key|apikey"
            r"|access_key|private_key|credentials?)\b[\"']?\s*[:=]\s*[\"']?)"
            r"[^\"'\\\s,}&]+"
        ),
        r"\1" + MASK,
    ),
    # ?key=... / &key=... in URLs.
    (re.compile(r"([?&](?:key|token|sig|signature)=)[^&\s\"']+"), r"\1" + MASK),
    # Email addresses (customer data).
    (
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
        "[REDACTED-EMAIL]",
    ),
]

# Valores de secretos de la configuración: se ocultan donde aparezcan.
_SECRET_ENV = ("MCP_TOKEN", "ALERT_WEBHOOK_TOKEN", "POSTGRES_PASSWORD", "LLM_API_KEY")
_MIN_SECRET_LENGTH = 6


def _known_secrets() -> list[str]:
    values = (os.environ.get(name, "") for name in _SECRET_ENV)
    return sorted(
        (v for v in values if len(v) >= _MIN_SECRET_LENGTH), key=len, reverse=True
    )


def redact(text: str) -> str:
    """Return text with credentials, secrets and email addresses masked."""
    for secret in _known_secrets():
        text = text.replace(secret, MASK)
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def redact_value(value):
    """Redact strings inside dicts/lists (for audit arguments)."""
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, dict):
        return {k: redact_value(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [redact_value(v) for v in value]
    return value
