"""Explicit project settings and configurable artifact location."""
import json
import os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
DATES = ("2026-03-16", "2026-06-15")
BEDROOM_ORDER = ["Studio", "1 bedroom", "2 bedroom", "3 bedroom", "4 bedroom", "5 bedroom", "6+ bedrooms"]

def settings():
    path = Path(os.environ.get("DSO576_CONFIG", ROOT / "config/project.json"))
    result = json.loads(path.read_text())
    if tuple(result["dates"]) != DATES:
        raise ValueError("Only March 16 and June 15, 2026 are supported.")
    validate_thresholds(result["min_priced"], result["coverage_warning"])
    return result

def validate_thresholds(min_priced, coverage_warning):
    if not isinstance(min_priced, int) or isinstance(min_priced, bool) or min_priced < 1:
        raise ValueError("Minimum priced count must be a positive integer.")
    if not 0 <= coverage_warning <= 1:
        raise ValueError("Coverage warning threshold must be between 0 and 1.")

def processed_dir():
    path = Path(os.environ.get("DSO576_PROCESSED_DIR", settings()["processed_dir"]))
    return path if path.is_absolute() else ROOT / path
