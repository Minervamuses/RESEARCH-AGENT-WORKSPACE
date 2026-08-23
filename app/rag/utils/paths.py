"""Path utilities for the KMS."""

import hashlib
import re
from pathlib import Path

_DATE_RE = re.compile(r"(\d{4})(\d{2})(\d{2})")


def extract_date(rel_path: str) -> int:
    """Extract date as YYYYMMDD integer from path if a date folder exists."""
    for part in Path(rel_path).parts:
        match = _DATE_RE.fullmatch(part)
        if match:
            return int(f"{match.group(1)}{match.group(2)}{match.group(3)}")
    return 0


def source_namespace(root: Path) -> str:
    """Return a deterministic namespace for one canonical ingest root."""
    canonical_root = root.resolve()
    digest = hashlib.sha256(str(canonical_root).encode("utf-8")).hexdigest()
    return f"root-{digest}"


def scoped_source_id(namespace: str, rel_path: str) -> str:
    """Combine a root namespace and root-relative path into a stable id."""
    return f"{namespace}:{rel_path}"
