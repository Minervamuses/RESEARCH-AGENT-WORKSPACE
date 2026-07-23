"""Source-checkout resource and drop-in-directory smoke tests."""

from agent.config import AgentConfig
from agent.extensions.discovery import scan_extensions
from agent.extensions.manager import default_private_skill_path
from agent.extensions.paths import resolve_extension_paths
from agent.paths import find_app_root


def test_source_checkout_has_default_dropin_dirs_and_private_skill():
    app_root = find_app_root()
    paths = resolve_extension_paths(AgentConfig())

    assert paths.dropin_root == (app_root / "tool").resolve()
    assert (paths.dropin_root / "skill").is_dir()
    assert (paths.dropin_root / "mcp").is_dir()
    assert (paths.dropin_root / "local" / "README.md").is_file()
    assert default_private_skill_path().is_file()


def test_checkout_placeholders_are_not_scanned_as_extensions(tmp_path):
    root = tmp_path / "tool"
    for kind in ("skill", "mcp"):
        folder = root / kind
        folder.mkdir(parents=True)
        (folder / ".gitkeep").write_text("", encoding="utf-8")
    config = AgentConfig(extension_dropin_dir=str(root))

    scan = scan_extensions(root, config=config)

    assert scan.items == {}
    assert scan.complete_for_delete is True
