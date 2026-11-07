"""Department-format (BIME Appendix 17) Word export through the vendored bime_word.

bime_word 1.1.5 lives in ``app/vendor/bime-word`` and runs as a child process
of the desktop backend's own interpreter. It reads the saved Markdown file,
writes ``<stem>.bime.docx`` beside it, and writes three sidecar reports
(``.bime.audit.json``, ``.bime.audit.md``, ``.bime.bime.json``).

Exit codes (bime_word ``scripts/bime/cli.py``): 0 written and audited, 1 written
but the audit found errors, 2 not written (message on stderr). A missing Python
dependency also exits 1, without JSON, so exit 0 and 1 count only when stdout
is the expected JSON summary.

In fragment scope bime_word numbers everything after the cover from 1, the
table of contents included. Appendix 17 二.4 numbers the front matter in
lowercase Roman numerals and starts the body at 1, so a converted document with
a table of contents gets its own front-matter section (``split_front_matter``)
and is audited again with ``bime_word audit``; the reports then describe the
file that is actually written.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from lxml import etree

from agent.paths import find_app_root

BIME_TIMEOUT_SECONDS = 180.0
_DETAIL_CHARS = 1_000
_MAX_COUNT = 1_000_000
_DOCUMENT_PART = "word/document.xml"
_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
# Children of w:sectPr that the schema places after w:pgNumType.
_AFTER_PGNUMTYPE = ("cols", "formProt", "vAlign", "noEndnote", "titlePg", "textDirection",
                    "bidi", "rtlGutter", "docGrid", "printerSettings", "sectPrChange")


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


def _summarize(summary: Any, reports: Any, layout: Any, folder: Path) -> dict[str, Any]:
    report = next(item for item in reports if isinstance(item, str) and item.endswith(".audit.md"))
    if not isinstance(summary, dict) or not isinstance(layout, bool):
        raise TypeError("audit")
    return {
        "errors": _count(summary, "error"),
        "warnings": _count(summary, "warning"),
        "manualChecks": _count(summary, "manual"),
        "reportPath": str(folder / report),
        "layoutVerified": layout,
    }


def _parse_summary(stdout: str, folder: Path) -> dict[str, Any]:
    """The audit summary from ``bime_word convert`` stdout."""
    payload = json.loads(stdout)
    return _summarize(payload["audit"], payload["reports"], payload["layout_verified"], folder)


def audit_command(target: Path, profile: Path | None, script: Path) -> list[str]:
    """Re-audit the final file into the same ``<stem>.bime.audit.*`` reports convert wrote."""
    command = [sys.executable, str(script), "audit", str(target)]
    if profile is not None:
        command += ["--config", str(profile)]
    return command + ["--scope", "fragment", "--report", str(target.with_suffix(".audit")), "--fail-on", "none"]


def _w(name: str) -> str:
    return f"{{{_W}}}{name}"


def _style(paragraph: etree._Element) -> str | None:
    style = paragraph.find(f"{_w('pPr')}/{_w('pStyle')}")
    return None if style is None else style.get(_w("val"))


def _set_numbering(section: etree._Element, fmt: str) -> None:
    """Number this section ``fmt`` from 1; w:pgNumType goes in schema order."""
    numbering = section.find(_w("pgNumType"))
    if numbering is None:
        numbering = etree.Element(_w("pgNumType"))
        later = next((child for child in section if etree.QName(child).localname in _AFTER_PGNUMTYPE), None)
        if later is None:
            section.append(numbering)
        else:
            later.addprevious(numbering)
    numbering.set(_w("fmt"), fmt)
    numbering.set(_w("start"), "1")


def _split_document_xml(data: bytes) -> bytes | None:
    """The document part with the table of contents in its own lowerRoman section, or None.

    Only a document whose TOC title (``BIMETOCTitle``) shares a section with the
    first chapter heading changes. A new empty paragraph before that heading
    ends the front-matter section (outside the TOC field, so updating the field
    in Word keeps it); the section copies the body's page setup and footer.
    """
    root = etree.fromstring(data)
    body = root.find(_w("body"))
    if body is None:
        return None
    children = list(body)
    toc = next((i for i, el in enumerate(children) if el.tag == _w("p") and _style(el) == "BIMETOCTitle"), None)
    if toc is None:
        return None
    chapter = next((i for i in range(toc + 1, len(children))
                    if children[i].tag == _w("p") and _style(children[i]) == "Heading1"), None)
    if chapter is None:
        return None
    if any(el.find(f"{_w('pPr')}/{_w('sectPr')}") is not None for el in children[toc:chapter]):
        return None
    body_section = next((el.find(f"{_w('pPr')}/{_w('sectPr')}") for el in children[chapter:]
                         if el.tag == _w("p") and el.find(f"{_w('pPr')}/{_w('sectPr')}") is not None),
                        body.find(_w("sectPr")))
    if body_section is None:
        return None
    front = copy.deepcopy(body_section)
    for kind in front.findall(_w("type")):
        front.remove(kind)  # no w:type: the next section starts on a new page
    _set_numbering(front, "lowerRoman")
    _set_numbering(body_section, "decimal")
    breaker = etree.Element(_w("p"))
    etree.SubElement(breaker, _w("pPr")).append(front)
    heading = children[chapter]
    heading.addprevious(breaker)
    page_break = heading.find(f"{_w('pPr')}/{_w('pageBreakBefore')}")
    if page_break is not None:
        page_break.getparent().remove(page_break)
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def split_front_matter(path: Path) -> bool:
    """Give the table of contents its own lowerRoman section (Appendix 17 二.4).

    Returns whether the file changed. Every other package part is copied
    byte for byte; the file is replaced atomically with the same mode.
    """
    try:
        with zipfile.ZipFile(path) as archive:
            members = [(info, archive.read(info)) for info in archive.infolist()]
    except (OSError, zipfile.BadZipFile) as exc:
        raise BimeExportError(f"Could not read {path.name} to number its front matter: {exc}") from exc
    try:
        document = next(data for info, data in members if info.filename == _DOCUMENT_PART)
        updated = _split_document_xml(document)
    except (StopIteration, etree.XMLSyntaxError) as exc:
        raise BimeExportError(f"{path.name} has no readable {_DOCUMENT_PART}.") from exc
    if updated is None:
        return False
    fd, temp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle, zipfile.ZipFile(handle, "w") as archive:
            for info, data in members:
                archive.writestr(info, updated if info.filename == _DOCUMENT_PART else data)
        os.chmod(temp, stat.S_IMODE(path.stat().st_mode))
        os.replace(temp, path)
    except BaseException:
        Path(temp).unlink(missing_ok=True)
        raise
    return True


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _record_split(operation_report: Path, converted_sha256: str, final_sha256: str) -> None:
    """Note the extra section in bime_word's operation report (``<stem>.bime.bime.json``)."""
    if not operation_report.is_file():
        return
    try:
        report = json.loads(operation_report.read_text(encoding="utf-8"))
        report["decisions"].append({
            "type": "front_matter_section",
            "rule": "PAGE_FORMAT",
            "message": "After conversion, the research agent gave the table of contents its own lowerRoman "
                       "section and restarted the body at 1 (Appendix 17 二.4); output_sha256 is the final file.",
            "converted_sha256": converted_sha256,
        })
        report["output_sha256"] = final_sha256
    except (ValueError, KeyError, AttributeError, TypeError) as exc:
        raise BimeExportError(f"Could not update {operation_report.name}: {exc}") from exc
    operation_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _run(command: list[str], folder: Path, env: dict[str, str], timeout: float) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(command, cwd=folder, env=env, capture_output=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise BimeExportError(f"bime_word did not finish within {timeout:g} s.") from exc
    except OSError as exc:
        raise BimeExportError(f"bime_word could not start: {exc}") from exc


def _reaudit(target: Path, profile: Path | None, script: Path, folder: Path, env: dict[str, str],
             timeout: float, layout_verified: bool) -> dict[str, Any]:
    """Audit the final file again; ``bime_word audit`` prints ``{overall, summary, reports}``."""
    completed = _run(audit_command(target, profile, script), folder, env, timeout)
    stdout = completed.stdout.decode("utf-8", errors="replace")
    stderr = completed.stderr.decode("utf-8", errors="replace")
    if completed.returncode != 0:
        raise BimeExportError(_detail(stderr) or f"bime_word audit failed with exit code {completed.returncode}.")
    try:
        payload = json.loads(stdout)
        return _summarize(payload["summary"], payload["reports"], layout_verified, folder)
    except (ValueError, KeyError, TypeError, StopIteration) as exc:
        detail = _detail(stderr) or _detail(stdout) or "no output"
        raise BimeExportError(f"bime_word audit returned unexpected output: {detail}") from exc


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
    completed = _run(convert_command(document_path, library_path, script), folder, env, timeout)
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
    converted = _sha256(target)
    if split_front_matter(target):
        audit = _reaudit(target, profile_for(document_path), script, folder, env, timeout, audit["layoutVerified"])
        _record_split(target.with_suffix(".bime.json"), converted, _sha256(target))
    return {"path": str(target), "audit": audit}
