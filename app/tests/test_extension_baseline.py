"""Characterization tests for the pre-extension startup contract."""

from agent.cli.slash_commands import build_default_registry
from agent.config import AgentConfig
from agent.extensions.discovery import scan_extensions
from agent.skills import discover_skills


def test_private_management_skill_is_not_publicly_discovered():
    names = {skill.name for skill in discover_skills(None)}

    assert {"_prompt-master", "academic-paper-writing", "citation"} <= names
    assert "extension-management" not in names


def test_default_slash_commands_use_case_insensitive_local_lookup():
    registry = build_default_registry()

    assert registry.get("STATUS") is registry.get("status")
    assert registry.get("SKILL") is registry.get("skill")
    assert registry.get("Extension-Management") is registry.get(
        "extension-management"
    )


def test_skill_scan_ignores_only_regular_zip_sources(tmp_path):
    root = tmp_path / "dropins"
    skill_root = root / "skill"
    writer = skill_root / "writer"
    writer.mkdir(parents=True)
    (writer / "SKILL.md").write_text(
        "---\nname: writer\ndescription: Example\n---\n\nWrite clearly.\n",
        encoding="utf-8",
    )
    archive = skill_root / "pending.ZIP"
    archive.write_bytes(b"PK\x05\x06" + b"\x00" * 18)
    (skill_root / "notes.txt").write_text("not a skill", encoding="utf-8")
    (skill_root / "invalid.zip").mkdir()
    (skill_root / "linked.zip").symlink_to(archive)
    mcp_root = root / "mcp"
    mcp_root.mkdir()
    (mcp_root / "pending.zip").write_bytes(archive.read_bytes())

    scan = scan_extensions(root, config=AgentConfig())

    assert set(scan.items) == {
        "skill:writer", "skill:notes.txt", "skill:invalid.zip",
        "skill:linked.zip", "mcp:pending.zip",
    }
    assert scan.items["skill:writer"].valid is True
    assert all(not item.valid for key, item in scan.items.items() if key != "skill:writer")
    assert archive.read_bytes() == b"PK\x05\x06" + b"\x00" * 18
