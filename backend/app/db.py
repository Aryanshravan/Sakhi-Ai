from collections.abc import Iterator
from functools import lru_cache

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.config import settings


def _connection_kwargs() -> dict:
    # The password may contain "@", so split on the last "@" instead of
    # handing the raw URL to the driver.
    credentials, host_part = settings.database_url.split("://", 1)[1].rsplit("@", 1)
    user, password = credentials.split(":", 1)
    host_port, database = host_part.split("/", 1)
    host, port = host_port.split(":", 1)
    return {"host": host, "port": int(port), "user": user, "password": password, "dbname": database}


def connect() -> psycopg.Connection:
    """A standalone connection, for scripts such as the migration."""
    return psycopg.connect(**_connection_kwargs(), row_factory=dict_row)


@lru_cache
def _pool() -> ConnectionPool:
    return ConnectionPool(
        kwargs={**_connection_kwargs(), "row_factory": dict_row},
        min_size=1,
        max_size=5,
        open=True,
    )


def get_db() -> Iterator[psycopg.Connection]:
    """FastAPI dependency: one pooled connection and transaction per request."""
    with _pool().connection() as conn:
        yield conn


def pooled_connection():
    """A pooled connection for background work outside a request (use as a context manager)."""
    return _pool().connection()
