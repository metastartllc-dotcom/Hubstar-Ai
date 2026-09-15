"""Command-line entry point for unified preview and guarded apply modes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.importers.unified_excel_preview import run_preview
from app.importers.unified_excel_import import ImportPostCommitError, apply_unified_import


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Preview or apply the unified Excel master-data import")
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--database-path", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--report-dir", type=Path, required=True)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--expected-workbook-sha256")
    parser.add_argument("--expected-database-sha256")
    parser.add_argument("--backup-path", type=Path)
    parser.add_argument("--confirm")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.dry_run:
            result = run_preview(
                file_path=args.file,
                project_id=args.project_id,
                database_path=args.database_path,
                report_dir=args.report_dir,
            )
        else:
            required = {
                "--plan": args.plan,
                "--expected-workbook-sha256": args.expected_workbook_sha256,
                "--expected-database-sha256": args.expected_database_sha256,
                "--backup-path": args.backup_path,
                "--confirm": args.confirm,
            }
            missing = [name for name, value in required.items() if value is None]
            if missing:
                print(f"Import failed: required apply option missing: {missing[0]}", file=sys.stderr)
                return 2
            result = apply_unified_import(
                file_path=args.file, project_id=args.project_id,
                database_path=args.database_path, plan_path=args.plan,
                expected_workbook_sha256=args.expected_workbook_sha256,
                expected_database_sha256=args.expected_database_sha256,
                backup_path=args.backup_path, report_dir=args.report_dir,
                confirm=args.confirm,
            )
    except ImportPostCommitError as exc:
        print(json.dumps({"summary": exc.result.summary, "reports": []}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    except Exception as exc:
        label = "preview" if args.dry_run else "apply"
        print(f"Import {label} failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"summary": result.summary, "reports": result.report_paths}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
