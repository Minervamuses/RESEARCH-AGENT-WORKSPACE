"""Desktop knowledge slash commands /init, /ingest, /sync and /prune, and their path checks."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from agent.config import AgentConfig
from agent.cli.slash_commands import ParsedSlashCommand, SlashCommandResult
from agent.extensions.paths import resolve_extension_paths
from agent.ingest import diff_folder, ingest_file, ingest_folder, init_workspace, prune_folder
from agent.paths import find_app_root
from agent.session import ChatSession
from agent.skills import DEFAULT_SKILLS_DIR
from rag.collect import SKIP_DIRS, TEXT_EXTENSIONS
from agent.desktop.errors import DesktopServiceError
from agent.desktop.extension_ops import _MAX_LOCAL_COMMAND_BYTES


_WINDOWS_DRIVE = re.compile(r"^[A-Za-z]:[\\/]")


_EXTENSIONLESS_INGEST_FILES = {
    "Dockerfile",
    "Makefile",
    "Procfile",
    ".env.example",
    ".gitignore",
}


_MAX_KNOWLEDGE_RESULT_PATHS = 512


_MAX_KNOWLEDGE_PATH_BYTES = 4_096


@dataclass(frozen=True)
class DesktopKnowledgeOperations:
    """Concrete Python-owned knowledge calls injectable at the desktop edge."""

    init_workspace: Callable[
        [AgentConfig],
        Awaitable[tuple[int, int, Path, set[str]]],
    ]
    ingest_file: Callable[
        [Path, AgentConfig],
        Awaitable[tuple[str, int]],
    ]
    ingest_folder: Callable[
        [Path, AgentConfig],
        Awaitable[tuple[int, int]],
    ]
    diff_folder: Callable[[Path, AgentConfig], Awaitable[dict[str, Any]]]
    prune_folder: Callable[[Path, AgentConfig], Awaitable[list[str]]]


@dataclass(frozen=True)
class _PrunePreview:
    root: Path
    orphans: tuple[str, ...]
    digest: str


class _KnowledgeCommandOps:
    """DesktopService methods moved here unchanged; `self` is the DesktopService."""

    async def _execute_desktop_knowledge_command(
        self,
        session: ChatSession,
        parsed: ParsedSlashCommand,
    ) -> SlashCommandResult:
        method = {
            "init": "knowledge.init_workspace",
            "ingest": "knowledge.ingest_file",
            "sync": "knowledge.sync",
            "prune": (
                "knowledge.prune_apply"
                if parsed.args and parsed.args[-1] == "--yes"
                else "knowledge.prune_preview"
            ),
        }[parsed.name.casefold()]
        try:
            if parsed.name.casefold() == "init":
                return await self._desktop_init_command(parsed)
            if parsed.name.casefold() == "ingest":
                return await self._desktop_ingest_command(parsed)
            if parsed.name.casefold() == "sync":
                return await self._desktop_sync_command(parsed)
            return await self._desktop_prune_command(session, parsed)
        except DesktopServiceError:
            raise
        except Exception as exc:
            raise self._map_exception(method, exc) from exc

    async def _desktop_init_command(
        self,
        parsed: ParsedSlashCommand,
    ) -> SlashCommandResult:
        if parsed.args:
            raise DesktopServiceError(
                "PROTOCOL_INVALID",
                "/init takes no arguments.",
            )
        async with self._knowledge_operation(turn_owned=True):
            await self._require_operation_approval(
                "knowledge.init_workspace", str(find_app_root().parent),
                "Import the host workspace into the local knowledge index, excluding the app directory.",
                parameters={"storePath": str(Path(self.config.persist_dir).expanduser().resolve())},
            )
            files, chunks, host_root, excluded = (
                await self._knowledge_operations.init_workspace(self.config)
            )
        files = self._knowledge_count(files, "file")
        chunks = self._knowledge_count(chunks, "chunk")
        excluded_names = self._knowledge_string_items(excluded, "excluded name")
        root = self._bounded_text(str(host_root), _MAX_KNOWLEDGE_PATH_BYTES)
        excluded_text = ", ".join(excluded_names) or "none"
        return self._knowledge_result(
            (
                f"initialized: {files} files, {chunks} chunks "
                f"(root={root}, excluded {excluded_text})"
            ),
            mutation=True,
        )

    async def _desktop_ingest_command(
        self,
        parsed: ParsedSlashCommand,
    ) -> SlashCommandResult:
        if len(parsed.args) != 1:
            raise DesktopServiceError(
                "PROTOCOL_INVALID",
                "usage: /ingest <absolute-file-or-directory>",
            )
        target = self._validated_path(
            parsed.args[0],
            kind="file-or-directory",
            destructive_root=True,
        )
        if target.is_file():
            if (
                target.suffix.lower() not in TEXT_EXTENSIONS
                and target.name not in _EXTENSIONLESS_INGEST_FILES
            ):
                raise DesktopServiceError(
                    "INVALID_PATH",
                    "The selected file type is not supported for ingest.",
                )
            async with self._knowledge_operation(turn_owned=True):
                await self._require_operation_approval(
                    "knowledge.ingest_file", str(target), "Import this file into the local knowledge index.",
                    parameters={"storePath": str(Path(self.config.persist_dir).expanduser().resolve())},
                )
                pid, chunks = await self._knowledge_operations.ingest_file(
                    target,
                    self.config,
                )
            chunks = self._knowledge_count(chunks, "chunk")
            if chunks == 0:
                raise DesktopServiceError(
                    "RAG_WRITE_FAILED",
                    "The selected file contains no indexable UTF-8 text.",
                    details={"partialWritePossible": True},
                )
            safe_pid = self._bounded_text(str(pid), _MAX_KNOWLEDGE_PATH_BYTES)
            if not safe_pid:
                raise DesktopServiceError(
                    "RAG_WRITE_FAILED",
                    "The ingest operation returned no document identifier.",
                    details={"partialWritePossible": True},
                )
            return self._knowledge_result(
                f"ingested {safe_pid} ({chunks} chunks)",
                mutation=True,
            )

        async with self._knowledge_operation(turn_owned=True):
            await self._require_operation_approval(
                "knowledge.ingest_folder", str(target), "Import this directory into the local knowledge index.",
                parameters={"storePath": str(Path(self.config.persist_dir).expanduser().resolve())},
            )
            files, chunks = await self._knowledge_operations.ingest_folder(
                target,
                self.config,
            )
        files = self._knowledge_count(files, "file")
        chunks = self._knowledge_count(chunks, "chunk")
        return self._knowledge_result(
            f"ingested {files} files ({chunks} chunks) under {target}",
            mutation=True,
        )

    async def _desktop_sync_command(
        self,
        parsed: ParsedSlashCommand,
    ) -> SlashCommandResult:
        if len(parsed.args) != 1:
            raise DesktopServiceError(
                "PROTOCOL_INVALID",
                "usage: /sync <absolute-directory>",
            )
        target = self._validated_path(
            parsed.args[0],
            kind="directory",
            destructive_root=True,
        )
        async with self._knowledge_operation(turn_owned=True):
            diff = await self._knowledge_operations.diff_folder(target, self.config)
        missing_store, missing_disk = self._knowledge_diff_paths(diff)
        return self._knowledge_result(
            self._render_knowledge_diff(
                target,
                missing_store,
                missing_disk,
            )
        )

    async def _desktop_prune_command(
        self,
        session: ChatSession,
        parsed: ParsedSlashCommand,
    ) -> SlashCommandResult:
        apply = len(parsed.args) == 2 and parsed.args[1] == "--yes"
        if len(parsed.args) not in {1, 2} or (
            len(parsed.args) == 2 and not apply
        ):
            raise DesktopServiceError(
                "PROTOCOL_INVALID",
                "usage: /prune <absolute-directory> [--yes]",
            )
        target = self._validated_path(
            parsed.args[0],
            kind="directory",
            destructive_root=True,
        )
        if not apply:
            async with self._knowledge_operation(turn_owned=True):
                diff = await self._knowledge_operations.diff_folder(
                    target,
                    self.config,
                )
            _missing_store, orphans = self._knowledge_diff_paths(diff)
            preview = _PrunePreview(
                root=target,
                orphans=orphans,
                digest=self._prune_digest(target, orphans),
            )
            lines = [
                f"Would prune {len(orphans)} orphaned path(s) under {target}:"
            ]
            lines.extend(f"  - {path}" for path in orphans)
            if not orphans:
                lines.append("  (none)")
            lines.append("Re-run the same command with --yes to apply.")
            result = self._knowledge_result("\n".join(lines))
            self._composer_prune_preview = (session.session_id, preview)
            turn = self._running_turn
            if turn is None or turn.permission_mode != "bypass":
                return result

        stored = self._composer_prune_preview
        self._composer_prune_preview = None
        if (
            stored is None
            or stored[0] != session.session_id
            or stored[1].root != target
        ):
            raise DesktopServiceError(
                "PRUNE_PREVIEW_STALE",
                "Preview this exact directory before confirming prune.",
            )
        preview = stored[1]
        async with self._knowledge_operation(turn_owned=True):
            await self._require_operation_approval(
                "knowledge.prune_apply", str(target), "Prune these missing paths from the local knowledge index.",
                parameters={"orphans": list(preview.orphans), "storePath": str(Path(self.config.persist_dir).expanduser().resolve())},
            )
            latest = await self._knowledge_operations.diff_folder(
                target,
                self.config,
            )
            _missing_store, latest_orphans = self._knowledge_diff_paths(latest)
            if self._prune_digest(target, latest_orphans) != preview.digest:
                raise DesktopServiceError(
                    "PRUNE_PREVIEW_STALE",
                    "The orphan set changed; preview again before applying.",
                )
            removed = await self._knowledge_operations.prune_folder(
                target,
                self.config,
            )
        if isinstance(removed, (str, bytes)) or not isinstance(removed, (list, tuple)):
            raise DesktopServiceError(
                "RAG_WRITE_FAILED",
                "The prune operation returned an invalid result.",
                details={"partialWritePossible": True},
            )
        return self._knowledge_result(
            f"pruned {len(removed)} orphaned pid(s) under {target}",
            mutation=True,
        )

    @staticmethod
    def _knowledge_count(value: Any, label: str) -> int:
        if type(value) is not int or value < 0:
            raise DesktopServiceError(
                "RAG_WRITE_FAILED",
                f"The knowledge operation returned an invalid {label} count.",
                details={"partialWritePossible": True},
            )
        return value

    @staticmethod
    def _knowledge_result(
        message: str,
        *,
        mutation: bool = False,
    ) -> SlashCommandResult:
        if len(message.encode("utf-8")) > _MAX_LOCAL_COMMAND_BYTES:
            raise DesktopServiceError(
                "RAG_WRITE_FAILED" if mutation else "RAG_READ_FAILED",
                "The knowledge result is too large; choose a narrower directory.",
                details={"partialWritePossible": True} if mutation else None,
            )
        return SlashCommandResult(message=message)

    @staticmethod
    def _knowledge_string_items(values: Any, label: str) -> tuple[str, ...]:
        if isinstance(values, (str, bytes)) or not isinstance(
            values,
            (list, tuple, set, frozenset),
        ):
            raise DesktopServiceError(
                "RAG_READ_FAILED",
                f"The knowledge operation returned invalid {label} data.",
            )
        if len(values) > _MAX_KNOWLEDGE_RESULT_PATHS:
            raise DesktopServiceError(
                "RAG_READ_FAILED",
                "The knowledge result is too large; choose a narrower directory.",
            )
        normalized: list[str] = []
        for value in values:
            if not isinstance(value, str) or not value or "\x00" in value:
                raise DesktopServiceError(
                    "RAG_READ_FAILED",
                    f"The knowledge operation returned invalid {label} data.",
                )
            if len(value.encode("utf-8")) > _MAX_KNOWLEDGE_PATH_BYTES:
                raise DesktopServiceError(
                    "RAG_READ_FAILED",
                    "A knowledge result path exceeded the desktop limit.",
                )
            normalized.append(value)
        return tuple(sorted(set(normalized)))

    @classmethod
    def _knowledge_diff_paths(
        cls,
        diff: Any,
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        if not isinstance(diff, dict):
            raise DesktopServiceError(
                "RAG_READ_FAILED",
                "The knowledge comparison returned an invalid result.",
            )
        return (
            cls._knowledge_string_items(
                diff.get("missing_from_store"),
                "disk-only path",
            ),
            cls._knowledge_string_items(
                diff.get("missing_from_disk"),
                "store-only path",
            ),
        )

    @staticmethod
    def _render_knowledge_diff(
        target: Path,
        missing_store: tuple[str, ...],
        missing_disk: tuple[str, ...],
    ) -> str:
        lines = [
            f"Diff against {target}:",
            f"  on disk, not in store ({len(missing_store)}):",
        ]
        lines.extend(f"    + {path}" for path in missing_store)
        if not missing_store:
            lines.append("    (none)")
        lines.append(f"  in store, not on disk ({len(missing_disk)}):")
        lines.extend(f"    - {path}" for path in missing_disk)
        if not missing_disk:
            lines.append("    (none)")
        return "\n".join(lines)

    @staticmethod
    def _prune_digest(root: Path, orphans: tuple[str, ...]) -> str:
        payload = json.dumps(
            {"root": str(root), "orphans": list(orphans)},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @asynccontextmanager
    async def _knowledge_operation(self, *, turn_owned: bool = False):
        if self._knowledge_active or (self._turn_active and not turn_owned):
            raise DesktopServiceError(
                "BUSY_KNOWLEDGE_MUTATION",
                "Another knowledge mutation is active.",
                retryable=True,
            )
        self._knowledge_active = True
        try:
            yield
        finally:
            self._knowledge_active = False

    def _validated_path(
        self,
        raw: str,
        *,
        kind: str,
        destructive_root: bool = False,
    ) -> Path:
        if (
            not raw
            or _WINDOWS_DRIVE.match(raw)
            or raw.startswith("\\\\")
            or raw.startswith("//")
        ):
            raise DesktopServiceError(
                "INVALID_PATH", "Select an absolute Linux path."
            )
        candidate = Path(raw)
        if not candidate.is_absolute() or any(
            part.is_symlink() for part in (candidate, *candidate.parents)
        ):
            raise DesktopServiceError(
                "INVALID_PATH", "Select a non-symlink absolute Linux path."
            )
        try:
            resolved = candidate.resolve(strict=True)
        except (FileNotFoundError, OSError) as exc:
            raise DesktopServiceError(
                "INVALID_PATH", "The selected path does not exist."
            ) from exc
        if kind == "file" and not resolved.is_file():
            raise DesktopServiceError("INVALID_PATH", "The selected path is not a file.")
        if kind == "directory" and not resolved.is_dir():
            raise DesktopServiceError(
                "INVALID_PATH", "The selected path is not a directory."
            )
        if kind == "file-or-directory" and not (
            resolved.is_file() or resolved.is_dir()
        ):
            raise DesktopServiceError(
                "INVALID_PATH",
                "The selected path is not a file or directory.",
            )
        if destructive_root and resolved == Path(resolved.anchor):
            raise DesktopServiceError(
                "INVALID_PATH", "The filesystem root cannot be used here."
            )
        if any(part in SKIP_DIRS for part in resolved.parts):
            raise DesktopServiceError(
                "INVALID_PATH", "The selected path is under an excluded directory."
            )
        for protected in self._protected_roots():
            if (
                resolved == protected
                or resolved.is_relative_to(protected)
                or (resolved.is_dir() and protected.is_relative_to(resolved))
            ):
                raise DesktopServiceError(
                    "INVALID_PATH", "The selected path overlaps application state."
                )
        return resolved

    def _protected_roots(self) -> tuple[Path, ...]:
        extension_paths = resolve_extension_paths(self.config, env=self.environ)
        skills_root = (
            Path(self.config.skills_dir).expanduser().resolve()
            if self.config.skills_dir
            else DEFAULT_SKILLS_DIR.resolve()
        )
        roots = {
            Path(self.config.persist_dir).expanduser().resolve(),
            skills_root,
            extension_paths.dropin_root.resolve(),
            extension_paths.state_root.resolve(),
        }
        return tuple(sorted(roots, key=str))
