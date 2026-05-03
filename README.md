# mesahub Python SDK

Python SDK for [mesahub](https://mesahub.app) — access SQLite databases from Python with raw SQL or a high-level table API.

## Installation

```bash
pip install mesahub
```

Requires Python 3.11+ and [`httpx`](https://www.python-httpx.org/).

## Quick Start

```python
from mesahub import MesahubClient

client = MesahubClient(
    api_key="shs_your_api_key",       # from mesahub.app → Settings → API Keys
    api_url="https://api.mesahub.app", # or your self-hosted core URL
)

db    = client.db("my-app-db")        # your database slug from the dashboard
users = db.table("users")

# High-level table API
all_rows = users.find(where={"active": 1}, limit=20)
alice    = users.find_one(where={"email": "alice@example.com"})
count    = users.count(where={"active": 1})
new_row  = users.insert({"name": "Bob", "email": "bob@example.com", "active": 1})

users.update(where={"id": new_row["id"]}, set={"name": "Robert"})
users.delete(where={"id": new_row["id"]})

# Raw SQL
result = db.query("SELECT * FROM users WHERE active = ?", [1])
print(result["rows"])  # [{"id": 1, "name": "Alice", ...}]

db.exec("CREATE TABLE IF NOT EXISTS logs (msg TEXT, created_at TEXT)")

client.close()
```

### Context manager

```python
with MesahubClient(api_key="shs_...", api_url="https://api.mesahub.app") as client:
    db = client.db("my-app-db")
    rows = db.table("orders").find(where={"status": "pending"})
```

## Connection String

```python
from mesahub import MesahubClient, parse_mesahub_url

info   = parse_mesahub_url("mh://shs_abc@mycore.railway.app/mydb")
client = MesahubClient(
    api_key=info["api_key"],
    api_url=info["api_url"],
    route_prefix=info["route_prefix"],
)
db = client.db(info["db_name"])
```

Format: `mh://apikey@host[:port]/dbname`

- Remote hosts (e.g. `railway.app`) → HTTPS, `/v1/` routes
- `localhost` / Docker service names / `*.internal` → HTTP, `/api/` routes

## WHERE Filters

```python
# Shorthand equality
users.find(where={"active": 1})

# Comparison operators
users.find(where={"age": {"gte": 18}, "score": {"lt": 100}})

# LIKE
users.find(where={"name": {"like": "%alice%"}})

# IN / NOT IN
users.find(where={"role": {"in": ["admin", "editor"]}})

# NULL checks
users.find(where={"deleted_at": {"is_null": True}})
users.find(where={"verified_at": {"is_not_null": True}})
```

All conditions in a single `where` dict are combined with `AND`.

| Operator key  | SQL equivalent   |
|---------------|------------------|
| *(plain value)* | `= ?`          |
| `eq`          | `= ?`           |
| `ne`          | `!= ?`          |
| `gt`          | `> ?`           |
| `gte`         | `>= ?`          |
| `lt`          | `< ?`           |
| `lte`         | `<= ?`          |
| `like`        | `LIKE ?`        |
| `not_like`    | `NOT LIKE ?`    |
| `in`          | `IN (...)`      |
| `not_in`      | `NOT IN (...)`  |
| `is_null`     | `IS NULL`       |
| `is_not_null` | `IS NOT NULL`   |

## `find()` Options

```python
users.find(
    where={"active": 1},
    select=["id", "name", "email"],
    order_by=[{"column": "created_at", "direction": "desc"}],
    limit=10,
    offset=20,
)
```

## `insert_many()`

```python
db.table("logs").insert_many(
    [{"msg": "started"}, {"msg": "done"}],
    on_conflict="ignore",  # "ignore" | "replace" | None
)
```

## Files

```python
files = db.files

# List
listing = files.list(limit=10, folder_prefix="reports/")

# Upload
record = files.upload(open("report.pdf", "rb").read(), "report.pdf", "application/pdf")
print(record["url"])

# Download
data = files.download(record["id"])

# Delete
files.delete(record["id"])
```

## Error Handling

```python
from mesahub import MesahubError, AuthenticationError, NotFoundError

try:
    db.query("SELECT * FROM users")
except AuthenticationError:
    print("Invalid API key")
except MesahubError as e:
    print(f"[{e.code}] {e.status_code}: {e}")
```

## Self-Hosting

Replace `api_url` with your own core server URL and optionally set `route_prefix="api"` for direct Go access (bypassing Caddy):

```python
client = MesahubClient(
    api_key="your-admin-token",
    api_url="http://localhost:4004",
    route_prefix="api",
)
```
