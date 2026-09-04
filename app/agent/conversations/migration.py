"""Non-destructive, conversation-atomic import from legacy history sources."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from agent.conversations.legacy import (
    LegacyChromaReader,
    LegacyConversationReader,
    LegacyConversationSnapshot,
    LegacyReadError,
    LegacySourceCount,
    legacy_turn_id,
)
from agent.conversations.legacy_plan import LegacyPlanLogReader
from agent.conversations.models import (
    SCHEMA_VERSION,
    ConversationConflictError,
    ConversationDocument,
    ConversationMalformedError,
    ConversationTooLargeError,
    ConversationTurn,
    ConversationUnavailableError,
    ConversationValidationError,
    validate_conversation_id,
    validate_project_id,
)
from agent.conversations.repository import (
    ConversationRepository,
    ConversationSnapshot,
)
from agent.config import AgentConfig
from agent.paths import find_app_root


MigrationStatus = Literal["created", "already_present", "skipped", "failed"]
MigrationReason = Literal[
    "canonical_publish_failed",
    "canonical_target_invalid",
    "legacy_read_failed",
    "legacy_source_changed",
    "no_legacy_turns",
]


@dataclass(frozen=True)
class MigrationResult:
    """Safe structured outcome for one legacy conversation import."""

    status: MigrationStatus
    reason: MigrationReason | None
    source_counts: tuple[LegacySourceCount, ...]
    turn_count: int
    dropped_activity_count: int


class ConversationMigrator:
    """Publish an unchanged, fully staged legacy snapshot exactly once."""

    def __init__(
        self,
        repository: ConversationRepository,
        reader: LegacyConversationReader,
    ) -> None:
        self._repository = repository
        self._reader = reader

    def import_conversation(
        self,
        conversation_id: str,
        project_id: str | None,
    ) -> MigrationResult:
        """Import one conversation without modifying any legacy source."""
        validated_id = validate_conversation_id(conversation_id)
        validated_project_id = validate_project_id(project_id)

        existing = self._load_existing(validated_id)
        if existing is not None:
            if existing.document.project_id != validated_project_id:
                return self._failed("canonical_target_invalid")
            return self._already_present(existing)
        if self._target_exists(validated_id):
            existing = self._load_existing(validated_id)
            if (
                existing is not None
                and existing.document.project_id == validated_project_id
            ):
                return self._already_present(existing)
            return self._failed("canonical_target_invalid")

        try:
            staged = self._reader.read(validated_id)
        except LegacyReadError:
            return self._failed("legacy_read_failed")

        document: ConversationDocument | None = None
        try:
            if staged.turns:
                document = self._to_document(staged, validated_project_id)
        except ConversationValidationError:
            return self._from_snapshot(
                staged,
                status="failed",
                reason="legacy_read_failed",
            )

        try:
            confirmed = self._reader.read(validated_id)
        except LegacyReadError:
            return self._failed("legacy_read_failed")
        if (
            staged.fingerprint != confirmed.fingerprint
            or staged != confirmed
        ):
            return self._from_snapshot(
                staged,
                status="failed",
                reason="legacy_source_changed",
            )
        if document is None:
            return self._from_snapshot(
                staged,
                status="skipped",
                reason="no_legacy_turns",
            )

        try:
            created = self._repository.create_document(document)
        except ConversationConflictError:
            return self._resolve_publish_race(
                staged,
                validated_id,
                validated_project_id,
            )
        except ConversationUnavailableError:
            return self._resolve_ambiguous_publish(
                staged,
                document,
                validated_id,
            )
        except (ConversationTooLargeError, ConversationValidationError):
            return self._from_snapshot(
                staged,
                status="failed",
                reason="canonical_publish_failed",
            )

        try:
            persisted = self._repository.load(validated_id)
        except (
            ConversationMalformedError,
            ConversationTooLargeError,
            ConversationUnavailableError,
        ):
            return self._resolve_ambiguous_publish(
                staged,
                document,
                validated_id,
            )
        if (
            persisted.document != document
            or persisted.fingerprint != created.fingerprint
        ):
            return self._from_snapshot(
                staged,
                status="failed",
                reason="canonical_publish_failed",
            )
        return self._from_snapshot(staged, status="created", reason=None)

    def _resolve_ambiguous_publish(
        self,
        staged: LegacyConversationSnapshot,
        expected: ConversationDocument,
        conversation_id: str,
    ) -> MigrationResult:
        existing = self._load_existing(conversation_id)
        if existing is not None and existing.document == expected:
            return self._from_snapshot(staged, status="created", reason=None)
        return self._from_snapshot(
            staged,
            status="failed",
            reason="canonical_publish_failed",
        )

    def _load_existing(
        self,
        conversation_id: str,
    ) -> ConversationSnapshot | None:
        try:
            return self._repository.load(conversation_id)
        except (
            ConversationMalformedError,
            ConversationTooLargeError,
            ConversationUnavailableError,
        ):
            return None

    def _target_exists(self, conversation_id: str) -> bool:
        target = self._repository.path_for(conversation_id)
        try:
            target.lstat()
        except FileNotFoundError:
            return False
        except OSError:
            return True
        return True

    def _resolve_publish_race(
        self,
        staged: LegacyConversationSnapshot,
        conversation_id: str,
        project_id: str | None,
    ) -> MigrationResult:
        existing = self._load_existing(conversation_id)
        if existing is None or existing.document.project_id != project_id:
            return self._from_snapshot(
                staged,
                status="failed",
                reason="canonical_target_invalid",
            )
        return MigrationResult(
            status="already_present",
            reason=None,
            source_counts=staged.source_counts,
            turn_count=len(existing.document.turns),
            dropped_activity_count=staged.dropped_activity_count,
        )

    @staticmethod
    def _already_present(existing: ConversationSnapshot) -> MigrationResult:
        return MigrationResult(
            status="already_present",
            reason=None,
            source_counts=(),
            turn_count=len(existing.document.turns),
            dropped_activity_count=0,
        )

    @staticmethod
    def _to_document(
        snapshot: LegacyConversationSnapshot,
        project_id: str | None,
    ) -> ConversationDocument:
        turns = tuple(
            ConversationTurn(
                turn_id=legacy_turn_id(snapshot.conversation_id, turn.turn_number),
                turn_number=turn.turn_number,
                kind="display-only",
                state="completed",
                display_input=turn.user_input,
                semantic_input=None,
                context_eligible=False,
                thinking_mode=None,
                submitted_at=turn.timestamp,
                finished_at=turn.timestamp,
                assistant_output=turn.assistant_output,
                tool_activities=(),
                failure=None,
            )
            for turn in snapshot.turns
        )
        timestamp_values = tuple(turn.timestamp for turn in snapshot.turns)
        created_at = min(timestamp_values, key=_parse_timestamp)
        updated_at = max(timestamp_values, key=_parse_timestamp)
        return ConversationDocument(
            schema_version=SCHEMA_VERSION,
            conversation_id=snapshot.conversation_id,
            project_id=project_id,
            created_at=created_at,
            updated_at=updated_at,
            turns=turns,
        )

    @staticmethod
    def _failed(reason: MigrationReason) -> MigrationResult:
        return MigrationResult(
            status="failed",
            reason=reason,
            source_counts=(),
            turn_count=0,
            dropped_activity_count=0,
        )

    @staticmethod
    def _from_snapshot(
        snapshot: LegacyConversationSnapshot,
        *,
        status: MigrationStatus,
        reason: MigrationReason | None,
    ) -> MigrationResult:
        return MigrationResult(
            status=status,
            reason=reason,
            source_counts=snapshot.source_counts,
            turn_count=len(snapshot.turns),
            dropped_activity_count=snapshot.dropped_activity_count,
        )


def create_legacy_migrator(
    config: AgentConfig,
    repository: ConversationRepository,
) -> ConversationMigrator:
    """Build the strict legacy readers only at an explicit migration boundary."""
    return ConversationMigrator(
        repository,
        LegacyConversationReader(
            chroma_read=LegacyChromaReader(config.persist_dir),
            plan_read=lambda conversation_id: LegacyPlanLogReader(
                config,
                session_id=conversation_id,
                app_root_resolver=lambda: find_app_root(),
            ).read_direct_answer_turns(),
        ),
    )


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.removesuffix("Z") + "+00:00")


__all__ = [
    "ConversationMigrator",
    "MigrationReason",
    "MigrationResult",
    "MigrationStatus",
    "create_legacy_migrator",
]
