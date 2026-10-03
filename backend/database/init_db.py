from pathlib import Path

from backend.database.connection import get_connection


def initialize_database() -> None:
    schema_path = Path(__file__).with_name("schema.sql")
    schema = schema_path.read_text(encoding="utf-8")

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(schema)
        connection.commit()


if __name__ == "__main__":
    initialize_database()
    print("DayFlow database initialized.")
