"""MCP stderr log policy: 0600 creation, 5 MiB rotation, run headers."""

import os

from agent.mcp import (
    MCP_LOG_KEEP_ROTATED,
    MCP_LOG_MAX_BYTES,
    MCPServerSpec,
    _spec_to_connection,
    prepare_stderr_log,
)


def test_log_created_0600_with_run_header_before_server_start(tmp_path):
    log_path = tmp_path / "web_search.stderr.log"
    run_id = prepare_stderr_log(str(log_path), run_id="run-abc")
    assert run_id == "run-abc"
    assert log_path.exists()
    assert oct(log_path.stat().st_mode & 0o777) == "0o600"
    content = log_path.read_text(encoding="utf-8")
    assert content.startswith("=== mcp run run-abc started ")
    assert content.rstrip().endswith("===")


def test_repeated_runs_append_headers_without_rotation(tmp_path):
    log_path = tmp_path / "s.stderr.log"
    prepare_stderr_log(str(log_path), run_id="one")
    prepare_stderr_log(str(log_path), run_id="two")
    content = log_path.read_text(encoding="utf-8")
    assert "run one" in content and "run two" in content
    assert not (tmp_path / "s.stderr.log.1").exists()


def test_rotation_at_5mib_keeps_three_copies(tmp_path):
    log_path = tmp_path / "s.stderr.log"
    for run in range(4):
        log_path.write_bytes(f"payload-{run}".encode().ljust(MCP_LOG_MAX_BYTES, b"x"))
        prepare_stderr_log(str(log_path), run_id=f"run-{run}")
    assert MCP_LOG_KEEP_ROTATED == 3
    # Current log holds only the newest header.
    assert "run-3" in log_path.read_text(encoding="utf-8")
    rotated = sorted(p.name for p in tmp_path.glob("s.stderr.log.*"))
    assert rotated == ["s.stderr.log.1", "s.stderr.log.2", "s.stderr.log.3"]
    # Oldest payload fell off the end.
    assert "payload-3" in (tmp_path / "s.stderr.log.1").read_text(
        encoding="utf-8", errors="replace"
    )[:64]
    assert "payload-1" in (tmp_path / "s.stderr.log.3").read_text(
        encoding="utf-8", errors="replace"
    )[:64]


def test_unwritable_location_degrades_without_raising(tmp_path):
    blocked = tmp_path / "no-write"
    blocked.mkdir()
    blocked.chmod(0o500)
    try:
        run_id = prepare_stderr_log(str(blocked / "x.log"))
        assert run_id  # still returns a run id; startup must not crash
    finally:
        blocked.chmod(0o700)


def test_spec_to_connection_prepares_log(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    spec = MCPServerSpec(
        name="web_search", command="/bin/echo", args=["hi"], env={}
    )
    conn = _spec_to_connection(spec)
    log_path = tmp_path / "agent-mcp" / "web_search.stderr.log"
    assert log_path.exists()
    assert oct(log_path.stat().st_mode & 0o777) == "0o600"
    assert "=== mcp run" in log_path.read_text(encoding="utf-8")
    assert str(log_path) in " ".join(conn["args"])
