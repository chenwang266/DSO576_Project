"""Validated project settings: snapshot paths/dates, output directory, and analysis thresholds."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "project.json"
CONFIG_ENV = "LA_PRICING_CONFIG"


class ConfigError(ValueError):
    """Raised when project settings are missing or invalid."""


@dataclass(frozen=True)
class Snapshot:
    label: str
    date: str
    path: Path


@dataclass(frozen=True)
class Settings:
    snapshots: tuple[Snapshot, ...]
    processed_dir: Path
    min_priced_count: int = 20
    coverage_warning: float = 0.8
    small_sample_threshold: int = 20
    histogram_bins: int = 20
    unknown_bedroom_warning: float = 0.1
    default_selection: dict = field(default_factory=dict)

    @property
    def dates(self) -> tuple[str, ...]:
        return tuple(s.date for s in self.snapshots)

    @property
    def labels(self) -> dict[str, str]:
        return {s.date: s.label for s in self.snapshots}


def _resolve(path: str | Path, base: Path) -> Path:
    path = Path(path).expanduser()
    return path if path.is_absolute() else (base / path)


def validate_thresholds(min_priced_count: int, coverage_warning: float) -> None:
    if isinstance(min_priced_count, bool) or not isinstance(min_priced_count, int) or min_priced_count < 1:
        raise ConfigError(f"min_priced_count must be a positive integer, got {min_priced_count!r}")
    if isinstance(coverage_warning, bool) or not isinstance(coverage_warning, (int, float)) or not 0 <= coverage_warning <= 1:
        raise ConfigError(f"coverage_warning must be a fraction between 0 and 1, got {coverage_warning!r}")


def load_settings(path: str | Path | None = None, root: Path = ROOT) -> Settings:
    """Read config/project.json (or $LA_PRICING_CONFIG) and validate it. Relative paths resolve from the repo root."""
    path = Path(path or os.environ.get(CONFIG_ENV) or DEFAULT_CONFIG)
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}. Restore config/project.json or set {CONFIG_ENV}.")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ConfigError(f"{path} is not valid JSON: {error}") from error

    snapshots = raw.get("snapshots")
    if not isinstance(snapshots, list) or len(snapshots) != 2:
        raise ConfigError("Config must list exactly two snapshots (March and June).")
    parsed = []
    for item in snapshots:
        try:
            label, nominal, file = item["label"], item["date"], item["path"]
            date.fromisoformat(nominal)
        except (KeyError, TypeError, ValueError) as error:
            raise ConfigError(f"Invalid snapshot entry {item!r}: needs label, ISO date and path.") from error
        parsed.append(Snapshot(str(label), nominal, _resolve(file, root)))
    if parsed[0].date >= parsed[1].date:
        raise ConfigError("Snapshots must be listed in chronological order with distinct dates.")

    settings = Settings(
        snapshots=tuple(parsed),
        processed_dir=_resolve(raw.get("processed_dir", "data/processed"), root),
        min_priced_count=raw.get("min_priced_count", 20),
        coverage_warning=raw.get("coverage_warning", 0.8),
        small_sample_threshold=raw.get("small_sample_threshold", 20),
        histogram_bins=raw.get("histogram_bins", 20),
        unknown_bedroom_warning=raw.get("unknown_bedroom_warning", 0.1),
        default_selection=dict(raw.get("default_selection") or {}),
    )
    validate_thresholds(settings.min_priced_count, settings.coverage_warning)
    if not isinstance(settings.small_sample_threshold, int) or settings.small_sample_threshold < 1:
        raise ConfigError("small_sample_threshold must be a positive integer.")
    if not isinstance(settings.histogram_bins, int) or settings.histogram_bins < 1:
        raise ConfigError("histogram_bins must be a positive integer.")
    if not 0 <= settings.unknown_bedroom_warning <= 1:
        raise ConfigError("unknown_bedroom_warning must be a fraction between 0 and 1.")
    return settings
