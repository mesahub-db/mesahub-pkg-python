from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .table import TableHandle
from .types import ExecResult, FileRecord, QueryResult

if TYPE_CHECKING:
    from .client import MesahubClient


class DatabaseHandle:
    """
    Scoped entry point for a single database reference (UUID or slug).

    Obtained via ``client.db("my-db")``.
    """

    def __init__(self, ref: str, client: "MesahubClient") -> None:
        self._ref = ref
        self._client = client
        self.files = _DatabaseFiles(ref, client)

    def query(self, sql: str, bindings: list[Any] | None = None) -> QueryResult:
        raw = self._client._post(
            self._client._path_query(self._ref),
            {"sql": sql, "bindings": bindings or []},
        )
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

    def exec(self, sql: str, bindings: list[Any] | None = None) -> ExecResult:
        raw = self._client._post(
            self._client._path_exec(self._ref),
            {"sql": sql, "bindings": bindings or []},
        )
        stat = raw.get("stat") or {}
        return ExecResult(
            rows_affected=raw.get("rowsAffected") or stat.get("rowsAffected") or 0,
            last_insert_rowid=raw.get("lastInsertRowid"),
            query_duration_ms=stat.get("queryDurationMs"),
        )

    def _exec_rows(self, sql: str, bindings: list[Any] | None = None) -> QueryResult:
        """Used internally by TableHandle for INSERT … RETURNING *."""
        raw = self._client._post(
            self._client._path_exec(self._ref),
            {"sql": sql, "bindings": bindings or []},
        )
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

    def table(self, table_name: str) -> TableHandle:
        return TableHandle(table_name, self.query, self.exec, self._exec_rows)


class _DatabaseFiles:
    def __init__(self, ref: str, client: "MesahubClient") -> None:
        self._ref = ref
        self._client = client

    def list(
        self,
        limit: int | None = None,
        offset: int | None = None,
        folder_prefix: str | None = None,
    ) -> dict:
        params: dict[str, str] = {}
        if limit is not None:
            params["limit"] = str(limit)
        if offset is not None:
            params["offset"] = str(offset)
        if folder_prefix is not None:
            params["folder_prefix"] = folder_prefix
        return self._client._get(self._client._path_files(self._ref), params=params)

    def upload(
        self,
        data: bytes,
        filename: str,
        content_type: str = "application/octet-stream",
    ) -> FileRecord:
        return self._client._upload(
            self._client._path_files(self._ref), data, filename, content_type
        )

    def download(self, file_id: str) -> bytes:
        return self._client._download(
            self._client._path_file_item(self._ref, file_id)
        )

    def delete(self, file_id: str) -> None:
        self._client._delete(self._client._path_file_item(self._ref, file_id))
