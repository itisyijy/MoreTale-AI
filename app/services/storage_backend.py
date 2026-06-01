from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class StorageBackend(Protocol):
    """Public contract for all storage backends."""

    def public_url(self, relative_path: str) -> str:
        """Return a publicly accessible URL for the given relative path."""
        ...

    def upload(self, local_path: Path, relative_path: str) -> str:
        """Upload a local file and return its public URL.

        For local backend this is a no-op; the file is already on disk.
        For GCS backend this uploads the file to the configured bucket.
        """
        ...

    def delete(self, relative_path: str) -> None:
        """Delete a stored object when the backend supports deletion."""
        ...


class LocalStorageBackend:
    """Serves files from local disk via FastAPI's StaticFiles mount."""

    def __init__(self, static_prefix: str = "/static/outputs") -> None:
        self._prefix = static_prefix.rstrip("/")

    def public_url(self, relative_path: str) -> str:
        rel = str(relative_path).lstrip("/")
        return f"{self._prefix}/{rel}"

    def upload(self, local_path: Path, relative_path: str) -> str:
        return self.public_url(relative_path)

    def delete(self, relative_path: str) -> None:
        _ = relative_path


class GCSStorageBackend:
    """Uploads files to Google Cloud Storage and returns public CDN URLs.

    Uses Application Default Credentials. On Cloud Run, grant the service account
    permission to write objects to the configured bucket.
    """

    def __init__(self, bucket: str, key_prefix: str = "") -> None:
        self._bucket = bucket
        self._prefix = key_prefix.strip("/")

    def object_name(self, relative_path: str) -> str:
        rel = str(relative_path).lstrip("/")
        return f"{self._prefix}/{rel}" if self._prefix else rel

    def public_url(self, relative_path: str) -> str:
        return f"https://storage.googleapis.com/{self._bucket}/{self.object_name(relative_path)}"

    def upload(self, local_path: Path, relative_path: str) -> str:
        if not self._bucket:
            raise ValueError("MORETALE_GCS_BUCKET is required for GCS storage backend")

        client = _build_gcs_client()
        bucket = client.bucket(self._bucket)
        blob = bucket.blob(self.object_name(relative_path))
        blob.upload_from_filename(str(local_path))
        return self.public_url(relative_path)

    def delete(self, relative_path: str) -> None:
        if not self._bucket:
            raise ValueError("MORETALE_GCS_BUCKET is required for GCS storage backend")

        client = _build_gcs_client()
        bucket = client.bucket(self._bucket)
        blob = bucket.blob(self.object_name(relative_path))
        blob.delete()


def _build_gcs_client():
    from google.cloud import storage as gcs

    return gcs.Client()


def get_storage_backend() -> StorageBackend:
    """Return the configured storage backend (local or gcs)."""
    from app.core.config import get_settings

    settings = get_settings()
    if settings.storage_backend == "gcs":
        return GCSStorageBackend(
            bucket=settings.gcs_bucket,
            key_prefix=settings.gcs_key_prefix,
        )
    return LocalStorageBackend(static_prefix=settings.static_outputs_prefix)
