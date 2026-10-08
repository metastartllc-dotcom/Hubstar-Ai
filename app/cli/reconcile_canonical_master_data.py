"""Fail-closed CLI for canonical master-data reconciliation."""

import argparse
import json
from pathlib import Path
from typing import Sequence

from app.importers.canonical_master_data_reconciliation import run_reconciliation_preview


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare canonical workbook with production master data without writes.")
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--database-path", type=Path, required=True)
    parser.add_argument("--report-dir", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if not args.dry_run:
        parser.error("--dry-run is required; reconciliation never applies changes")
    result = run_reconciliation_preview(
        args.file, args.project_id.strip(), args.database_path, args.report_dir, Path.cwd()
    )
    print(json.dumps(result.summary, ensure_ascii=False, sort_keys=True))
    return 0 if result.summary["status"] == "PREVIEW_READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
