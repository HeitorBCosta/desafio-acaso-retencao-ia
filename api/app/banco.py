"""Acesso à base analítica: um pool de conexões e as consultas em arquivos .sql."""
import os
from functools import cache
from pathlib import Path

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://acaso:acaso@localhost:5432/acaso")
PASTA_SQL = Path(__file__).with_name("sql")

pool = ConnectionPool(DATABASE_URL, min_size=1, max_size=5, open=False,
                      kwargs={"row_factory": dict_row})


@cache
def sql(nome: str) -> str:
    """Lê app/sql/<nome>.sql uma vez. As mesmas consultas estão citadas na documentação."""
    return (PASTA_SQL / f"{nome}.sql").read_text(encoding="utf-8")


def consultar(nome: str, params: dict | None = None) -> list[dict]:
    with pool.connection() as con:
        return con.execute(sql(nome), params or {}).fetchall()
