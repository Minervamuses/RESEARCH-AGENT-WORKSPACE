"""Strict declarative stdio MCP descriptors and exact launch bindings."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    ValidationError,
    model_validator,
)

from agent.mcp import MCPServerSpec

_NAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9_-]{0,62}[a-z0-9])?$")
_ENV_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_INTERPRETERS = frozenset({"python", "python3", "node", "deno", "bun"})
_RESERVED_MCP_IDENTIFIERS = frozenset({"github", "web_search"})
_BASE_ENV = (
    "PATH",
    "HOME",
    "USER",
    "TMPDIR",
    "TMP",
    "TEMP",
    "LANG",
    "LC_ALL",
    "SYSTEMROOT",
)
_SECRET_HINTS = ("TOKEN", "SECRET", "PASSWORD", "API_KEY", "PRIVATE_KEY")


class MCPManifestError(ValueError):
    """A drop-in MCP descriptor cannot produce one safe direct launch."""


class MCPEnvironmentBinding(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    from_env: str | None = None
    value: str | None = None
    required: StrictBool = False
    secret: StrictBool = False

    @model_validator(mode="after")
    def validate_source(self) -> "MCPEnvironmentBinding":
        if (self.from_env is None) == (self.value is None):
            raise ValueError("exactly one of from_env or value is required")
        if self.from_env is not None and not _ENV_RE.fullmatch(self.from_env):
            raise ValueError("from_env is not a valid environment name")
        if self.value is not None and self.secret:
            raise ValueError("literal secret values are forbidden")
        return self


class MCPRuntime(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    transport: Literal["stdio"]
    command: str = Field(min_length=1, max_length=512)
    args: list[str] = Field(default_factory=list, max_length=64)
    cwd: str = Field(default=".", min_length=1, max_length=512)


class MCPDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal[1]
    kind: Literal["mcp"]
    id: str
    family: str
    scope: Literal["skill", "global"] = "skill"
    runtime: MCPRuntime
    environment: dict[str, MCPEnvironmentBinding] = Field(default_factory=dict)


@dataclass(frozen=True)
class MCPLaunchCandidate:
    """One fully resolved launch whose binding excludes secret values."""

    descriptor: MCPDescriptor
    binding_hash: str
    resolved_command: str
    args: tuple[str, ...]
    cwd: str
    env: dict[str, str]
    env_names: tuple[str, ...]

    def to_server_spec(self) -> MCPServerSpec:
        return MCPServerSpec(
            name=self.descriptor.id,
            family=self.descriptor.family,
            command=self.resolved_command,
            args=list(self.args),
            env=dict(self.env),
            cwd=self.cwd,
            sanitize_stdout=False,
            dropin=True,
        )


def validate_mcp_descriptor(
    data: Mapping[str, Any],
    *,
    extension_id: str,
) -> MCPDescriptor:
    try:
        descriptor = MCPDescriptor.model_validate(data)
    except ValidationError as exc:
        raise MCPManifestError(f"invalid MCP descriptor: {exc}") from exc
    if descriptor.id != extension_id:
        raise MCPManifestError("MCP descriptor ID must equal folder ID")
    if not _NAME_RE.fullmatch(descriptor.id):
        raise MCPManifestError("invalid MCP ID")
    if not _NAME_RE.fullmatch(descriptor.family):
        raise MCPManifestError("invalid MCP family")
    if descriptor.id.casefold() in _RESERVED_MCP_IDENTIFIERS:
        raise MCPManifestError("MCP ID is reserved by a built-in server")
    if descriptor.family.casefold() in _RESERVED_MCP_IDENTIFIERS:
        raise MCPManifestError("MCP family is reserved by a built-in server")
    for name, binding in descriptor.environment.items():
        if not _ENV_RE.fullmatch(name):
            raise MCPManifestError(f"invalid environment name: {name}")
        if binding.value is not None and any(
            hint in name.upper() for hint in _SECRET_HINTS
        ):
            raise MCPManifestError(
                f"literal value is forbidden for secret-like variable: {name}"
            )
    return descriptor


def descriptor_for_bundle(
    bundle: Path,
    *,
    extension_id: str,
    proposal: Mapping[str, Any] | None,
) -> MCPDescriptor:
    """Use strict extension.yaml, or a model proposal only when it is absent."""
    manifest_path = bundle / "extension.yaml"
    if manifest_path.exists():
        if manifest_path.is_symlink() or not manifest_path.is_file():
            raise MCPManifestError("extension.yaml is not a regular file")
        try:
            data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, yaml.YAMLError) as exc:
            raise MCPManifestError(f"extension.yaml is unreadable: {exc}") from exc
        if not isinstance(data, Mapping):
            raise MCPManifestError("extension.yaml must be a mapping")
        return validate_mcp_descriptor(data, extension_id=extension_id)
    if proposal is None:
        raise MCPManifestError(
            "MCP has no extension.yaml and manager supplied no unique proposal"
        )
    return validate_mcp_descriptor(proposal, extension_id=extension_id)


def _contained(bundle: Path, raw: str, *, kind: str) -> Path:
    path = Path(raw)
    if path.is_absolute():
        raise MCPManifestError(f"{kind} must be relative to the MCP bundle")
    resolved = (bundle / path).resolve()
    if not resolved.is_relative_to(bundle.resolve()):
        raise MCPManifestError(f"{kind} escapes the MCP bundle")
    return resolved


def _resolve_command(
    descriptor: MCPDescriptor,
    bundle: Path,
) -> tuple[str, str]:
    raw = descriptor.runtime.command
    if Path(raw).is_absolute():
        raise MCPManifestError("absolute MCP command is not allowed")
    if "/" in raw or "\\" in raw or raw.startswith("."):
        path = _contained(bundle, raw, kind="command")
        if not path.is_file() or path.is_symlink():
            raise MCPManifestError("bundle command is missing or not regular")
        if os.name != "nt" and not os.access(path, os.X_OK):
            raise MCPManifestError("bundle command is not executable")
        rel = path.relative_to(bundle.resolve()).as_posix()
        return str(path), f"bundle:{rel}"

    if raw not in _INTERPRETERS:
        allowed = ", ".join(sorted(_INTERPRETERS))
        raise MCPManifestError(
            f"external command {raw!r} is not an allowlisted interpreter ({allowed})"
        )
    resolved = shutil.which(raw)
    if not resolved:
        raise MCPManifestError(f"required interpreter is unavailable: {raw}")
    resolved_path = Path(resolved).resolve()
    try:
        metadata = resolved_path.stat()
    except OSError as exc:
        raise MCPManifestError(f"cannot inspect interpreter {raw}: {exc}") from exc

    script_arg = next(
        (arg for arg in descriptor.runtime.args if arg and not arg.startswith("-")),
        None,
    )
    if script_arg is None:
        raise MCPManifestError(
            "interpreter command requires an explicit bundle-relative script"
        )
    script = _contained(bundle, script_arg, kind="interpreter script")
    if not script.is_file() or script.is_symlink():
        raise MCPManifestError("interpreter script is missing or not regular")
    identity = (
        f"external:{resolved_path}:{metadata.st_size}:{metadata.st_mtime_ns}"
    )
    return str(resolved_path), identity


def _runtime_env(
    descriptor: MCPDescriptor,
    env: Mapping[str, str],
) -> dict[str, str]:
    child = {name: env[name] for name in _BASE_ENV if name in env}
    for target, binding in descriptor.environment.items():
        if binding.from_env is not None:
            value = env.get(binding.from_env)
            if value is None:
                if binding.required:
                    raise MCPManifestError(
                        f"required environment variable is missing: {binding.from_env}"
                    )
                continue
            child[target] = value
        else:
            child[target] = binding.value or ""
    return child


def resolve_mcp_candidate(
    descriptor: MCPDescriptor,
    *,
    bundle: Path,
    source_hash: str,
    env: Mapping[str, str] | None = None,
) -> MCPLaunchCandidate:
    """Resolve direct argv/cwd/env and compute a secret-free approval binding."""
    bundle = bundle.resolve()
    command, command_identity = _resolve_command(descriptor, bundle)
    cwd_path = _contained(bundle, descriptor.runtime.cwd, kind="cwd")
    if not cwd_path.is_dir() or cwd_path.is_symlink():
        raise MCPManifestError("MCP cwd is missing or not a regular directory")
    runtime_env = _runtime_env(
        descriptor,
        dict(os.environ) if env is None else env,
    )
    env_contract = {
        name: binding.model_dump(mode="json")
        for name, binding in sorted(descriptor.environment.items())
    }
    binding_payload = {
        "source_hash": source_hash,
        "command_identity": command_identity,
        "args": descriptor.runtime.args,
        "cwd": descriptor.runtime.cwd,
        "environment": env_contract,
        "family": descriptor.family,
        "scope": descriptor.scope,
    }
    binding_hash = hashlib.sha256(
        json.dumps(
            binding_payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return MCPLaunchCandidate(
        descriptor=descriptor,
        binding_hash=binding_hash,
        resolved_command=command,
        args=tuple(descriptor.runtime.args),
        cwd=str(cwd_path),
        env=runtime_env,
        env_names=tuple(sorted(descriptor.environment)),
    )
