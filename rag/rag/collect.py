"""File collection for ingest: which files to index, grouped by folder.

Library-level module so both the ingest CLI and rag.sync share one
implementation (sync previously reached into the CLI's private helpers).
"""

from __future__ import annotations

import re
from pathlib import Path

# File extensions to ingest as text
TEXT_EXTENSIONS = {
    # Docs
    ".md", ".txt", ".rst", ".csv", ".json", ".yaml", ".yml", ".toml",
    # Python
    ".py",
    # Web
    ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".vue", ".svelte",
    # Config
    ".ini", ".cfg", ".conf", ".env.example",
    # Data
    ".sql", ".sh", ".bash", ".zsh",
    # Other code
    ".java", ".c", ".cpp", ".h", ".go", ".rs", ".rb",
    # PL/SQL (legacy)
    ".pck", ".pkb", ".pks", ".plsql",
}

# Directories to always skip
SKIP_DIRS = {
    ".git",
    ".github",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    "env",
    ".claude",
    ".opencode",
    ".cursor",
    "plan_logs",
    "volumes",
    "dist",
    "build",
}

_DO_NOT_INDEX_PATTERN = re.compile(r"^\s*do_not_index\s*:\s*true\s*$", re.IGNORECASE)


def _should_ingest(path: Path) -> bool:
    """Check if a file should be ingested."""
    if path.suffix.lower() in TEXT_EXTENSIONS:
        return True
    if path.name in {"Makefile", "Dockerfile", "Procfile", ".gitignore", ".env.example"}:
        return True
    return False


def get_file_preview(path: Path) -> str:
    """Get the first non-empty line of a file."""
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped:
                    return stripped[:120]
        return ""
    except (UnicodeDecodeError, PermissionError):
        return ""


def has_do_not_index_sentinel(path: Path, scan_lines: int = 8) -> bool:
    """Return True when early file lines contain a do_not_index flag."""
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            for _ in range(scan_lines):
                line = f.readline()
                if not line:
                    break
                if _DO_NOT_INDEX_PATTERN.match(line):
                    return True
    except OSError:
        return False
    return False


def collect_folders(
    root: Path,
    extra_skip: set[str] | None = None,
    skip_rel_paths: set[str] | None = None,
) -> dict[str, list[Path]]:
    """Group ingestable files by their parent directory.

    Args:
        root: Directory to scan.
        extra_skip: Names matched against any path component (so a name like
            ``"app"`` skips every directory called ``app`` anywhere in the tree).
        skip_rel_paths: Rel paths anchored at ``root`` (POSIX-style); a file is
            skipped iff its rel path equals or sits under one of these. Use this
            when a name-based skip would over-match (e.g. excluding only the
            top-level ``app/`` while keeping ``web/backend/app/``).
    """
    skip_names = SKIP_DIRS | (extra_skip or set())
    skip_path_parts = [Path(p).parts for p in (skip_rel_paths or set())]
    folders: dict[str, list[Path]] = {}
    for file_path in sorted(root.rglob("*")):
        if not file_path.is_file():
            continue
        parts = file_path.relative_to(root).parts
        if any(part in skip_names for part in parts):
            continue
        if any(parts[: len(sp)] == sp for sp in skip_path_parts):
            continue
        if not _should_ingest(file_path):
            continue
        if file_path.suffix.lower() == ".md" and has_do_not_index_sentinel(file_path):
            continue
        folder_rel = str(file_path.parent.relative_to(root))
        if folder_rel == ".":
            folder_rel = ""
        folders.setdefault(folder_rel, []).append(file_path)
    return folders
