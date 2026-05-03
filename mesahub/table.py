from typing import Any, Callable

from .types import ExecResult, QueryResult
from .where import _quote_ident, build_where


class TableHandle:
    """
    High-level access to a single SQLite table.

    Obtained via ``db.table("table_name")``.
    """

    def __init__(
        self,
        table_name: str,
        query_fn: Callable,
        exec_fn: Callable,
        write_query_fn: Callable,
    ) -> None:
        self._tbl = _quote_ident(table_name)
        self._query_fn = query_fn
        self._exec_fn = exec_fn
        self._write_query_fn = write_query_fn

    def find(
        self,
        where: dict[str, Any] | None = None,
        select: list[str] | None = None,
        order_by: list[dict[str, str]] | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[dict[str, Any]]:
        sql, bindings = self._build_select(where, select, order_by, limit, offset)
        result = self._query_fn(sql, bindings)
        return result["rows"]

    def find_one(
        self,
        where: dict[str, Any] | None = None,
        select: list[str] | None = None,
        order_by: list[dict[str, str]] | None = None,
    ) -> dict[str, Any] | None:
        rows = self.find(where=where, select=select, order_by=order_by, limit=1)
        return rows[0] if rows else None

    def count(self, where: dict[str, Any] | None = None) -> int:
        where_sql, bindings = build_where(where)
        where_clause = f" WHERE {where_sql}" if where_sql else ""
        sql = f'SELECT COUNT(*) AS "_count" FROM {self._tbl}{where_clause}'
        result = self._query_fn(sql, bindings)
        row = result["rows"][0] if result["rows"] else {}
        return int(row.get("_count", row.get("COUNT(*)", 0)))

    def insert(self, data: dict[str, Any]) -> dict[str, Any]:
        if not data:
            raise ValueError("insert() called with empty data dict")
        keys = list(data.keys())
        cols = ", ".join(_quote_ident(k) for k in keys)
        placeholders = ", ".join("?" * len(keys))
        bindings = [data[k] for k in keys]
        sql = f"INSERT INTO {self._tbl} ({cols}) VALUES ({placeholders}) RETURNING *"
        result = self._write_query_fn(sql, bindings)
        if not result["rows"]:
            raise RuntimeError("insert() returned no row from RETURNING *")
        return result["rows"][0]

    def insert_many(
        self,
        rows: list[dict[str, Any]],
        on_conflict: str | None = None,
    ) -> ExecResult:
        if not rows:
            raise ValueError("insert_many() called with empty rows list")
        keys = list(rows[0].keys())
        if not keys:
            raise ValueError("insert_many() first row has no columns")
        cols = ", ".join(_quote_ident(k) for k in keys)
        row_ph = f"({', '.join('?' * len(keys))})"
        conflict = {"ignore": " OR IGNORE", "replace": " OR REPLACE"}.get(
            on_conflict or "", ""
        )
        all_ph = ", ".join(row_ph for _ in rows)
        bindings: list[Any] = []
        for row in rows:
            for k in keys:
                bindings.append(row.get(k))
        sql = f"INSERT{conflict} INTO {self._tbl} ({cols}) VALUES {all_ph}"
        return self._exec_fn(sql, bindings)

    def update(self, where: dict[str, Any], set: dict[str, Any]) -> ExecResult:
        set_keys = list(set.keys())
        if not set_keys:
            raise ValueError("update() called with empty set dict")
        set_clauses = ", ".join(f"{_quote_ident(k)} = ?" for k in set_keys)
        set_bindings = [set[k] for k in set_keys]
        where_sql, where_bindings = build_where(where)
        if not where_sql:
            raise ValueError("update() requires a non-empty where clause")
        sql = f"UPDATE {self._tbl} SET {set_clauses} WHERE {where_sql}"
        return self._exec_fn(sql, set_bindings + where_bindings)

    def delete(self, where: dict[str, Any]) -> ExecResult:
        where_sql, bindings = build_where(where)
        if not where_sql:
            raise ValueError("delete() requires a non-empty where clause")
        sql = f"DELETE FROM {self._tbl} WHERE {where_sql}"
        return self._exec_fn(sql, bindings)

    def _build_select(
        self,
        where: dict[str, Any] | None,
        select: list[str] | None,
        order_by: list[dict[str, str]] | None,
        limit: int | None,
        offset: int | None,
    ) -> tuple[str, list[Any]]:
        select_cols = (
            ", ".join(_quote_ident(c) for c in select) if select else "*"
        )
        where_sql, bindings = build_where(where)
        where_clause = f" WHERE {where_sql}" if where_sql else ""

        order_clause = ""
        if order_by:
            parts = [
                f"{_quote_ident(o['column'])} {o.get('direction', 'asc').upper()}"
                for o in order_by
            ]
            order_clause = " ORDER BY " + ", ".join(parts)

        limit_clause = f" LIMIT {int(limit)}" if limit is not None else ""
        offset_clause = f" OFFSET {int(offset)}" if offset is not None else ""

        sql = (
            f"SELECT {select_cols} FROM {self._tbl}"
            f"{where_clause}{order_clause}{limit_clause}{offset_clause}"
        )
        return sql, bindings
