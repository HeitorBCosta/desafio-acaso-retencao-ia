"""
Sorteia 30 das 129 recusas rotuladas para uma conferência feita por uma pessoa.

Os rótulos de recusa sustentam o principal achado da análise, então vale ter alguém
além de quem rotulou lendo uma amostra. A planilha traz o início da pergunta e da
resposta ao lado do rótulo e do motivo, com colunas em branco para dizer se concorda.
A concordância vai para o documento, e os casos conferidos ganham o nome de quem
conferiu na coluna conferido_por de docs/rotulos/recusa_resultado.csv.

Como rodar:
    python scripts/12_amostra_conferencia_recusa.py

Lê:   docs/rotulos/recusa_resultado.csv, data/bronze/wildchat_brazil.parquet
Gera: data/amostras/12_conferencia_recusa.csv (tem texto, fica fora do Git)
"""
import csv
import sys
from pathlib import Path

import duckdb

sys.stdout.reconfigure(encoding="utf-8")

RAIZ = Path(__file__).resolve().parents[1]
ROTULOS = RAIZ / "docs/rotulos/recusa_resultado.csv"
BRAZIL = RAIZ / "data/bronze/wildchat_brazil.parquet"
SAIDA = RAIZ / "data/amostras/12_conferencia_recusa.csv"
N = 30
SEMENTE = 0.12
CHARS = 600


def main() -> None:
    con = duckdb.connect()
    con.execute(f"SELECT setseed({SEMENTE})").fetchall()
    linhas = con.execute(f"""
        WITH r AS (
            SELECT conversa_id::BIGINT AS conversa_id, resultado, motivo
            FROM read_csv('{ROTULOS.as_posix()}', delim=';', header=true, all_varchar=true)
            WHERE resultado IN ('parcial', 'nao_atendido')
        ),
        sorteio AS (SELECT *, random() AS ordem FROM r),
        escolhidos AS (SELECT * FROM sorteio ORDER BY ordem LIMIT {N}),
        c AS (
            SELECT conversation[1].turn_identifier AS conversa_id,
                   conversation[1]."content" AS pergunta,
                   list_filter(conversation, lambda x: x."role" = 'assistant')[1]."content" AS resposta
            FROM read_parquet('{BRAZIL.as_posix()}')
        )
        SELECT e.conversa_id::VARCHAR, e.resultado, e.motivo,
               left(COALESCE(c.pergunta, ''), {CHARS}), left(COALESCE(c.resposta, ''), {CHARS})
        FROM escolhidos e LEFT JOIN c USING (conversa_id)
        ORDER BY e.resultado, e.motivo, e.conversa_id
    """).fetchall()
    total = con.execute(f"""
        SELECT count(*) FROM read_csv('{ROTULOS.as_posix()}', delim=';', header=true, all_varchar=true)
        WHERE resultado IN ('parcial', 'nao_atendido')
    """).fetchall()[0][0]

    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    with SAIDA.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["conversa_id", "resultado_claude", "motivo_claude", "pergunta_inicio", "resposta_inicio",
                    "concorda_resultado", "concorda_motivo", "comentario"])
        for cid, res, mot, perg, resp in linhas:
            w.writerow([cid, res, mot, perg.replace("\n", " ⏎ "), resp.replace("\n", " ⏎ "), "", "", ""])
    sem_texto = sum(1 for l in linhas if not l[3] and not l[4])
    print(f"Sorteadas {len(linhas)} de {total} recusas rotuladas (semente {SEMENTE}).")
    if sem_texto:
        print(f"ATENÇÃO: {sem_texto} sem texto encontrado no bronze.")
    print(f"Gravado: {SAIDA}")


if __name__ == "__main__":
    main()
