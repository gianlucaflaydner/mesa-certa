"""Apaga, migra e semeia o banco configurado em DATABASE_URL. Alvo `make seed`."""

from pathlib import Path

from mesa_certa.config import get_settings
from mesa_certa.db.reset import reset_database

MIGRATIONS_PATH = Path(__file__).resolve().parent.parent / "migrations"


def main() -> None:
    database_url = get_settings().database_url
    reset_database(database_url, MIGRATIONS_PATH)
    print(f"Banco recriado e semeado: {database_url}")


if __name__ == "__main__":
    main()
