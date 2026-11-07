"""Department-format (BIME Appendix 17) Word export through the vendored bime_word.

bime_word 1.1.5 lives in ``app/vendor/bime-word`` and runs as a child process
of the desktop backend's own interpreter. It reads the saved Markdown file,
writes ``<stem>.bime.docx`` beside it, and writes three sidecar reports
(``.bime.audit.json``, ``.bime.audit.md``, ``.bime.bime.json``).

Exit codes (bime_word ``scripts/bime/cli.py``): 0 written and audited, 1 written
but the audit found errors, 2 not written (message on stderr). A missing Python
dependency also exits 1, without JSON, so exit 0 and 1 count only when stdout
is the expected JSON summary.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from agent.paths import find_app_root

BIME_TIMEOUT_SECONDS = 180.0
_DETAIL_CHARS = 1_000
_MAX_COUNT = 1_000_000


class BimeExportError(Exception):
    """bime_word did not produce a document; the message is shown to the user."""


def vendor_script() -> Path:
    """The vendored command-line entry point."""
    return find_app_root() / "vendor" / "bime-word" / "scripts" / "bime_word.py"


def bime_target(document_path: Path) -> Path:
    """``<stem>.bime.docx`` beside the document (never the tracked ``<stem>.docx``)."""
    return document_path.parent / f"{document_path.stem}.bime.docx"


def profile_for(document_path: Path) -> Path | None:
    """``bime-<stem>-profile.json`` beside the document, when the author keeps one."""
    candidate = document_path.parent / f"bime-{document_path.stem}-profile.json"
    return candidate if candidate.is_file() else None


def convert_command(document_path: Path, library_path: Path, script: Path) -> list[str]:
    """The bime_word convert call: fragment scope, project bibliography, overwrite."""
    command = [sys.executable, str(script), "convert", str(document_path), "-o", str(bime_target(document_path))]
    profile = profile_for(document_path)
    if profile is not None:
        command += ["--config", str(profile)]
    return command + ["--bibliography", str(library_path), "--scope", "fragment", "--overwrite"]


def _detail(text: str) -> str:
    text = text.strip()
    return text if len(text) <= _DETAIL_CHARS else "…" + text[-_DETAIL_CHARS:]


def _count(summary: dict[str, Any], name: str) -> int:
    value = summary[name]
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= _MAX_COUNT:
        raise TypeError(name)
    return value


def _parse_summary(stdout: str, folder: Path) -> dict[str, Any]:
    payload = json.loads(stdout)
    summary = payload["audit"]
    report = next(item for item in payload["reports"] if isinstance(item, str) and item.endswith(".audit.md"))
    layout = payload["layout_verified"]
    if not isinstance(summary, dict) or not isinstance(layout, bool):
        raise TypeError("audit")
    return {
        "errors": _count(summary, "error"),
        "warnings": _count(summary, "warning"),
        "manualChecks": _count(summary, "manual"),
        "reportPath": str(folder / report),
        "layoutVerified": layout,
    }


def run_bime_convert(
    document_path: Path,
    library_path: Path,
    *,
    timeout: float = BIME_TIMEOUT_SECONDS,
    script: Path | None = None,
) -> dict[str, Any]:
    """Convert one saved Markdown file; return the output path and audit summary."""
    script = vendor_script() if script is None else script
    if not script.is_file():
        raise BimeExportError(f"The bundled bime_word is missing: {script}")
    folder = document_path.parent
    env = dict(os.environ)
    # Pandoc sits beside the backend's interpreter in the Conda environment.
    env["PATH"] = os.pathsep.join(filter(None, [str(Path(sys.executable).parent), env.get("PATH", "")]))
    try:
        completed = subprocess.run(
            convert_command(document_path, library_path, script),
            cwd=folder, env=env, capture_output=True, timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise BimeExportError(f"bime_word did not finish within {timeout:g} s.") from exc
    except OSError as exc:
        raise BimeExportError(f"bime_word could not start: {exc}") from exc
    stdout = completed.stdout.decode("utf-8", errors="replace")
    stderr = completed.stderr.decode("utf-8", errors="replace")
    if completed.returncode not in (0, 1):
        raise BimeExportError(_detail(stderr) or f"bime_word failed with exit code {completed.returncode}.")
    try:
        audit = _parse_summary(stdout, folder)
    except (ValueError, KeyError, TypeError, StopIteration) as exc:
        detail = _detail(stderr) or _detail(stdout) or "no output"
        raise BimeExportError(f"bime_word returned unexpected output (exit code {completed.returncode}): {detail}") from exc
    target = bime_target(document_path)
    if not target.is_file():
        raise BimeExportError(f"bime_word reported success but did not write {target}.")
    return {"path": str(target), "audit": audit}
