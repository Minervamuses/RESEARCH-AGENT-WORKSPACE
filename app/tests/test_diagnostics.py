"""Local diagnostic log: location, permissions, redaction, and fallback."""

import logging
import stat

import pytest

from agent import diagnostics


@pytest.fixture
def installed():
    yield
    diagnostics.uninstall_diagnostic_log()


def test_log_dir_precedence(tmp_path):
    assert diagnostics.diagnostic_log_dir({"AGENT_LOG_DIR": str(tmp_path / "x")}) == (
        tmp_path / "x"
    )
    assert diagnostics.diagnostic_log_dir({"XDG_STATE_HOME": str(tmp_path)}) == (
        tmp_path / "research-agent" / "logs"
    )


def test_install_writes_app_info_and_library_warnings_only(tmp_path, installed):
    path = diagnostics.install_diagnostic_log(
        "cli", echo_stderr=False, env={"AGENT_LOG_DIR": str(tmp_path / "logs")},
    )

    assert path == tmp_path / "logs" / "cli.log"
    assert diagnostics.current_log_path() == path
    logging.getLogger("skills.citation.service").info("save item outcome")
    logging.getLogger("agent.graph").debug("debug detail")
    logging.getLogger("httpx").info("HTTP Request: GET https://x?api_key=abc")
    logging.getLogger("httpx").warning("library warning")
    try:
        raise KeyError("boom")
    except KeyError:
        logging.getLogger("agent.desktop.service").exception("incident 1234abcd")
    for handler in logging.getLogger().handlers:
        handler.flush()

    text = path.read_text(encoding="utf-8")
    assert "INFO skills.citation.service" in text and "save item outcome" in text
    assert "debug detail" not in text
    assert "HTTP Request" not in text
    assert "library warning" in text
    assert "incident 1234abcd" in text and "Traceback" in text and "KeyError" in text
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_install_is_idempotent(tmp_path, installed):
    env = {"AGENT_LOG_DIR": str(tmp_path)}
    first = diagnostics.install_diagnostic_log("cli", echo_stderr=False, env=env)
    handler_count = len(logging.getLogger().handlers)

    second = diagnostics.install_diagnostic_log("other", echo_stderr=False, env=env)

    assert second == first
    assert len(logging.getLogger().handlers) == handler_count


def test_secrets_are_redacted_before_writing(tmp_path, installed):
    env = {
        "AGENT_LOG_DIR": str(tmp_path),
        "OPENROUTER_API_KEY": "sk-or-v1-supersecretvalue",
        "GITHUB_TOKEN": "ghp_tokenvalue123",
        "SHORT_KEY": "abc",
    }
    path = diagnostics.install_diagnostic_log("cli", echo_stderr=False, env=env)
    log = logging.getLogger("agent.test")
    log.warning("key sk-or-v1-supersecretvalue in text and ghp_tokenvalue123")
    log.warning("url https://api.openalex.org/works?api_key=raw123&search=x")
    log.warning("header Authorization: Bearer abc.def-ghi and mailto:me@example.org")
    log.warning("short abc stays")
    try:
        raise RuntimeError("failed with token=deadbeefcafe")
    except RuntimeError:
        log.exception("traceback carries secrets")
    for handler in logging.getLogger().handlers:
        handler.flush()

    text = path.read_text(encoding="utf-8")
    for secret in (
        "sk-or-v1-supersecretvalue", "ghp_tokenvalue123", "raw123",
        "abc.def-ghi", "me@example.org", "deadbeefcafe",
    ):
        assert secret not in text
    assert "api_key=[redacted]&search=x" in text
    assert "short abc stays" in text


def test_echo_stderr_keeps_plain_warnings_on_the_terminal(tmp_path, installed, capsys):
    diagnostics.install_diagnostic_log(
        "cli", echo_stderr=True, env={"AGENT_LOG_DIR": str(tmp_path)},
    )

    logging.getLogger("agent.mcp").warning("MCP server failed to start")
    logging.getLogger("agent.mcp").info("not for the terminal")

    err = capsys.readouterr().err
    assert "MCP server failed to start" in err
    assert "not for the terminal" not in err


def test_unwritable_log_dir_falls_back_to_stderr(tmp_path, installed, capsys):
    blocker = tmp_path / "file"
    blocker.write_text("not a directory")

    path = diagnostics.install_diagnostic_log(
        "desktop-backend", echo_stderr=False, env={"AGENT_LOG_DIR": str(blocker)},
    )

    assert path is None
    assert diagnostics.current_log_path() is None
    logging.getLogger("agent.desktop.server").error("still visible")
    err = capsys.readouterr().err
    assert "diagnostic log file unavailable" in err
    assert "still visible" in err


def test_rotation_keeps_owner_only_files(tmp_path, installed, monkeypatch):
    monkeypatch.setattr(diagnostics, "MAX_LOG_BYTES", 200)
    path = diagnostics.install_diagnostic_log(
        "cli", echo_stderr=False, env={"AGENT_LOG_DIR": str(tmp_path)},
    )
    for index in range(20):
        logging.getLogger("agent.test").warning("line %d %s", index, "x" * 40)

    rotated = sorted(tmp_path.glob("cli.log*"))
    assert path in rotated and len(rotated) > 1
    assert len(rotated) <= diagnostics.LOG_BACKUP_COUNT + 1
    assert all(stat.S_IMODE(item.stat().st_mode) == 0o600 for item in rotated)
