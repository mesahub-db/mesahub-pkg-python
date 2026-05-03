from typing import Any, Optional
from typing_extensions import TypedDict


class QueryResult(TypedDict):
    rows: list[dict[str, Any]]
    columns: list[str]
    row_count: int
    query_duration_ms: Optional[float]


class ExecResult(TypedDict):
    rows_affected: int
    last_insert_rowid: Optional[int]
    query_duration_ms: Optional[float]


class FileRecord(TypedDict):
    id: str
    filename: str
    folder_path: Optional[str]
    size_bytes: int
    content_type: Optional[str]
    url: str
    uploaded_at: str
    expires_at: Optional[str]
    metadata: Optional[str]
