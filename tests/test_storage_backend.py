import os
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services.storage_backend import (
    GCSStorageBackend,
    LocalStorageBackend,
    get_storage_backend,
)


class TestLocalStorageBackend(unittest.TestCase):
    def test_public_url_with_default_prefix(self) -> None:
        backend = LocalStorageBackend()
        self.assertEqual(
            backend.public_url("abc/p01.png"),
            "/static/outputs/abc/p01.png",
        )

    def test_public_url_with_custom_prefix(self) -> None:
        backend = LocalStorageBackend(static_prefix="https://cdn.example.com")
        self.assertEqual(
            backend.public_url("abc/p01.png"),
            "https://cdn.example.com/abc/p01.png",
        )

    def test_public_url_strips_leading_slash_from_relative_path(self) -> None:
        backend = LocalStorageBackend()
        self.assertEqual(
            backend.public_url("/abc/p01.png"),
            "/static/outputs/abc/p01.png",
        )

    def test_upload_returns_public_url_without_side_effects(self) -> None:
        backend = LocalStorageBackend()
        result = backend.upload(Path("/tmp/f.wav"), "abc/f.wav")
        self.assertEqual(result, backend.public_url("abc/f.wav"))


class TestGCSStorageBackend(unittest.TestCase):
    def test_public_url_without_prefix(self) -> None:
        backend = GCSStorageBackend(bucket="my-bucket")
        self.assertEqual(
            backend.public_url("abc/p01.png"),
            "https://storage.googleapis.com/my-bucket/abc/p01.png",
        )

    def test_public_url_with_key_prefix(self) -> None:
        backend = GCSStorageBackend(bucket="b", key_prefix="stories")
        self.assertEqual(
            backend.public_url("abc/p01.png"),
            "https://storage.googleapis.com/b/stories/abc/p01.png",
        )

    def test_public_url_strips_leading_slash_from_relative_path(self) -> None:
        backend = GCSStorageBackend(bucket="my-bucket")
        self.assertEqual(
            backend.public_url("/abc/p01.png"),
            "https://storage.googleapis.com/my-bucket/abc/p01.png",
        )

    def test_upload_uploads_file_and_returns_public_url(self) -> None:
        backend = GCSStorageBackend(bucket="my-bucket")
        with patch("app.services.storage_backend._build_gcs_client") as client_factory:
            result = backend.upload(Path("/tmp/f.wav"), "abc/f.wav")

        client = client_factory.return_value
        bucket = client.bucket.return_value
        blob = bucket.blob.return_value
        client.bucket.assert_called_once_with("my-bucket")
        bucket.blob.assert_called_once_with("abc/f.wav")
        blob.upload_from_filename.assert_called_once_with("/tmp/f.wav")
        self.assertEqual(result, "https://storage.googleapis.com/my-bucket/abc/f.wav")

    def test_delete_deletes_object(self) -> None:
        backend = GCSStorageBackend(bucket="my-bucket")
        with patch("app.services.storage_backend._build_gcs_client") as client_factory:
            backend.delete("abc/f.wav")

        bucket = client_factory.return_value.bucket.return_value
        bucket.blob.assert_called_once_with("abc/f.wav")
        bucket.blob.return_value.delete.assert_called_once()

    def test_upload_uses_key_prefix(self) -> None:
        backend = GCSStorageBackend(bucket="my-bucket", key_prefix="stories")
        with patch("app.services.storage_backend._build_gcs_client") as client_factory:
            result = backend.upload(Path("/tmp/f.wav"), "abc/f.wav")

        bucket = client_factory.return_value.bucket.return_value
        bucket.blob.assert_called_once_with("stories/abc/f.wav")
        self.assertEqual(
            result,
            "https://storage.googleapis.com/my-bucket/stories/abc/f.wav",
        )

    def test_upload_requires_bucket(self) -> None:
        backend = GCSStorageBackend(bucket="")
        with self.assertRaises(ValueError):
            backend.upload(Path("/tmp/f.wav"), "abc/f.wav")


class TestGetStorageBackend(unittest.TestCase):
    def test_default_returns_local_backend(self) -> None:
        env = {k: v for k, v in os.environ.items() if k != "MORETALE_STORAGE_BACKEND"}
        env["MORETALE_STORY_PAGE_COUNT"] = "3"
        with patch.dict(os.environ, env, clear=True):
            backend = get_storage_backend()
        self.assertIsInstance(backend, LocalStorageBackend)

    def test_local_env_returns_local_backend(self) -> None:
        with patch.dict(
            os.environ,
            {"MORETALE_STORAGE_BACKEND": "local", "MORETALE_STORY_PAGE_COUNT": "3"},
            clear=False,
        ):
            backend = get_storage_backend()
        self.assertIsInstance(backend, LocalStorageBackend)

    def test_gcs_env_returns_gcs_backend(self) -> None:
        with patch.dict(
            os.environ,
            {
                "MORETALE_STORAGE_BACKEND": "gcs",
                "MORETALE_GCS_BUCKET": "my-bucket",
                "MORETALE_GCS_KEY_PREFIX": "",
                "MORETALE_STORY_PAGE_COUNT": "3",
            },
            clear=False,
        ):
            backend = get_storage_backend()
        self.assertIsInstance(backend, GCSStorageBackend)

    def test_gcs_backend_has_correct_bucket(self) -> None:
        with patch.dict(
            os.environ,
            {
                "MORETALE_STORAGE_BACKEND": "gcs",
                "MORETALE_GCS_BUCKET": "my-bucket",
                "MORETALE_GCS_KEY_PREFIX": "",
                "MORETALE_STORY_PAGE_COUNT": "3",
            },
            clear=False,
        ):
            backend = get_storage_backend()
        self.assertIsInstance(backend, GCSStorageBackend)
        self.assertEqual(backend._bucket, "my-bucket")


if __name__ == "__main__":
    unittest.main()
