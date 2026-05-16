#!/usr/bin/env python3
"""Compatibility wrapper for the canonical AnyRouter check-in CLI."""

from __future__ import annotations

import sys
from pathlib import Path


SRC_DIR = Path(__file__).resolve().parent / 'python' / 'src'
if str(SRC_DIR) not in sys.path:
	sys.path.insert(0, str(SRC_DIR))

from cli.checkin import *  # noqa: F401,F403
from cli.checkin import run_main


if __name__ == '__main__':
	run_main()
