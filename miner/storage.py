"""Storage Abstraction Layer for TUTUCO CLIP MINER.

Supports local filesystem storage and Google Cloud Storage (GCS).
Enforces private bucket storage with signed URLs for temporary access (NO make_public).
Falls back gracefully to local storage when Cloud credentials are not configured.
"""
from __future__ import annotations

import os
import shutil
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, BinaryIO, Dict, Optional


class BaseStorageService(ABC):
    """Abstract interface for storing and retrieving media assets."""

    @abstractmethod
    def store_file(
        self,
        file_obj: BinaryIO,
        filename: str,
        content_type: str = "video/mp4",
        category: str = "edited",
    ) -> Dict[str, Any]:
        """Save a file and return its metadata and access URL."""
        pass

    @abstractmethod
    def get_access_url(self, storage_path: str, expiration_minutes: int = 60) -> str:
        """Return a secure (signed or local) URL to access the file."""
        pass

    @abstractmethod
    def delete_file(self, storage_path: str) -> bool:
        """Delete an asset from storage."""
        pass

    @property
    @abstractmethod
    def is_cloud(self) -> bool:
        """Return True if backed by Cloud Storage."""
        pass

    @property
    def mode(self) -> str:
        """Return 'gcs' or 'local' mode string."""
        return "gcs" if self.is_cloud else "local"

    def save_edited_video(
        self,
        candidate_id: str,
        file_obj: BinaryIO,
        filename: str,
    ) -> Dict[str, Any]:
        """Convenience method to save an edited video for a candidate."""
        res = self.store_file(file_obj, filename, content_type="video/mp4", category="edited")
        return {
            "candidate_id": candidate_id,
            "filename": filename,
            "storage_mode": self.mode,
            "url": res["access_url"],
            "path": res.get("storage_path") or res.get("blob_name"),
            "blob_name": res.get("blob_name"),
            "file_size": res["file_size"],
            "created_at": res["created_at"],
            "expires_at": res["expires_at"],
        }


class LocalStorageService(BaseStorageService):
    """Local filesystem storage provider for offline and developer environments."""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir / "data" / "edited"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    @property
    def is_cloud(self) -> bool:
        return False

    def store_file(
        self,
        file_obj: BinaryIO,
        filename: str,
        content_type: str = "video/mp4",
        category: str = "edited",
    ) -> Dict[str, Any]:
        file_id = str(uuid.uuid4())
        safe_name = f"{file_id}_{Path(filename).name}"
        dest_path = self.base_dir / safe_name

        file_obj.seek(0)
        with open(dest_path, "wb") as f:
            shutil.copyfileobj(file_obj, f)

        file_size = dest_path.stat().st_size
        created_at = datetime.now(timezone.utc)
        expires_at = created_at + timedelta(days=30)

        return {
            "id": file_id,
            "filename": filename,
            "storage_path": str(dest_path),
            "relative_url": f"/media/edited/{safe_name}",
            "access_url": f"/media/edited/{safe_name}",
            "file_size": file_size,
            "content_type": content_type,
            "is_cloud": False,
            "created_at": created_at.isoformat(),
            "expires_at": expires_at.isoformat(),
        }

    def get_access_url(self, storage_path: str, expiration_minutes: int = 60) -> str:
        safe_name = Path(storage_path).name
        return f"/media/edited/{safe_name}"

    def delete_file(self, storage_path: str) -> bool:
        p = Path(storage_path)
        if p.is_file():
            p.unlink()
            return True
        return False


class GCSStorageService(BaseStorageService):
    """Google Cloud Storage provider with secure, private signed URLs."""

    def __init__(self, project_id: str, bucket_name: str, credentials_path: Optional[str] = None):
        from google.cloud import storage

        self.project_id = project_id
        self.bucket_name = bucket_name

        if credentials_path and Path(credentials_path).is_file():
            self.client = storage.Client.from_service_account_json(credentials_path, project=project_id)
        else:
            self.client = storage.Client(project=project_id)

        self.bucket = self.client.bucket(bucket_name)

    @property
    def is_cloud(self) -> bool:
        return True

    def store_file(
        self,
        file_obj: BinaryIO,
        filename: str,
        content_type: str = "video/mp4",
        category: str = "edited",
    ) -> Dict[str, Any]:
        file_id = str(uuid.uuid4())
        safe_name = f"{category}/{file_id}_{Path(filename).name}"
        blob = self.bucket.blob(safe_name)

        file_obj.seek(0)
        blob.upload_from_file(file_obj, content_type=content_type)
        # Objects remain PRIVATE (no make_public)

        created_at = datetime.now(timezone.utc)
        expires_at = created_at + timedelta(days=30)
        signed_url = self.get_access_url(safe_name, expiration_minutes=120)

        return {
            "id": file_id,
            "filename": filename,
            "storage_path": safe_name,
            "bucket": self.bucket_name,
            "access_url": signed_url,
            "content_type": content_type,
            "is_cloud": True,
            "created_at": created_at.isoformat(),
            "expires_at": expires_at.isoformat(),
        }

    def get_access_url(self, storage_path: str, expiration_minutes: int = 60) -> str:
        """Generate a temporary signed URL for private access without public exposure."""
        try:
            blob = self.bucket.blob(storage_path)
            return blob.generate_signed_url(
                version="v4",
                expiration=timedelta(minutes=expiration_minutes),
                method="GET",
            )
        except Exception:
            # Fallback if signed URL generation fails (e.g. on default Compute Engine credentials)
            return f"https://storage.cloud.google.com/{self.bucket_name}/{storage_path}"

    def delete_file(self, storage_path: str) -> bool:
        try:
            blob = self.bucket.blob(storage_path)
            blob.delete()
            return True
        except Exception:
            return False


def get_storage_service(root_dir: Path) -> BaseStorageService:
    """Factory creating GCS storage if configured, otherwise local storage."""
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
    bucket_name = os.environ.get("BUCKET_NAME")
    creds = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")

    if project_id and bucket_name:
        try:
            return GCSStorageService(project_id, bucket_name, creds)
        except Exception as err:
            import logging
            logging.getLogger("miner.storage").warning(
                "GCS storage configuration failed (%s). Falling back to local storage.", err
            )

    return LocalStorageService(root_dir)
