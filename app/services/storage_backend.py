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


class LocalStorageBackend:
    """Serves files from local disk via FastAPI's StaticFiles mount."""

    def __init__(self, static_prefix: str = "/static/outputs") -> None:
        self._prefix = static_prefix.rstrip("/")

    def public_url(self, relative_path: str) -> str:
        rel = str(relative_path).lstrip("/")
        return f"{self._prefix}/{rel}"

    def upload(self, local_path: Path, relative_path: str) -> str:
        return self.public_url(relative_path)


class GCSStorageBackend:
    """Uploads files to Google Cloud Storage and returns public CDN URLs.

    TODO: install google-cloud-storage and set GOOGLE_APPLICATION_CREDENTIALS
          (or use Workload Identity in GKE) before enabling this backend.
    """

    def __init__(self, bucket: str, key_prefix: str = "") -> None:
        self._bucket = bucket
        self._prefix = key_prefix.strip("/")

    def public_url(self, relative_path: str) -> str:
        rel = str(relative_path).lstrip("/")
        key = f"{self._prefix}/{rel}" if self._prefix else rel
        return f"https://storage.googleapis.com/{self._bucket}/{key}"

    def upload(self, local_path: Path, relative_path: str) -> str:
        # TODO: uncomment once google-cloud-storage is added to requirements.txt
        #
        # from google.cloud import storage as gcs
        # client = gcs.Client()
        # bucket = client.bucket(self._bucket)
        # rel = str(relative_path).lstrip("/")
        # key = f"{self._prefix}/{rel}" if self._prefix else rel
        # blob = bucket.blob(key)
        # blob.upload_from_filename(str(local_path))
        # return self.public_url(relative_path)
        raise NotImplementedError("GCS upload not yet implemented")


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
