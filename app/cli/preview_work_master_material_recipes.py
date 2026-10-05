"""CLI for the fail-closed Work Master material recipe dry-run preview."""

import argparse
import json
from pathlib import Path
from typing import Sequence

from app.importers.work_master_material_recipe_preview import run_recipe_preview


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate Work Master material recipes without writing to the database."
    )
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--database-path", type=Path, required=True)
    parser.add_argument("--report-dir", type=Path, required=True)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Required safety acknowledgement; this command never applies changes.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.dry_run:
        parser.error("--dry-run is required; recipe import is not implemented")
    result = run_recipe_preview(
        file_path=args.file,
        project_id=args.project_id.strip(),
        database_path=args.database_path,
        report_dir=args.report_dir,
        repository_root=Path.cwd(),
    )
    print(json.dumps(result.summary, ensure_ascii=False, sort_keys=True))
    return 0 if result.summary["status"] == "PREVIEW_READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
