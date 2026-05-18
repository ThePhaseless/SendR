from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast

from sqlalchemy import delete, func, literal, text
from sqlmodel import select

from database import build_async_engine, create_session_factory
from db_migrations import run_migrations_for_url
from models import (
    AuthToken,
    DownloadLog,
    FileUpload,
    ScanStatus,
    Subscription,
    Transfer,
    UploadEmailRecipient,
    UploadGroupSettings,
    UploadPassword,
    User,
    UserLogin,
    VerificationCode,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from sqlmodel import SQLModel
    from sqlmodel.ext.asyncio.session import AsyncSession

BUNDLE_VERSION = 1
MANIFEST_FILENAME = "manifest.json"
TABLES_DIRNAME = "tables"
FILES_DIRNAME = "files"
FILES_MANIFEST_FILENAME = "files-manifest.ndjson"
DEFAULT_BATCH_SIZE = 250
StorageScope = Literal["clean", "quarantine", "absent"]


@dataclass(frozen=True, slots=True)
class TableSpec:
    model: type[SQLModel]
    file_stem: str
    order_by: str

    @property
    def table_name(self) -> str:
        return str(self.model.__table__.name)

    @property
    def filename(self) -> str:
        return f"{self.file_stem}.ndjson"


@dataclass(slots=True)
class ValidationIssue:
    severity: Literal["warning", "error"]
    code: str
    message: str
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }


@dataclass(slots=True)
class ValidationReport:
    database_url: str
    upload_dir: str
    quarantine_dir: str
    table_counts: dict[str, int]
    referenced_files: int
    issues: list[ValidationIssue]
    alembic_revision: str | None

    @property
    def error_count(self) -> int:
        return sum(issue.severity == "error" for issue in self.issues)

    @property
    def warning_count(self) -> int:
        return sum(issue.severity == "warning" for issue in self.issues)

    @property
    def has_errors(self) -> bool:
        return self.error_count > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "database_url": self.database_url,
            "upload_dir": self.upload_dir,
            "quarantine_dir": self.quarantine_dir,
            "table_counts": self.table_counts,
            "referenced_files": self.referenced_files,
            "alembic_revision": self.alembic_revision,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "issues": [issue.to_dict() for issue in self.issues],
        }


@dataclass(slots=True)
class ExportResult:
    bundle_dir: str
    manifest: dict[str, Any]
    validation_report: ValidationReport

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundle_dir": self.bundle_dir,
            "manifest": self.manifest,
            "validation_report": self.validation_report.to_dict(),
        }


@dataclass(slots=True)
class ImportResult:
    bundle_dir: str
    database_url: str
    upload_dir: str
    quarantine_dir: str
    imported_rows: dict[str, int]
    copied_files: int
    skipped_files: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundle_dir": self.bundle_dir,
            "database_url": self.database_url,
            "upload_dir": self.upload_dir,
            "quarantine_dir": self.quarantine_dir,
            "imported_rows": self.imported_rows,
            "copied_files": self.copied_files,
            "skipped_files": self.skipped_files,
        }


MODEL_SPECS: tuple[TableSpec, ...] = (
    TableSpec(User, "user", "id"),
    TableSpec(Subscription, "subscription", "id"),
    TableSpec(UserLogin, "userlogin", "id"),
    TableSpec(UploadGroupSettings, "uploadgroupsettings", "upload_group"),
    TableSpec(UploadPassword, "uploadpassword", "id"),
    TableSpec(UploadEmailRecipient, "uploademailrecipient", "id"),
    TableSpec(FileUpload, "fileupload", "id"),
    TableSpec(Transfer, "transfer", "id"),
    TableSpec(DownloadLog, "downloadlog", "id"),
)
EXCLUDED_TABLES: tuple[str, ...] = (
    AuthToken.__table__.name,
    VerificationCode.__table__.name,
)
INTEGER_ID_MODELS: tuple[type[SQLModel], ...] = (
    User,
    Subscription,
    UserLogin,
    UploadPassword,
    UploadEmailRecipient,
    FileUpload,
    Transfer,
    DownloadLog,
)


@dataclass(slots=True)
class FileReference:
    stored_filename: str
    content_hash: str | None
    expected_size_bytes: int
    file_upload_ids: list[int]
    active_file_upload_ids: list[int]
    scan_statuses: list[str]
    storage_scope: StorageScope
    present_on_source: bool
    actual_sha256: str | None
    actual_size_bytes: int | None

    def to_manifest_row(self) -> dict[str, Any]:
        return {
            "stored_filename": self.stored_filename,
            "content_hash": self.content_hash,
            "expected_size_bytes": self.expected_size_bytes,
            "actual_size_bytes": self.actual_size_bytes,
            "file_upload_ids": self.file_upload_ids,
            "active_file_upload_ids": self.active_file_upload_ids,
            "scan_statuses": self.scan_statuses,
            "storage_scope": self.storage_scope,
            "present_on_source": self.present_on_source,
            "sha256": self.actual_sha256,
        }


def _iso_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _serialize_json_line(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True)


def _normalize_quarantine_dir(upload_dir: Path, quarantine_dir: Path | None) -> Path:
    return upload_dir if quarantine_dir is None else quarantine_dir


def _clean_storage_path(upload_dir: Path, stored_filename: str) -> Path:
    return upload_dir / stored_filename


def _quarantine_storage_path(quarantine_dir: Path, stored_filename: str) -> Path:
    return quarantine_dir / stored_filename


def _storage_scope_path(
    upload_dir: Path,
    quarantine_dir: Path,
    stored_filename: str,
    storage_scope: StorageScope,
) -> Path | None:
    if storage_scope == "clean":
        return _clean_storage_path(upload_dir, stored_filename)
    if storage_scope == "quarantine":
        return _quarantine_storage_path(quarantine_dir, stored_filename)
    return None


def _entry_storage_scope(entry: dict[str, Any]) -> StorageScope:
    storage_scope = entry.get("storage_scope")
    if storage_scope in {"clean", "quarantine", "absent"}:
        return cast("StorageScope", storage_scope)
    return "clean" if bool(entry.get("present_on_source")) else "absent"


def _allowed_scopes_for_scan_status(scan_status: ScanStatus) -> set[StorageScope]:
    if scan_status == ScanStatus.clean:
        return {"clean"}
    if scan_status in (ScanStatus.queued, ScanStatus.scanning):
        return {"quarantine"}
    if scan_status == ScanStatus.infected:
        return {"absent"}
    return {"quarantine", "absent"}


def _resolve_expected_scopes(scan_statuses: set[ScanStatus]) -> set[StorageScope]:
    expected_scopes: set[StorageScope] | None = None
    for scan_status in scan_statuses:
        current = _allowed_scopes_for_scan_status(scan_status)
        expected_scopes = (
            current if expected_scopes is None else expected_scopes & current
        )
    return expected_scopes or {"absent"}


def _detect_storage_scope(
    upload_dir: Path,
    quarantine_dir: Path,
    stored_filename: str,
) -> tuple[StorageScope, Path | None, bool]:
    clean_path = _clean_storage_path(upload_dir, stored_filename)
    if upload_dir == quarantine_dir:
        if clean_path.exists():
            return "clean", clean_path, False
        return "absent", None, False

    quarantine_path = _quarantine_storage_path(quarantine_dir, stored_filename)
    clean_exists = clean_path.exists()
    quarantine_exists = quarantine_path.exists()

    if clean_exists and quarantine_exists:
        return "clean", clean_path, True
    if clean_exists:
        return "clean", clean_path, False
    if quarantine_exists:
        return "quarantine", quarantine_path, False
    return "absent", None, False


def _hash_file(file_path: Path) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


async def _count_rows(session: AsyncSession, spec: TableSpec) -> int:
    result = await session.exec(select(func.count()).select_from(spec.model))
    return int(result.one())


async def _get_alembic_revision(session: AsyncSession) -> str | None:
    try:
        result = await session.exec(text("SELECT version_num FROM alembic_version"))
    except Exception:
        return None

    row = result.first()
    if row is None:
        return None
    return str(row[0])


async def _collect_file_references(
    session: AsyncSession,
    upload_dir: Path,
    quarantine_dir: Path,
) -> tuple[list[FileReference], list[ValidationIssue], list[tuple[str, StorageScope]]]:
    result = await session.exec(select(FileUpload).order_by(FileUpload.id))
    uploads = list(result.all())
    references: dict[str, FileReference] = {}
    issues: list[ValidationIssue] = []

    for upload in uploads:
        if upload.id is None:
            raise RuntimeError("FileUpload must be persisted before migration")

        reference = references.get(upload.stored_filename)
        if reference is None:
            reference = FileReference(
                stored_filename=upload.stored_filename,
                content_hash=upload.content_hash,
                expected_size_bytes=upload.file_size_bytes,
                file_upload_ids=[upload.id],
                active_file_upload_ids=[upload.id] if upload.is_active else [],
                scan_statuses=[upload.scan_status.value],
                storage_scope="absent",
                present_on_source=False,
                actual_sha256=None,
                actual_size_bytes=None,
            )
            references[upload.stored_filename] = reference
            continue

        reference.file_upload_ids.append(upload.id)
        if upload.is_active:
            reference.active_file_upload_ids.append(upload.id)
        if upload.scan_status.value not in reference.scan_statuses:
            reference.scan_statuses.append(upload.scan_status.value)

        if reference.content_hash != upload.content_hash:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="INCONSISTENT_CONTENT_HASH",
                    message=(
                        "Rows sharing the same stored file disagree on content_hash."
                    ),
                    details={
                        "stored_filename": upload.stored_filename,
                        "file_upload_ids": reference.file_upload_ids,
                    },
                )
            )

        if reference.expected_size_bytes != upload.file_size_bytes:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="INCONSISTENT_FILE_SIZE",
                    message="Rows sharing the same stored file disagree on file size.",
                    details={
                        "stored_filename": upload.stored_filename,
                        "file_upload_ids": reference.file_upload_ids,
                    },
                )
            )

    upload_dir.mkdir(parents=True, exist_ok=True)
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    clean_files = sorted(
        entry.name for entry in upload_dir.iterdir() if entry.is_file()
    )
    quarantine_files = (
        []
        if quarantine_dir == upload_dir
        else sorted(entry.name for entry in quarantine_dir.iterdir() if entry.is_file())
    )
    referenced_names = set(references)
    orphan_files: list[tuple[str, StorageScope]] = [
        (name, "clean") for name in clean_files if name not in referenced_names
    ]
    orphan_files.extend(
        (name, "quarantine")
        for name in quarantine_files
        if name not in referenced_names
    )

    for orphan, storage_scope in orphan_files:
        issues.append(
            ValidationIssue(
                severity="warning",
                code="ORPHAN_UPLOAD_FILE",
                message=(
                    "Upload payload exists on disk without a matching FileUpload row."
                ),
                details={"stored_filename": orphan, "storage_scope": storage_scope},
            )
        )

    for reference in references.values():
        scan_statuses = {ScanStatus(status) for status in reference.scan_statuses}
        expected_scopes = _resolve_expected_scopes(scan_statuses)
        single_storage_root = upload_dir == quarantine_dir
        actual_scope, file_path, duplicate_payload = _detect_storage_scope(
            upload_dir,
            quarantine_dir,
            reference.stored_filename,
        )
        reference.storage_scope = actual_scope
        if single_storage_root and actual_scope != "absent":
            if expected_scopes == {"quarantine"}:
                reference.storage_scope = "quarantine"
            elif expected_scopes == {"absent"}:
                reference.storage_scope = "absent"
        if duplicate_payload:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="DUPLICATE_UPLOAD_PAYLOAD",
                    message=(
                        "Upload payload exists in both clean and quarantine storage."
                    ),
                    details={
                        "stored_filename": reference.stored_filename,
                        "clean_path": str(
                            _clean_storage_path(upload_dir, reference.stored_filename)
                        ),
                        "quarantine_path": str(
                            _quarantine_storage_path(
                                quarantine_dir, reference.stored_filename
                            )
                        ),
                    },
                )
            )

        if actual_scope == "absent" and actual_scope not in expected_scopes:
            if reference.active_file_upload_ids:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        code="MISSING_ACTIVE_UPLOAD_FILE",
                        message="Active upload references a missing payload file.",
                        details={
                            "stored_filename": reference.stored_filename,
                            "file_upload_ids": reference.file_upload_ids,
                            "active_file_upload_ids": reference.active_file_upload_ids,
                            "scan_statuses": reference.scan_statuses,
                            "expected_storage_scopes": sorted(expected_scopes),
                        },
                    )
                )
            else:
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        code="MISSING_INACTIVE_UPLOAD_FILE",
                        message="Inactive upload references a missing payload file.",
                        details={
                            "stored_filename": reference.stored_filename,
                            "file_upload_ids": reference.file_upload_ids,
                            "scan_statuses": reference.scan_statuses,
                            "expected_storage_scopes": sorted(expected_scopes),
                        },
                    )
                )

        if (
            not single_storage_root
            and actual_scope != "absent"
            and actual_scope not in expected_scopes
        ):
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="UPLOAD_STORAGE_SCOPE_MISMATCH",
                    message=(
                        "Upload payload is stored in the wrong directory for "
                        "its scan status."
                    ),
                    details={
                        "stored_filename": reference.stored_filename,
                        "actual_storage_scope": actual_scope,
                        "expected_storage_scopes": sorted(expected_scopes),
                        "scan_statuses": reference.scan_statuses,
                    },
                )
            )

        if file_path is None:
            continue

        actual_size = file_path.stat().st_size
        actual_sha256 = _hash_file(file_path)
        reference.present_on_source = True
        reference.actual_size_bytes = actual_size
        reference.actual_sha256 = actual_sha256

        if reference.expected_size_bytes != actual_size:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="FILE_SIZE_MISMATCH",
                    message="Stored file size does not match FileUpload metadata.",
                    details={
                        "stored_filename": reference.stored_filename,
                        "expected_size_bytes": reference.expected_size_bytes,
                        "actual_size_bytes": actual_size,
                    },
                )
            )

        if reference.content_hash and reference.content_hash != actual_sha256:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="CONTENT_HASH_MISMATCH",
                    message=(
                        "Stored file checksum does not match FileUpload.content_hash."
                    ),
                    details={
                        "stored_filename": reference.stored_filename,
                        "content_hash": reference.content_hash,
                        "actual_sha256": actual_sha256,
                    },
                )
            )

    return list(references.values()), issues, orphan_files


async def validate_source(
    database_url: str,
    upload_dir: Path,
    quarantine_dir: Path | None = None,
) -> ValidationReport:
    normalized_quarantine_dir = _normalize_quarantine_dir(upload_dir, quarantine_dir)
    engine = build_async_engine(database_url)
    session_factory = create_session_factory(engine)

    try:
        async with session_factory() as session:
            table_counts = {
                spec.table_name: await _count_rows(session, spec)
                for spec in MODEL_SPECS
            }
            alembic_revision = await _get_alembic_revision(session)
            file_references, issues, _orphan_files = await _collect_file_references(
                session, upload_dir, normalized_quarantine_dir
            )
    finally:
        await engine.dispose()

    return ValidationReport(
        database_url=database_url,
        upload_dir=str(upload_dir),
        quarantine_dir=str(normalized_quarantine_dir),
        table_counts=table_counts,
        referenced_files=len(file_references),
        issues=issues,
        alembic_revision=alembic_revision,
    )


async def _export_table(
    session: AsyncSession,
    spec: TableSpec,
    table_path: Path,
    batch_size: int,
) -> int:
    exported = 0
    offset = 0
    order_column = getattr(spec.model, spec.order_by)

    with table_path.open("w", encoding="utf-8") as handle:
        while True:
            stmt = (
                select(spec.model)
                .order_by(order_column)
                .offset(offset)
                .limit(batch_size)
            )
            result = await session.exec(stmt)
            rows = list(result.all())
            if not rows:
                break

            for row in rows:
                handle.write(_serialize_json_line(row.model_dump(mode="json")))
                handle.write("\n")

            exported += len(rows)
            offset += len(rows)

    return exported


def _ensure_bundle_paths(
    bundle_dir: Path, *, overwrite: bool = False
) -> tuple[Path, Path]:
    if bundle_dir.exists():
        has_existing_content = any(bundle_dir.iterdir())
        if has_existing_content and not overwrite:
            raise ValueError(f"Bundle directory is not empty: {bundle_dir}")
        if overwrite:
            shutil.rmtree(bundle_dir)

    bundle_dir.mkdir(parents=True, exist_ok=True)
    tables_dir = bundle_dir / TABLES_DIRNAME
    files_dir = bundle_dir / FILES_DIRNAME
    tables_dir.mkdir(parents=True, exist_ok=True)
    files_dir.mkdir(parents=True, exist_ok=True)
    return tables_dir, files_dir


async def export_bundle(
    database_url: str,
    upload_dir: Path,
    bundle_dir: Path,
    *,
    quarantine_dir: Path | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    overwrite: bool = False,
) -> ExportResult:
    normalized_quarantine_dir = _normalize_quarantine_dir(upload_dir, quarantine_dir)
    validation_report = await validate_source(
        database_url,
        upload_dir,
        normalized_quarantine_dir,
    )
    if validation_report.has_errors:
        raise ValueError("Source validation failed; export aborted.")

    tables_dir, files_dir = _ensure_bundle_paths(bundle_dir, overwrite=overwrite)
    engine = build_async_engine(database_url)
    session_factory = create_session_factory(engine)

    try:
        async with session_factory() as session:
            table_manifest: dict[str, dict[str, Any]] = {}
            for spec in MODEL_SPECS:
                table_path = tables_dir / spec.filename
                row_count = await _export_table(session, spec, table_path, batch_size)
                table_manifest[spec.table_name] = {
                    "file": str(Path(TABLES_DIRNAME) / spec.filename),
                    "rows": row_count,
                }

            file_references, _, _ = await _collect_file_references(
                session,
                upload_dir,
                normalized_quarantine_dir,
            )
    finally:
        await engine.dispose()

    copied_files = 0
    files_manifest_path = bundle_dir / FILES_MANIFEST_FILENAME
    with files_manifest_path.open("w", encoding="utf-8") as handle:
        for reference in sorted(file_references, key=lambda item: item.stored_filename):
            if reference.present_on_source:
                source_path = _storage_scope_path(
                    upload_dir,
                    normalized_quarantine_dir,
                    reference.stored_filename,
                    reference.storage_scope,
                )
                if source_path is None:
                    raise RuntimeError(
                        "Source payload path could not be resolved for a present file."
                    )
                destination_path = files_dir / reference.stored_filename
                shutil.copy2(source_path, destination_path)
                copied_files += 1

            handle.write(_serialize_json_line(reference.to_manifest_row()))
            handle.write("\n")

    manifest = {
        "bundle_version": BUNDLE_VERSION,
        "exported_at": _iso_now(),
        "source_database_dialect": database_url.split(":", maxsplit=1)[0],
        "source_upload_dir": str(upload_dir),
        "source_quarantine_dir": str(normalized_quarantine_dir),
        "alembic_revision": validation_report.alembic_revision,
        "tables": table_manifest,
        "excluded_tables": list(EXCLUDED_TABLES),
        "files": {
            "manifest": FILES_MANIFEST_FILENAME,
            "payload_dir": FILES_DIRNAME,
            "referenced": len(file_references),
            "copied": copied_files,
        },
        "validation": {
            "warning_count": validation_report.warning_count,
            "error_count": validation_report.error_count,
        },
    }
    manifest_path = bundle_dir / MANIFEST_FILENAME
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )

    return ExportResult(
        bundle_dir=str(bundle_dir),
        manifest=manifest,
        validation_report=validation_report,
    )


def _load_manifest(bundle_dir: Path) -> dict[str, Any]:
    manifest_path = bundle_dir / MANIFEST_FILENAME
    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing bundle manifest: {manifest_path}")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"Expected JSON object in {path}")
            yield payload


async def _ensure_target_is_empty(session: AsyncSession) -> None:
    for spec in MODEL_SPECS:
        count = await _count_rows(session, spec)
        if count > 0:
            raise ValueError(
                "Target database is not empty; table "
                f"{spec.table_name} already has {count} rows."
            )

    result = await session.exec(select(func.count()).select_from(AuthToken))
    if int(result.one()) > 0:
        raise ValueError("Target database already contains auth tokens.")

    result = await session.exec(select(func.count()).select_from(VerificationCode))
    if int(result.one()) > 0:
        raise ValueError("Target database already contains verification codes.")


def _ensure_storage_directories_are_empty(
    upload_dir: Path,
    quarantine_dir: Path,
) -> None:
    existing_upload_entries = sorted(entry.name for entry in upload_dir.iterdir())
    if existing_upload_entries:
        raise ValueError(f"Target upload directory is not empty: {upload_dir}")

    if quarantine_dir == upload_dir:
        return

    existing_quarantine_entries = sorted(
        entry.name for entry in quarantine_dir.iterdir()
    )
    if existing_quarantine_entries:
        raise ValueError(f"Target quarantine directory is not empty: {quarantine_dir}")


def _cleanup_copied_payloads(paths: list[Path]) -> None:
    for path in reversed(paths):
        if path.exists():
            path.unlink()


async def _import_table(
    session: AsyncSession,
    spec: TableSpec,
    table_path: Path,
    batch_size: int,
) -> int:
    inserted = 0
    batch: list[SQLModel] = []

    for payload in _iter_jsonl(table_path):
        batch.append(spec.model.model_validate(payload))
        if len(batch) >= batch_size:
            session.add_all(batch)
            await session.flush()
            inserted += len(batch)
            batch.clear()

    if batch:
        session.add_all(batch)
        await session.flush()
        inserted += len(batch)

    return inserted


async def _reset_postgresql_sequences(session: AsyncSession) -> None:
    bind = session.get_bind()
    if bind is None or bind.dialect.name != "postgresql":
        return

    for model in INTEGER_ID_MODELS:
        table_name = model.__table__.name
        max_id = select(func.max(model.id)).scalar_subquery()
        has_rows = select(func.count()).select_from(model).scalar_subquery() > 0
        stmt = select(
            func.setval(
                func.pg_get_serial_sequence(literal(table_name), literal("id")),
                func.coalesce(max_id, 1),
                has_rows,
            )
        )
        await session.exec(stmt)

    await session.commit()


async def import_bundle(
    database_url: str,
    upload_dir: Path,
    bundle_dir: Path,
    *,
    quarantine_dir: Path | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    force: bool = False,
) -> ImportResult:
    manifest = _load_manifest(bundle_dir)
    if int(manifest.get("bundle_version", 0)) != BUNDLE_VERSION:
        raise ValueError("Unsupported bundle version.")

    normalized_quarantine_dir = _normalize_quarantine_dir(upload_dir, quarantine_dir)
    run_migrations_for_url(database_url)

    upload_dir.mkdir(parents=True, exist_ok=True)
    normalized_quarantine_dir.mkdir(parents=True, exist_ok=True)
    if not force:
        _ensure_storage_directories_are_empty(upload_dir, normalized_quarantine_dir)

    engine = build_async_engine(database_url)
    session_factory = create_session_factory(engine)

    imported_rows: dict[str, int] = {}
    copied_files = 0
    skipped_files = 0
    copied_payload_paths: list[Path] = []
    session: AsyncSession | None = None

    try:
        async with session_factory() as session:
            if not force:
                await _ensure_target_is_empty(session)

            for spec in MODEL_SPECS:
                table_meta = manifest["tables"][spec.table_name]
                table_path = bundle_dir / str(table_meta["file"])
                imported_rows[spec.table_name] = await _import_table(
                    session,
                    spec,
                    table_path,
                    batch_size,
                )

            await session.exec(delete(AuthToken))
            await session.exec(delete(VerificationCode))
            files_payload_dir = bundle_dir / FILES_DIRNAME
            files_manifest_path = bundle_dir / FILES_MANIFEST_FILENAME
            for entry in _iter_jsonl(files_manifest_path):
                stored_filename = str(entry["stored_filename"])
                storage_scope = _entry_storage_scope(entry)
                if storage_scope == "absent":
                    skipped_files += 1
                    continue

                source_path = files_payload_dir / stored_filename
                if not source_path.exists():
                    raise FileNotFoundError(
                        f"Missing bundled file payload: {source_path}"
                    )

                destination_path = _storage_scope_path(
                    upload_dir,
                    normalized_quarantine_dir,
                    stored_filename,
                    storage_scope,
                )
                if destination_path is None:
                    raise RuntimeError(
                        "Target payload path could not be resolved for a bundled file."
                    )

                if destination_path.exists() and not force:
                    raise ValueError(
                        f"Target upload file already exists: {destination_path}"
                    )

                shutil.copy2(source_path, destination_path)
                copied_payload_paths.append(destination_path)
                copied_files += 1

            await session.commit()
            await _reset_postgresql_sequences(session)
    except Exception:
        if session is not None:
            await session.rollback()
        _cleanup_copied_payloads(copied_payload_paths)
        raise
    finally:
        await engine.dispose()

    return ImportResult(
        bundle_dir=str(bundle_dir),
        database_url=database_url,
        upload_dir=str(upload_dir),
        quarantine_dir=str(normalized_quarantine_dir),
        imported_rows=imported_rows,
        copied_files=copied_files,
        skipped_files=skipped_files,
    )


async def verify_target(
    database_url: str,
    upload_dir: Path,
    bundle_dir: Path,
    quarantine_dir: Path | None = None,
) -> ValidationReport:
    manifest = _load_manifest(bundle_dir)
    normalized_quarantine_dir = _normalize_quarantine_dir(upload_dir, quarantine_dir)
    report = await validate_source(database_url, upload_dir, normalized_quarantine_dir)
    issues = list(report.issues)

    for table_name, table_meta in cast(
        "dict[str, dict[str, Any]]", manifest["tables"]
    ).items():
        expected_rows = int(table_meta["rows"])
        actual_rows = report.table_counts.get(table_name)
        if actual_rows != expected_rows:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="ROW_COUNT_MISMATCH",
                    message="Target row count does not match the bundle manifest.",
                    details={
                        "table": table_name,
                        "expected_rows": expected_rows,
                        "actual_rows": actual_rows,
                    },
                )
            )

    engine = build_async_engine(database_url)
    session_factory = create_session_factory(engine)
    try:
        async with session_factory() as session:
            token_count = int(
                (await session.exec(select(func.count()).select_from(AuthToken))).one()
            )
            code_count = int(
                (
                    await session.exec(
                        select(func.count()).select_from(VerificationCode)
                    )
                ).one()
            )
    finally:
        await engine.dispose()

    if token_count > 0:
        issues.append(
            ValidationIssue(
                severity="error",
                code="AUTH_TOKENS_PRESENT",
                message="Target database still contains auth tokens after import.",
                details={"count": token_count},
            )
        )
    if code_count > 0:
        issues.append(
            ValidationIssue(
                severity="error",
                code="VERIFICATION_CODES_PRESENT",
                message=(
                    "Target database still contains verification codes after import."
                ),
                details={"count": code_count},
            )
        )

    files_manifest_path = bundle_dir / FILES_MANIFEST_FILENAME
    for entry in _iter_jsonl(files_manifest_path):
        stored_filename = str(entry["stored_filename"])
        expected_scope = _entry_storage_scope(entry)
        single_storage_root = upload_dir == normalized_quarantine_dir
        actual_scope, target_path, duplicate_payload = _detect_storage_scope(
            upload_dir,
            normalized_quarantine_dir,
            stored_filename,
        )
        if duplicate_payload:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="DUPLICATE_TARGET_UPLOAD_PAYLOAD",
                    message=(
                        "Target upload payload exists in both clean and "
                        "quarantine storage."
                    ),
                    details={"stored_filename": stored_filename},
                )
            )

        if expected_scope == "absent":
            if actual_scope != "absent":
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        code="UNEXPECTED_FILE_PRESENT",
                        message=(
                            "Target upload file exists even though source "
                            "bundle marked it missing."
                        ),
                        details={
                            "stored_filename": stored_filename,
                            "storage_scope": actual_scope,
                        },
                    )
                )
            continue

        if actual_scope == "absent" or target_path is None:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="MISSING_TARGET_UPLOAD_FILE",
                    message=(
                        "Bundled file payload is missing on the target upload "
                        "directory."
                    ),
                    details={
                        "stored_filename": stored_filename,
                        "expected_storage_scope": expected_scope,
                    },
                )
            )
            continue

        if actual_scope != expected_scope and not (
            single_storage_root
            and actual_scope != "absent"
            and expected_scope in {"clean", "quarantine"}
        ):
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="TARGET_FILE_LOCATION_MISMATCH",
                    message=(
                        "Target upload file exists, but in the wrong storage directory."
                    ),
                    details={
                        "stored_filename": stored_filename,
                        "expected_storage_scope": expected_scope,
                        "actual_storage_scope": actual_scope,
                    },
                )
            )
            continue

        expected_sha256 = entry.get("sha256")
        if isinstance(expected_sha256, str):
            actual_sha256 = _hash_file(target_path)
            if actual_sha256 != expected_sha256:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        code="TARGET_FILE_HASH_MISMATCH",
                        message=(
                            "Target upload file checksum does not match the "
                            "bundle manifest."
                        ),
                        details={
                            "stored_filename": stored_filename,
                            "expected_sha256": expected_sha256,
                            "actual_sha256": actual_sha256,
                        },
                    )
                )

    return ValidationReport(
        database_url=report.database_url,
        upload_dir=report.upload_dir,
        quarantine_dir=report.quarantine_dir,
        table_counts=report.table_counts,
        referenced_files=report.referenced_files,
        issues=issues,
        alembic_revision=report.alembic_revision,
    )
