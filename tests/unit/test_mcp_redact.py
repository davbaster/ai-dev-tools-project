"""Redaction hides secrets and personal data, keeps what investigation needs (#16)."""

import pytest

from oncall.mcp_server.redact import redact, redact_value

HIDDEN = [
    ("Authorization: Bearer abc.def-123", "abc.def-123"),
    ('{"authorization": "Bearer tok3n-value"}', "tok3n-value"),
    ("postgresql://para_luego:s3cr3t-pw@db:5432/para_luego", "s3cr3t-pw"),
    ("password=hunter2-x", "hunter2-x"),
    ('{"token": "a1b2c3d4e5"}', "a1b2c3d4e5"),
    ("api_key: zzz-key-123", "zzz-key-123"),
    ("POSTGRES_PASSWORD=change_me_local", "change_me_local"),
    ("MCP_TOKEN=abcdef123456", "abcdef123456"),
    ("ghp_" + "A" * 36, "ghp_" + "A" * 36),
    ("github_pat_" + "B1" * 15, "github_pat_" + "B1" * 15),
    ("sk-" + "c" * 32, "sk-" + "c" * 32),
    ("https://api.render.com/deploy/srv-abc123?key=SeCrEtKey", "SeCrEtKey"),
    ("contact ana.perez@example.com now", "ana.perez@example.com"),
]


@pytest.mark.parametrize(("text", "secret"), HIDDEN)
def test_secret_is_hidden(text, secret):
    out = redact(text)
    assert secret not in out and "[REDACTED" in out


def test_investigation_data_is_kept():
    line = (
        '{"trace_id": "4bf92f3577b34da6a3ce929d0e0e4736", "span_id": "00f067aa0ba902b7", '
        '"version": "36d0d0ccb475f9ef1c2c7dbac5fd4236c516ccc8", "item_id": 42, '
        '"route": "/api/items/{item_id}", "timestamp": "2026-11-12T19:46:28.256Z", '
        '"sql": "WHERE auth_tokens.token_hash = %(token_hash_1)s"}'
    )
    assert redact(line) == line


def test_configured_secret_values_are_hidden(monkeypatch):
    monkeypatch.setenv("MCP_TOKEN", "local-mcp-token-value")
    assert "local-mcp-token-value" not in redact("x local-mcp-token-value y")


def test_nested_arguments_are_redacted():
    out = redact_value({"q": ["password=abc12345"], "n": 3})
    assert out == {"q": ["password=[REDACTED]"], "n": 3}


def test_redaction_never_breaks_json_strings():
    import json

    text = json.dumps({"content": 'POSTGRES_PASSWORD=abc\\"x\nTOKEN="y12345"'})
    assert json.loads(redact(text))
