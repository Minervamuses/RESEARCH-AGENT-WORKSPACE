"""Test-only backend entry: the real server ``main`` serving the isolated fixture.

Crash-recovery tests start this file as a child process instead of the
production module, so production code carries no fixture switch.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.desktop import server  # noqa: E402
from support.fixture_session import build_phase02_fixture_service  # noqa: E402


def _build_fixture_service(original_cwd: Path):
    return build_phase02_fixture_service(original_cwd=original_cwd, environ=os.environ)


if __name__ == "__main__":
    server.main(build_service=_build_fixture_service)
