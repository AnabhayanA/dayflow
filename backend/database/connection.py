import os
from contextlib import contextmanager

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

load_dotenv()


def database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not configured. Copy .env.example to .env and "
            "add the TigerData connection string."
        )
    return url


@contextmanager
def get_connection():
    with psycopg.connect(database_url(), row_factory=dict_row) as connection:
        yield connection
