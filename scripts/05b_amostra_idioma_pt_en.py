"""
Sorteia 100 primeiras conversas com idioma 'Portuguese' e 100 com 'English' na base,
para conferir por leitura se o rótulo de idioma da base é confiável nesses dois grupos
(no grupo 'Outros' ele coincidiu com a leitura em só 9 de 100).

Uso:
    python scripts/05b_amostra_idioma_pt_en.py

Entradas: data/silver/primeira_conversa.parquet, data/bronze/wildchat_brazil.parquet
Saída:    data/amostras/05b_idioma_pt_en.csv (tem texto; não versionar)
"""
import csv
import sys
from pathlib import Path

import duckdb

sys.stdout.reconfigure(encoding="utf-8")

SILVER = Path("data/silver/primeira_conversa.parquet")
BRAZIL = Path("data/bronze/wildchat_brazil.parquet")
SAIDA = Path("data/amostras/05b_idioma_pt_en.csv")
SEMENTE = 0.42
N_POR_IDIOMA = 100


def main() -> None:
    con = duckdb.connect()
    con.execute(f"SELECT setseed({SEMENTE})").fetchall()
    rel = con.sql(f"""
        WITH p AS (
            SELECT s.conversa_id, s.idioma,
                   left(regexp_replace(b.pergunta, '\\s+', ' ', 'g'), 300) AS pergunta_trecho
            FROM read_parquet('{SILVER.as_posix()}') s
            JOIN (SELECT conversation[1].turn_identifier AS conversa_id,
                         conversation[1]."content" AS pergunta
                  FROM read_parquet('{BRAZIL.as_posix()}')) b USING (conversa_id)
            WHERE s.idioma IN ('Portuguese', 'English') AND NOT s.pergunta_vazia
        ),
        -- O sorteio vira coluna antes da janela: esta versão do DuckDB não aceita
        -- random() direto no ORDER BY de uma janela.
        com_sorteio AS (SELECT *, random() AS r FROM p),
        sorteio AS (
            SELECT *, row_number() OVER (PARTITION BY idioma ORDER BY r) AS ordem FROM com_sorteio
        )
        SELECT conversa_id, idioma AS idioma_na_base, pergunta_trecho,
               NULL AS idioma_que_voce_identifica
        FROM sorteio WHERE ordem <= {N_POR_IDIOMA}
        ORDER BY idioma_na_base, conversa_id
    """)
    linhas = rel.fetchall()
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    with SAIDA.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(rel.columns)
        w.writerows(linhas)
    print(f"{SAIDA}: {len(linhas)} conversas ({N_POR_IDIOMA} por idioma)")


if __name__ == "__main__":
    main()