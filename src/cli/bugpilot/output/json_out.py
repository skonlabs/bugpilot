"""
JSON output formatter - outputs machine-readable JSON to stdout.
"""
from __future__ import annotations

import json
import sys
from typing import Any


def print_json(data: Any, indent: int = 2) -> None:
    """Serialize data to JSON and write to stdout."""
    sys.stdout.write(json.dumps(data, indent=indent, default=str) + "\n")
    sys.stdout.flush()


def print_error_json(message: str, code: int = 1) -> None:
    """Serialize an error to JSON and write to stderr."""
    import sys
    sys.stderr.write(json.dumps({"error": message, "code": code}) + "\n")
    sys.stderr.flush()
