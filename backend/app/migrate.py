"""Create or update the database schema: python -m app.migrate"""

from pathlib import Path

from app.db import connect

SCHEMA_FILE = Path(__file__).with_name("schema.sql")


def main() -> None:
    with connect() as conn:
        conn.execute(SCHEMA_FILE.read_text(encoding="utf-8"))
    print("Schema applied.")


if __name__ == "__main__":
    main()
