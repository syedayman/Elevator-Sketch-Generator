"""Supabase persistence for Drawing Debbie saved sketches.

The standalone app is a single shared workspace behind its password gate.
It therefore uses a server-only Supabase service-role key and assigns every
row to the configured ``GATE_USER_ID``.  Every query still includes that user
ID and the app scope so a programming mistake cannot cross workspaces.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from supabase import Client, create_client

import saved_sketches as saved


TABLE_NAME = "saved_sketches"
DEFAULT_LIMIT = 100


class SketchStoreError(RuntimeError):
    """Supabase could not complete a saved-sketch operation."""


class DuplicateSketchNameError(SketchStoreError):
    """The workspace already contains a sketch with the same name."""


class SketchNotFoundError(SketchStoreError):
    """The requested sketch does not exist in this workspace."""


class SketchConflictError(SketchStoreError):
    """The sketch changed after it was opened."""


def create_store(url: str, service_role_key: str, user_id: str) -> "SavedSketchStore":
    """Create a store from server-side configuration values."""
    if not isinstance(url, str) or not url.strip():
        raise SketchStoreError("SUPABASE_URL is not configured.")
    if not isinstance(service_role_key, str) or not service_role_key.strip():
        raise SketchStoreError("SUPABASE_SERVICE_ROLE_KEY is not configured.")
    return SavedSketchStore(
        create_client(url.strip(), service_role_key.strip()),
        user_id,
    )


class SavedSketchStore:
    """Small owner-scoped CRUD repository around the Supabase Data API."""

    def __init__(
        self,
        client: Client,
        user_id: str,
        *,
        app_scope: str = saved.APP_SCOPE,
    ) -> None:
        try:
            self.user_id = str(UUID(str(user_id)))
        except (TypeError, ValueError, AttributeError) as exc:
            raise SketchStoreError("GATE_USER_ID must be a UUID.") from exc
        self.client = client
        self.app_scope = app_scope

    def list_sketches(self, limit: int = DEFAULT_LIMIT) -> list[dict]:
        """Return lightweight metadata, most recently updated first."""
        safe_limit = max(1, min(int(limit), DEFAULT_LIMIT))
        try:
            response = (
                self.client.table(TABLE_NAME)
                .select("id,name,schema_version,summary,created_at,updated_at")
                .eq("user_id", self.user_id)
                .eq("app_scope", self.app_scope)
                .order("updated_at", desc=True)
                .limit(safe_limit)
                .execute()
            )
            return [self._metadata_from_row(row) for row in (response.data or [])]
        except (saved.SavedSketchError, SketchStoreError):
            raise
        except Exception as exc:
            self._raise_store_error("load saved sketches", exc)

    def get_sketch(self, sketch_id: str) -> dict:
        """Return and validate one complete saved sketch."""
        clean_id = self._validate_id(sketch_id)
        try:
            response = (
                self.client.table(TABLE_NAME)
                .select(
                    "id,name,schema_version,config,view_state,created_at,updated_at"
                )
                .eq("id", clean_id)
                .eq("user_id", self.user_id)
                .eq("app_scope", self.app_scope)
                .limit(1)
                .execute()
            )
            if not response.data:
                raise SketchNotFoundError("Saved sketch not found.")
            return saved.record_from_row(response.data[0])
        except (saved.SavedSketchError, SketchStoreError):
            raise
        except Exception as exc:
            self._raise_store_error("open the saved sketch", exc)

    def create_sketch(self, snapshot: dict) -> dict:
        """Insert and return a validated saved sketch."""
        clean = saved.validate_snapshot(snapshot)
        payload = {
            "user_id": self.user_id,
            "app_scope": self.app_scope,
            "summary": saved.config_summary(clean["config"]),
            **clean,
        }
        try:
            response = self.client.table(TABLE_NAME).insert(payload).execute()
            if not response.data:
                raise SketchStoreError("Supabase did not return the saved sketch.")
            return saved.record_from_row(response.data[0])
        except (saved.SavedSketchError, SketchStoreError):
            raise
        except Exception as exc:
            self._raise_store_error("save the sketch", exc)

    def update_sketch(
        self,
        sketch_id: str,
        snapshot: dict,
        *,
        expected_updated_at: str | None = None,
    ) -> dict:
        """Update an owned row, optionally guarding against stale overwrites."""
        clean_id = self._validate_id(sketch_id)
        clean = saved.validate_snapshot(snapshot)
        try:
            query = (
                self.client.table(TABLE_NAME)
                .update(
                    {
                        **clean,
                        "summary": saved.config_summary(clean["config"]),
                    }
                )
                .eq("id", clean_id)
                .eq("user_id", self.user_id)
                .eq("app_scope", self.app_scope)
            )
            if expected_updated_at:
                query = query.eq("updated_at", expected_updated_at)
            response = query.execute()
            if response.data:
                return saved.record_from_row(response.data[0])
            if expected_updated_at:
                try:
                    self.get_sketch(clean_id)
                except SketchNotFoundError:
                    raise
                raise SketchConflictError(
                    "This sketch was changed in another session. Open it again "
                    "before saving."
                )
            raise SketchNotFoundError("Saved sketch not found.")
        except (saved.SavedSketchError, SketchStoreError):
            raise
        except Exception as exc:
            self._raise_store_error("update the saved sketch", exc)

    def delete_sketch(self, sketch_id: str) -> None:
        """Permanently remove one owned saved sketch."""
        clean_id = self._validate_id(sketch_id)
        try:
            response = (
                self.client.table(TABLE_NAME)
                .delete()
                .eq("id", clean_id)
                .eq("user_id", self.user_id)
                .eq("app_scope", self.app_scope)
                .execute()
            )
            if not response.data:
                raise SketchNotFoundError("Saved sketch not found.")
        except SketchStoreError:
            raise
        except Exception as exc:
            self._raise_store_error("delete the saved sketch", exc)

    @staticmethod
    def _validate_id(value: str) -> str:
        try:
            return str(UUID(str(value)))
        except (TypeError, ValueError, AttributeError) as exc:
            raise SketchNotFoundError("Saved sketch not found.") from exc

    @staticmethod
    def _metadata_from_row(row: Any) -> dict:
        if not isinstance(row, dict):
            raise SketchStoreError("Supabase returned invalid saved-sketch data.")
        required = {
            "id",
            "name",
            "schema_version",
            "summary",
            "created_at",
            "updated_at",
        }
        if required - set(row):
            raise SketchStoreError("Supabase returned incomplete saved-sketch data.")
        try:
            sketch_id = str(UUID(str(row["id"])))
            name = saved.normalize_name(row["name"])
            saved._validate_timestamp(row["created_at"], "created_at")
            saved._validate_timestamp(row["updated_at"], "updated_at")
        except saved.SavedSketchError as exc:
            raise SketchStoreError(str(exc)) from exc
        version = row["schema_version"]
        if version != saved.SCHEMA_VERSION:
            raise SketchStoreError("A saved sketch uses an unsupported schema version.")
        summary = row["summary"]
        if not isinstance(summary, str) or not summary.strip() or len(summary) > 200:
            raise SketchStoreError("Supabase returned an invalid sketch summary.")
        return {
            "id": sketch_id,
            "name": name,
            "schema_version": version,
            "summary": summary,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    @staticmethod
    def _raise_store_error(action: str, exc: Exception) -> None:
        code = str(getattr(exc, "code", "") or "")
        message = str(exc)
        if code == "23505" or "23505" in message or "duplicate key" in message.lower():
            raise DuplicateSketchNameError(
                "A saved sketch with this name already exists."
            ) from exc
        raise SketchStoreError(
            f"Could not {action}. Check the Supabase connection and try again."
        ) from exc
