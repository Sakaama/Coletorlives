"""Cloud Database Adapter (Firestore) with Local Fallback.

Enables cloud synchronization of shared Product State (candidates, edited clips, VODs)
while allowing the app to run completely offline without errors if Cloud is not configured.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("miner.cloud_db")


class FirestoreSyncService:
    """Manages Firestore synchronizations for shared Product State."""

    def __init__(self, project_id: Optional[str] = None):
        self.project_id = project_id or os.environ.get("GOOGLE_CLOUD_PROJECT")
        self.client = None
        self._init_client()

    def _init_client(self) -> None:
        if not self.project_id:
            return

        try:
            from google.cloud import firestore

            creds = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
            if creds and Path(creds).is_file():
                self.client = firestore.Client.from_service_account_json(creds, project=self.project_id)
            else:
                self.client = firestore.Client(project=self.project_id)
            logger.info("Firestore client initialized for project %s", self.project_id)
        except Exception as e:
            logger.warning("Firestore could not be initialized (%s). Operating in local-only mode.", e)
            self.client = None

    @property
    def is_connected(self) -> bool:
        return self.client is not None

    def save_edited_clip(self, clip_data: Dict[str, Any]) -> bool:
        """Store or update an edited clip in Firestore collection 'edited_clips'."""
        if not self.client:
            return False

        try:
            clip_id = clip_data.get("id")
            if not clip_id:
                return False

            doc_ref = self.client.collection("edited_clips").document(str(clip_id))
            doc_ref.set(clip_data, merge=True)
            return True
        except Exception as err:
            logger.warning("Failed to save edited clip to Firestore: %s", err)
            return False

    def list_edited_clips(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List edited clips from Firestore."""
        if not self.client:
            return []

        try:
            from google.cloud import firestore

            docs = (
                self.client.collection("edited_clips")
                .order_by("created_at", direction=firestore.Query.DESCENDING)
                .limit(limit)
                .stream()
            )
            return [doc.to_dict() for doc in docs]
        except Exception as err:
            logger.warning("Failed to list edited clips from Firestore: %s", err)
            return []

    def save_raw_clip(self, raw_data: Dict[str, Any]) -> bool:
        """Store a raw discovery clip from radar webhook in 'raw_clips'."""
        if not self.client:
            return False

        try:
            clip_id = raw_data.get("id")
            if not clip_id:
                return False

            doc_ref = self.client.collection("raw_clips").document(str(clip_id))
            doc_ref.set(raw_data, merge=True)
            return True
        except Exception as err:
            logger.warning("Failed to save raw clip to Firestore: %s", err)
            return False

    def list_raw_clips(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List raw clips from Firestore."""
        if not self.client:
            return []

        try:
            from google.cloud import firestore

            docs = (
                self.client.collection("raw_clips")
                .order_by("created_at", direction=firestore.Query.DESCENDING)
                .limit(limit)
                .stream()
            )
            return [doc.to_dict() for doc in docs]
        except Exception as err:
            logger.warning("Failed to list raw clips from Firestore: %s", err)
            return []


def get_firestore_service() -> FirestoreSyncService:
    """Factory for Firestore service."""
    return FirestoreSyncService()
