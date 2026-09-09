"""Command-line entry point for the unified Excel dry-run preview."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.importers.unified_excel_preview import run_preview


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Preview the unified Excel import without database writes")
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--database-path", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true", required=True)
    parser.add_argument("--report-dir", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run_preview(
            file_path=args.file,
            project_id=args.project_id,
            database_path=args.database_path,
            report_dir=args.report_dir,
        )
    except Exception as exc:
        print(f"Import preview failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"summary": result.summary, "reports": result.report_paths}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
