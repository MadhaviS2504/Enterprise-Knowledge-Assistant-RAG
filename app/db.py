import json
from contextlib import contextmanager
import psycopg
from psycopg.rows import dict_row
from app.config import settings

@contextmanager
def connection():
    # Render provides a PostgreSQL connection URL. Prefer its external URL
    # for a FastAPI process running on your computer.
    url = settings().database_url
    if not url:
        raise RuntimeError("DATABASE_URL is missing from .env")
    with psycopg.connect(url, row_factory=dict_row, connect_timeout=10) as conn:
        yield conn

def audit(conn, actor, tenant, action, detail):
    conn.execute('INSERT INTO audit_events (actor,tenant_id,action,detail) VALUES (%s,%s,%s,%s)',
                 (actor, tenant, action, json.dumps(detail)))



# `app/db.py` provides reusable PostgreSQL connection and audit helpers.

# It has two purposes:

# - `connection()` establishes connections using `DATABASE_URL`.
# - `audit()` inserts application actions into the `audit_events` table.

# ```python
# with connection() as conn:
#     audit(conn, "user@example.com", "tenant-1", "document_upload", {"filename": "policy.pdf"})
# ```

# ### Where it is used currently

# It is not currently imported or called anywhere. Search results found no application modules using `connection()` or `audit()`.

# Database initialization is handled separately by `scripts/init_db.py`. That script reads the SQL schema and creates the tables.

# ```powershell
# python scripts/init_db.py
# ```

# ### Why it exists

# Without it, every future module would need to repeat:

# ```python
# psycopg.connect(settings().database_url)
# ```

# This module centralizes connection management and row formatting. It would be used by document uploads, chat history, approvals, feedback, and audit logging.

