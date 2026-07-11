"""Schema validation for skill manifests."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, StrictBool, ValidationError, model_validator

_LEGACY_FIELDS = ("capabilities", "tool_policy")
_LEGACY_FIELDS_ERROR = (
    "Legacy manifest fields `capabilities` and `tool_policy` are no longer "
    "supported. Use the `tools` section."
)


class SkillToolSelector(BaseModel):
    """One required/optional block of skill tool requests."""

    model_config = ConfigDict(extra="forbid", strict=True)

    local: list[str] = Field(default_factory=list)
    mcp_families: list[str] = Field(default_factory=list)

    def is_empty(self) -> bool:
        return not self.local and not self.mcp_families


class SkillTools(BaseModel):
    """Skill-scoped tool requests declared by a manifest."""

    model_config = ConfigDict(extra="forbid", strict=True)

    required: SkillToolSelector = Field(default_factory=SkillToolSelector)
    optional: SkillToolSelector = Field(default_factory=SkillToolSelector)

    @model_validator(mode="after")
    def reject_empty_tools_section(self) -> "SkillTools":
        if self.required.is_empty() and self.optional.is_empty():
            raise ValueError(
                "tools section must request at least one local tool or MCP family"
            )
        return self


class SkillResource(BaseModel):
    """Resource declaration in a skill manifest."""

    model_config = ConfigDict(extra="forbid", strict=True)

    path: str
    use_when: str | None = None
    pinned: StrictBool = False


class SkillManifest(BaseModel):
    """Validated skill manifest schema."""

    model_config = ConfigDict(extra="forbid", strict=True)

    tools: SkillTools | None = None
    resources: list[SkillResource] = Field(default_factory=list)
    task_modes: list[str] = Field(default_factory=list)


def validate_skill_manifest(
    data: Mapping[str, Any],
    *,
    source: str | Path = "manifest.yaml",
) -> dict[str, Any]:
    """Validate a manifest mapping and return a normalized plain dict."""
    legacy = [field for field in _LEGACY_FIELDS if field in data]
    if legacy:
        raise ValueError(f"invalid skill manifest: {source}: {_LEGACY_FIELDS_ERROR}")
    try:
        manifest = SkillManifest.model_validate(data)
    except ValidationError as exc:
        raise ValueError(f"invalid skill manifest: {source}: {exc}") from exc
    return manifest.model_dump(mode="python", exclude_none=True)
