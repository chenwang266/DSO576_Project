"""Build the canonical artifacts from the March and June raw listings.

    uv run python scripts/canonical_clean.py \
        --march data/raw/listings-2026-03-16.csv.gz --june data/raw/listings-2026-06-15.csv.gz \
        --output-dir data/processed

Arguments default to config/project.json.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.cleaning import CleaningError, run_cleaning  # noqa: E402
from src.config import ConfigError, load_settings  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=Path, help="Settings file (default: config/project.json)")
    parser.add_argument("--march", type=Path, help="March 2026-03-16 detailed listings .csv or .csv.gz")
    parser.add_argument("--june", type=Path, help="June 2026-06-15 detailed listings .csv or .csv.gz")
    parser.add_argument("--output-dir", type=Path, help="Directory for canonical artifacts")
    args = parser.parse_args(argv)
    try:
        settings = load_settings(args.config)
        march, june = settings.snapshots
        snapshots = (replace(march, path=args.march.resolve()) if args.march else march,
                     replace(june, path=args.june.resolve()) if args.june else june)
        output_dir = args.output_dir.resolve() if args.output_dir else settings.processed_dir
        report = run_cleaning(snapshots, output_dir, settings.small_sample_threshold)
    except (CleaningError, ConfigError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    print(f"Wrote canonical artifacts to {output_dir}")
    for item in report["inputs"]:
        print(f"  {item['label']} {item['nominal_date']}: {report['row_counts'][item['nominal_date']]:,} rows, "
              f"raw sha256 {item['sha256_before'][:12]}… unchanged={item['unchanged']}")
    for snap in report["snapshots"]:
        check = snap["reference_check"]
        if check:
            print(f"  {snap['label']} reference counts match: {check['matches']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
