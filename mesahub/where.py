from typing import Any


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def build_where(clause: dict[str, Any] | None) -> tuple[str, list[Any]]:
    """
    Compile a filter dict into (sql_fragment, bindings).

    Shorthand equality:  {"id": 1}
    Operator object:     {"age": {"gte": 18}, "name": {"like": "%alice%"}}

    All conditions are combined with AND.
    Returns ("", []) when clause is empty or None.
    """
    if not clause:
        return "", []

    parts: list[str] = []
    bindings: list[Any] = []

    for key, op in clause.items():
        col = _quote_ident(key)

        if op is None:
            continue

        if not isinstance(op, dict):
            parts.append(f"{col} = ?")
            bindings.append(op)
            continue

        if "is_null" in op:
            parts.append(f"{col} IS NULL")
        elif "is_not_null" in op:
            parts.append(f"{col} IS NOT NULL")
        elif "eq" in op:
            parts.append(f"{col} = ?")
            bindings.append(op["eq"])
        elif "ne" in op:
            parts.append(f"{col} != ?")
            bindings.append(op["ne"])
        elif "gt" in op:
            parts.append(f"{col} > ?")
            bindings.append(op["gt"])
        elif "gte" in op:
            parts.append(f"{col} >= ?")
            bindings.append(op["gte"])
        elif "lt" in op:
            parts.append(f"{col} < ?")
            bindings.append(op["lt"])
        elif "lte" in op:
            parts.append(f"{col} <= ?")
            bindings.append(op["lte"])
        elif "like" in op:
            parts.append(f"{col} LIKE ?")
            bindings.append(op["like"])
        elif "not_like" in op:
            parts.append(f"{col} NOT LIKE ?")
            bindings.append(op["not_like"])
        elif "in" in op:
            vals: list[Any] = op["in"]
            if not vals:
                parts.append("1 = 0")
            else:
                placeholders = ", ".join("?" * len(vals))
                parts.append(f"{col} IN ({placeholders})")
                bindings.extend(vals)
        elif "not_in" in op:
            vals = op["not_in"]
            if vals:
                placeholders = ", ".join("?" * len(vals))
                parts.append(f"{col} NOT IN ({placeholders})")
                bindings.extend(vals)
        else:
            parts.append(f"{col} = ?")
            bindings.append(op)

    return " AND ".join(parts), bindings
