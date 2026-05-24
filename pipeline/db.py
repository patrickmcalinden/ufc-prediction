"""Single source for the DB connection.

Reads DATABASE_URL from .env. All other pipeline modules import `connect()`
from here so we only have one place to touch if the connection method
changes.
"""

from __future__ import annotations

import os
from contextlib import contextmanager

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

load_dotenv()


def _db_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set — check your .env")
    return url


@contextmanager
def connect():
    """Yield a psycopg connection with dict_row factory.

        with connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
    """
    with psycopg.connect(_db_url(), row_factory=dict_row) as conn:
        yield conn


def sqlalchemy_url() -> str:
    """SQLAlchemy variant of the URL for pandas.read_sql_query()."""
    return _db_url().replace("postgresql://", "postgresql+psycopg://")
