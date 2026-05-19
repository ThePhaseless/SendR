# SendR Backend

The backend has two runtime roles:

- API server: serves FastAPI endpoints
- Scan worker: polls queued uploads and performs async malware scanning

Both roles use the same application code and should point at the same database and storage backend.

## Runtime Commands

From the `backend/` directory:

```bash
uv run uvicorn src.app:app --host 0.0.0.0 --port 8000
uv run python src/scan_worker.py
```

The API process runs database migrations during startup. The worker also runs migrations before polling the queue, then loops on queued uploads.

## Async Scan Requirements

If malware scanning is enabled, configure both runtime roles with the same values for:

- `SENDR_DATABASE_URL`
- `SENDR_UPLOAD_DIR`
- `SENDR_UPLOAD_QUARANTINE_DIR`
- `SENDR_SPACES_ACCESS_KEY`, `SENDR_SPACES_SECRET_KEY`, `SENDR_SPACES_BUCKET_NAME`, and `SENDR_SPACES_REGION` when object storage is enabled
- `SENDR_VIRUS_SCANNING_ENABLED`
- `SENDR_CLAMAV_HOST` and `SENDR_CLAMAV_PORT`, or `SENDR_CLAMAV_UNIX_SOCKET`

ClamAV should run as a separate daemon or container. The backend image is not expected to bundle ClamAV or its definition updates.

## Operational Notes

- The API does not launch the scan worker automatically.
- Queued and scanning payloads live in the quarantine directory for local-disk deployments. When Spaces is enabled, the queued payload remains in object storage and the worker downloads a temporary local copy for scanning.
- Infected payloads are deleted immediately and only their metadata remains in the database.
- Failed scan payloads remain blocked until an operator decides how to recover them.
