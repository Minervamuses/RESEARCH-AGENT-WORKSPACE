import subprocess
from pathlib import Path


def main() -> int:
    """Launch the existing Tauri desktop GUI."""
    desktop_dir = Path(__file__).resolve().parent / "app" / "desktop"
    return subprocess.run(
        ["npm", "run", "tauri", "dev"],
        cwd=desktop_dir,
        check=False,
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
