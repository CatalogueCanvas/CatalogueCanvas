"""CLI wrapper for the diagnostic report (see cataloguecanvas.diagnostics).

Usage:
    uv run python scripts/diagnostics.py            # print to stdout
    uv run python scripts/diagnostics.py report.md  # also write to a file
"""
from __future__ import annotations
import os
import sys
from pathlib import Path

if "CC_DATA_DIR" not in os.environ:
    default_data_dir = Path(__file__).resolve().parents[2] / "data"
    if default_data_dir.is_dir():
        os.environ["CC_DATA_DIR"] = str(default_data_dir)

from cataloguecanvas.diagnostics import build_report


def main() -> None:
    report = build_report()
    print(report)
    if len(sys.argv) > 1:
        target = Path(sys.argv[1])
        target.write_text(report)
        print(f"\nWritten to {target}", file=sys.stderr)


if __name__ == "__main__":
    main()
