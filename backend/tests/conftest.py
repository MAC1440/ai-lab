"""Shared pytest bootstrap for AI Lab backend tests.

The backend currently uses top-level imports such as ``services`` and
``routes``. Adding the backend directory to ``sys.path`` here keeps tests
consistent whether pytest is launched from the repository root or from the
backend directory.
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
