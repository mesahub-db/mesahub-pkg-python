"""
MesahubManagementClient — management-plane SDK for MesaHub.

Talks to the MesaHub dashboard (Next.js) using a ``shs_`` API key.
Provides CRUD for databases, buckets, and API keys.

Usage::

    from mesahub import MesahubManagementClient

    mgmt = MesahubManagementClient(
        dashboard_url="https://www.mesahub.app",
        api_key="shs_...",
    )

    # Databases
    dbs  = mgmt.databases.list()
    db   = mgmt.databases.create("my-app-db")
    mgmt.databases.delete(db["id"])

    # Buckets
    bkts = mgmt.buckets.list()
    bkt  = mgmt.buckets.create("my-bucket")
    mgmt.buckets.update(bkt["id"], name="renamed-bucket")

    # API Keys
    keys   = mgmt.api_keys.list()
    result = mgmt.api_keys.create("ci-key")
    print(result["key"])   # raw token — shown only once
    mgmt.api_keys.revoke(result["id"])
"""

from __future__ import annotations

import json
from typing import Any, BinaryIO, Optional

import httpx

from .errors import MesahubError


class _DatabasesNamespace:
    def __init__(self, client: "MesahubManagementClient") -> None:
        self._c = client

    def list(self) -> list[dict[str, Any]]:
        """Return all databases owned by the authenticated user."""
        return self._c._req("GET", "/api/user/databases")

    def get(self, id: str) -> dict[str, Any]:
        """Return a single database by ID."""
        return self._c._req("GET", f"/api/user/databases/{id}")

    def create(self, name: str, description: Optional[str] = None) -> dict[str, Any]:
        """Create a new database.

        ``name`` must be 3–50 lowercase alphanumeric characters, dashes, or underscores.
        """
        body: dict[str, Any] = {"name": name}
        if description is not None:
            body["description"] = description
        return self._c._req("POST", "/api/user/databases", body)

    def delete(self, id: str) -> None:
        """Delete a database by ID."""
        self._c._req("DELETE", f"/api/user/databases/{id}")

    def update(
        self,
        id: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> dict[str, Any]:
        """Update a database's name and/or description."""
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if description is not None:
            body["description"] = description
        return self._c._req("PATCH", f"/api/user/databases/{id}", body)

    def export(self, id: str, tables: list[str], filename: Optional[str] = None) -> bytes:
        """Export the given tables from a database as a SQLite binary.

        Returns the raw SQLite bytes.
        """
        body: dict[str, Any] = {"tables": tables}
        if filename:
            body["filename"] = filename
        res = self._c._http.post(f"/api/user/databases/{id}/export", json=body)
        if res.is_error:
            _raise_for_response(res)
        return res.content

    def import_inspect(self, id: str, file: BinaryIO, filename: str = "import.db") -> dict[str, Any]:
        """Phase 1 import: inspect a SQLite file and return its table list.

        Does *not* modify the target database.
        """
        return self._c._upload(f"/api/user/databases/{id}/import", file, filename, tables=None)

    def import_tables(
        self,
        id: str,
        file: BinaryIO,
        tables: list[str],
        filename: str = "import.db",
    ) -> dict[str, Any]:
        """Phase 2 import: copy the selected tables from a SQLite file into the database."""
        return self._c._upload(f"/api/user/databases/{id}/import", file, filename, tables=tables)


class _BucketsNamespace:
    def __init__(self, client: "MesahubManagementClient") -> None:
        self._c = client

    def list(self) -> list[dict[str, Any]]:
        """Return all buckets owned by the authenticated user."""
        return self._c._req("GET", "/api/user/buckets")

    def get(self, id: str) -> dict[str, Any]:
        """Return a single bucket by ID."""
        return self._c._req("GET", f"/api/user/buckets/{id}")

    def create(self, name: str, description: Optional[str] = None) -> dict[str, Any]:
        """Create a new bucket."""
        body: dict[str, Any] = {"name": name}
        if description is not None:
            body["description"] = description
        return self._c._req("POST", "/api/user/buckets", body)

    def delete(self, id: str) -> None:
        """Delete a bucket by ID."""
        self._c._req("DELETE", f"/api/user/buckets/{id}")

    def update(
        self,
        id: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> dict[str, Any]:
        """Update a bucket's name and/or description."""
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if description is not None:
            body["description"] = description
        return self._c._req("PATCH", f"/api/user/buckets/{id}", body)


class _APIKeysNamespace:
    def __init__(self, client: "MesahubManagementClient") -> None:
        self._c = client

    def list(self) -> list[dict[str, Any]]:
        """Return all API keys for the authenticated user."""
        return self._c._req("GET", "/api/user/api-keys")

    def create(self, name: str, scopes: Optional[list[str]] = None) -> dict[str, Any]:
        """Create a new API key.

        Returns ``{"id": ..., "name": ..., "key": ...}`` — the raw token is
        only returned once.
        """
        return self._c._req(
            "POST",
            "/api/user/api-keys",
            {"name": name, "scopes": scopes if scopes is not None else ["all:w"]},
        )

    def revoke(self, id: str) -> None:
        """Revoke an API key by ID."""
        self._c._req("DELETE", f"/api/user/api-keys/{id}")


def _raise_for_response(res: httpx.Response) -> None:
    try:
        detail = res.json().get("error", "")
    except Exception:
        detail = ""
    raise MesahubError(res.status_code, detail or f"HTTP {res.status_code}", res)


class MesahubManagementClient:
    """Management-plane client for MesaHub.

    :param dashboard_url: Dashboard origin, e.g. ``"https://www.mesahub.app"``.
    :param api_key: ``shs_`` API key for the authenticated user.
    :param timeout: HTTP timeout in seconds (default 30).
    """

    def __init__(
        self,
        dashboard_url: str,
        api_key: str,
        timeout: float = 30.0,
    ) -> None:
        base = dashboard_url.rstrip("/")
        self._http = httpx.Client(
            base_url=base,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )
        self.databases = _DatabasesNamespace(self)
        self.buckets = _BucketsNamespace(self)
        self.api_keys = _APIKeysNamespace(self)

    def _req(self, method: str, path: str, body: Any = None) -> Any:
        if body is not None:
            res = self._http.request(method, path, json=body)
        else:
            res = self._http.request(method, path)
        if res.status_code == 204:
            return None
        if res.is_error:
            _raise_for_response(res)
        return res.json()

    def _upload(
        self,
        path: str,
        file: BinaryIO,
        filename: str,
        tables: Optional[list[str]],
    ) -> Any:
        data: dict[str, Any] = {}
        if tables is not None:
            data["tables"] = json.dumps(tables)
        files = {"file": (filename, file, "application/octet-stream")}
        res = self._http.post(path, data=data, files=files)
        if res.is_error:
            _raise_for_response(res)
        return res.json()

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._http.close()

    def __enter__(self) -> "MesahubManagementClient":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
