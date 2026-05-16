from __future__ import annotations

import os
import tempfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
TEMP_DIR = ROOT_DIR / 'test-tmp'

TEMP_DIR.mkdir(exist_ok=True)
os.environ.setdefault('TMP', str(TEMP_DIR))
os.environ.setdefault('TEMP', str(TEMP_DIR))
os.environ.setdefault('TMPDIR', str(TEMP_DIR))
tempfile.tempdir = str(TEMP_DIR)
