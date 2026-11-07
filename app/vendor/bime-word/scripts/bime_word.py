#!/usr/bin/env python3
"""Run from any working directory; resources are resolved relative to this file."""
from __future__ import annotations
import sys
if sys.version_info < (3,10):
    raise SystemExit('bime_word requires Python 3.10 or newer.')
try:
    from bime.cli import main
except ImportError as exc:
    raise SystemExit('Missing Python dependency. In an isolated environment, run: python -m pip install -r requirements.txt\n'+str(exc))
if __name__=='__main__':
    raise SystemExit(main())
