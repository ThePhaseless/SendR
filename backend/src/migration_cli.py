from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from config import settings
from migration_bundle import (
    export_bundle,
    import_bundle,
    validate_source,
    verify_target,
)


def _write_json(stream: Any, payload: dict[str, Any]) -> None:
    json.dump(payload, stream, indent=2, sort_keys=True)
    stream.write("\n")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export and import SendR data across different database engines."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser(
        "validate-source",
        help="Validate a source database and upload directory before export.",
    )
    _add_database_arguments(validate_parser)

    export_parser = subparsers.add_parser(
        "export-bundle",
        help="Create a portable migration bundle from a source database.",
    )
    _add_database_arguments(export_parser)
    export_parser.add_argument(
        "--bundle-dir",
        required=True,
        type=Path,
        help="Directory where the bundle should be written.",
    )
    export_parser.add_argument(
        "--batch-size",
        type=int,
        default=250,
        help="Row batch size used during export and import operations.",
    )
    export_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite an existing bundle directory.",
    )

    import_parser = subparsers.add_parser(
        "import-bundle",
        help="Import a previously exported bundle into a target database.",
    )
    _add_database_arguments(import_parser)
    import_parser.add_argument(
        "--bundle-dir",
        required=True,
        type=Path,
        help="Directory containing the bundle manifest and payloads.",
    )
    import_parser.add_argument(
        "--batch-size",
        type=int,
        default=250,
        help="Row batch size used during export and import operations.",
    )
    import_parser.add_argument(
        "--force",
        action="store_true",
        help="Allow importing into a non-empty target database and upload directory.",
    )

    verify_parser = subparsers.add_parser(
        "verify-target",
        help="Verify a target database and upload directory against a bundle.",
    )
    _add_database_arguments(verify_parser)
    verify_parser.add_argument(
        "--bundle-dir",
        required=True,
        type=Path,
        help="Directory containing the bundle manifest and payloads.",
    )

    return parser


def _add_database_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--database-url",
        default=settings.DATABASE_URL,
        help="Database URL for the source or target environment.",
    )
    parser.add_argument(
        "--upload-dir",
        default=Path(settings.UPLOAD_DIR),
        type=Path,
        help="Upload directory for the source or target environment.",
    )
    parser.add_argument(
        "--quarantine-dir",
        default=None,
        type=Path,
        help=(
            "Quarantine upload directory for queued, scanning, or failed payloads. "
            "Defaults to the upload directory when omitted."
        ),
    )


async def _run_command(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    command = str(args.command)

    if command == "validate-source":
        report = await validate_source(
            args.database_url,
            args.upload_dir,
            quarantine_dir=args.quarantine_dir,
        )
        return (1 if report.has_errors else 0), report.to_dict()

    if command == "export-bundle":
        result = await export_bundle(
            args.database_url,
            args.upload_dir,
            args.bundle_dir,
            quarantine_dir=args.quarantine_dir,
            batch_size=args.batch_size,
            overwrite=bool(args.overwrite),
        )
        return 0, result.to_dict()

    if command == "import-bundle":
        result = await import_bundle(
            args.database_url,
            args.upload_dir,
            args.bundle_dir,
            quarantine_dir=args.quarantine_dir,
            batch_size=args.batch_size,
            force=bool(args.force),
        )
        return 0, result.to_dict()

    if command == "verify-target":
        report = await verify_target(
            args.database_url,
            args.upload_dir,
            args.bundle_dir,
            quarantine_dir=args.quarantine_dir,
        )
        return (1 if report.has_errors else 0), report.to_dict()

    raise ValueError(f"Unsupported command: {command}")


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        exit_code, payload = asyncio.run(_run_command(args))
    except Exception as exc:
        _write_json(
            sys.stderr,
            {
                "error": {
                    "type": exc.__class__.__name__,
                    "message": str(exc),
                }
            },
        )
        return 1

    _write_json(sys.stdout, payload)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
