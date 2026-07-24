"""Typed data exchanged by extension discovery and registry code."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ExtensionKind = Literal["skill", "mcp"]
ExtensionOperation = Literal[
    "add",
    "update",
    "delete",
    "unchanged",
    "blocked",
    "guarded",
]


class AppliedExtension(BaseModel):
    """One host-validated extension referenced by the applied registry."""

    model_config = ConfigDict(extra="forbid", strict=True)

    kind: ExtensionKind
    id: str
    source_hash: str
    installed_relpath: str
    skill_manifest: dict[str, Any] | None = None
    mcp_descriptor: dict[str, Any] | None = None
    command_binding_hash: str | None = None
    execution_approved: bool = False


class ExtensionRegistry(BaseModel):
    """The complete applied state for one drop-in root."""

    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal[1] = 1
    revision: int = Field(default=0, ge=0)
    source_root: str | None = None
    manager_skill_hash: str | None = None
    extensions: dict[str, AppliedExtension] = Field(default_factory=dict)


@dataclass(frozen=True)
class ScannedExtension:
    """One bundle observed under the desired-state root."""

    kind: ExtensionKind
    id: str
    source_path: Path
    source_hash: str | None
    relative_files: tuple[str, ...] = ()
    skill_manifest: dict[str, Any] | None = None
    valid: bool = True
    errors: tuple[str, ...] = ()

    @property
    def key(self) -> str:
        return extension_key(self.kind, self.id)


@dataclass(frozen=True)
class ScanResult:
    """A bounded scan of the complete desired-state root."""

    root: Path
    items: dict[str, ScannedExtension]
    complete_for_delete: bool
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExtensionChange:
    """One authoritative desired-versus-applied decision."""

    operation: ExtensionOperation
    key: str
    desired: ScannedExtension | None = None
    applied: AppliedExtension | None = None
    reason: str | None = None


@dataclass(frozen=True)
class ExtensionDiff:
    """Ordered, immutable change set produced by deterministic host code."""

    changes: tuple[ExtensionChange, ...]
    delete_enabled: bool
    diagnostics: tuple[str, ...] = field(default_factory=tuple)


def extension_key(kind: ExtensionKind, extension_id: str) -> str:
    return f"{kind}:{extension_id}"
