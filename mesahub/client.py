"""
mesahub — Python SDK for mesahub.

Talks directly to the mesahub core server (Go) using a shs_ API key.

Usage::

    from mesahub import MesahubClient

    client = MesahubClient(api_key="shs_...", api_url="https://api.yourapp.com")

    # High-level table API
    db    = client.db("my-db")
    users = db.table("users")

    all_rows = users.find(where={"active": 1}, limit=20)
    alice    = users.find_one(where={"email": "alice@example.com"})
    new_row  = users.insert({"name": "Bob", "email": "bob@example.com"})
    users.update(where={"id": new_row["id"]}, set={"name": "Robert"})
    users.delete(where={"id": new_row["id"]})

    # Raw SQL
    result = db.query("SELECT * FROM users WHERE active = ?", [1])

Connection string::

    from mesahub import MesahubClient, parse_mesahub_url

    info   = parse_mesahub_url("mh://shs_abc@mycore.railway.app/mydb")
    client = MesahubClient(**{k: v for k, v in info.items() if k != "db_name"})
    db     = client.db(info["db_name"])
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import unquote, urlparse

import httpx

from .database import DatabaseHandle
from .errors import MesahubError
from .types import ExecResult, FileRecord, QueryResult


class MesahubClient:
    def __init__(
        self,
        api_key: str,
        api_url: str,
        route_prefix: str = "v1",
        timeout: float = 30.0,
    ) -> None:
        base = re.sub(r"/(v1|api)/?$", "", api_url.rstrip("/"))
        self._http = httpx.Client(
            base_url=base,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )
        if route_prefix == "api":
            self._path_query     = lambda ref: f"/api/db/{ref}/query"
            self._path_exec      = lambda ref: f"/api/db/{ref}/exec"
            self._path_files     = lambda ref: f"/api/db/{ref}/files"
            self._path_file_item = lambda ref, fid: f"/api/db/{ref}/files/{fid}"
        else:
            self._path_query     = lambda ref: f"/v1/query/{ref}"
            self._path_exec      = lambda ref: f"/v1/exec/{ref}"
            self._path_files     = lambda ref: f"/v1/files/{ref}"
            self._path_file_item = lambda ref, fid: f"/v1/files/{ref}/{fid}"

    # ── Public API ────────────────────────────────────────────────────────────

    def query(
        self, ref: str, sql: str, bindings: list[Any] | None = None
    ) -> QueryResult:
        raw = self._post(self._path_query(ref), {"sql": sql, "bindings": bindings or []})
        columns = (
            [h["name"] for h in raw.get("headers", [])]
            if "headers" in raw
            else raw.get("columns", [])
        )
        rows = raw.get("rows") or []
        return QueryResult(
            rows=rows,
            columns=columns,
            row_count=len(rows),
            query_duration_ms=(raw.get("stat") or {}).get("queryDurationMs"),
        )

    def exec(
        self, ref: str, sql: str, bindings: list[Any] | None = None
    ) -> ExecResult:
        raw = self._post(self._path_exec(ref), {"sql": sql, "bindings": bindings or []})
        stat = raw.get("stat") or {}
        return ExecResult(
            rows_affected=raw.get("rowsAffected") or stat.get("rowsAffected") or 0,
            last_insert_rowid=raw.get("lastInsertRowid"),
            query_duration_ms=stat.get("queryDurationMs"),
        )

    def db(self, ref: str) -> DatabaseHandle:
        return DatabaseHandle(ref, self)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "MesahubClient":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    # ── HTTP primitives ───────────────────────────────────────────────────────

    def _post(self, path: str, body: Any) -> Any:
        r = self._http.post(path, json=body)
        self._raise_for_status(r)
        return r.json()

    def _get(self, path: str, params: dict | None = None) -> Any:
        r = self._http.get(path, params=params)
        self._raise_for_status(r)
        return r.json()

    def _delete(self, path: str) -> None:
        r = self._http.delete(path)
        self._raise_for_status(r)

    def _upload(
        self, path: str, data: bytes, filename: str, content_type: str
    ) -> Any:
        r = self._http.post(
            path, files={"file": (filename, data, content_type)}
        )
        self._raise_for_status(r)
        return r.json()

    def _download(self, path: str) -> bytes:
        r = self._http.get(path)
        self._raise_for_status(r)
        return r.content

    @staticmethod
    def _raise_for_status(r: httpx.Response) -> None:
        if r.is_error:
            try:
                body = r.json()
            except Exception:
                body = None
            raise MesahubError.from_response(r.status_code, r.reason_phrase, body)


# ── Connection string parser ──────────────────────────────────────────────────


def parse_mesahub_url(raw: str) -> dict[str, str]:
    """
    Parse a ``mh://`` connection string into its component parts.

    Format: ``mh://apikey@host[:port]/dbname``

    Returns a dict with keys: ``api_url``, ``api_key``, ``db_name``,
    ``route_prefix``.

    Example::

        info   = parse_mesahub_url("mh://shs_abc@mycore.railway.app/mydb")
        client = MesahubClient(api_key=info["api_key"], api_url=info["api_url"],
                               route_prefix=info["route_prefix"])
        db     = client.db(info["db_name"])
    """
    if not raw.startswith("mh://"):
        raise ValueError(
            f"Invalid MESAHUB_URL: must start with mh:// (got: {raw[:30]!r})"
        )

    parsed = urlparse(raw.replace("mh://", "http://", 1))
    host = parsed.hostname or ""

    if host == "local":
        raise ValueError(
            "mh://local/... is the embedded mode placeholder — it must be resolved "
            "to a concrete URL by start.sh before the application starts."
        )

    is_private = (
        host in ("localhost", "127.0.0.1")
        or "." not in host
        or host.endswith(".internal")
    )
    scheme = "http" if is_private else "https"
    port_part = f":{parsed.port}" if parsed.port else ""
    api_url = f"{scheme}://{host}{port_part}"

    api_key = unquote(parsed.username or "")
    if not api_key:
        raise ValueError(
            "MESAHUB_URL must include an API key: mh://apikey@host/dbname"
        )

    db_name = parsed.path.strip("/")
    if not db_name:
        raise ValueError(
            "MESAHUB_URL must include a database name: mh://apikey@host/dbname"
        )

    route_prefix = "api" if is_private else "v1"
    return {
        "api_url": api_url,
        "api_key": api_key,
        "db_name": db_name,
        "route_prefix": route_prefix,
    }
