"""
Mede quanto os 5 dias sem coleta pesam no retorno em 7 dias.

O script 10b achou 5 dias sem nenhuma conversa na base (13 e 14/10/2023, 17 a
19/01/2024, pelo horário de Brasília). Quem chegou nos 7 dias anteriores a esses
dias pode ter voltado justamente neles. Nesse caso a volta não ficou registrada, e o
usuário conta como se não tivesse voltado. O erro só pode ir para um lado: o retorno
desses usuários fica subestimado.

O script marca como "afetado" o usuário elegível cuja janela de 7 dias depois da
primeira conversa encosta em algum desses dias. Depois compara o retorno com e sem
os afetados e lista as semanas de chegada em que eles estão.

Leitura combinada antes de rodar: se o retorno sem os afetados ficar dentro do IC 95%
da taxa principal (22,5% a 25,8%, relatório 06), a lacuna não muda o resultado geral.
Nesse caso todos ficam na análise, e a ressalva vai para as semanas atingidas no
documento e no dashboard. Se ficar fora, a taxa principal passa a ser a calculada sem
os afetados.

Como rodar:
    python scripts/13_sensibilidade_dias_sem_coleta.py

Lê:   data/bronze/wildchat_brazil.parquet, data/gold/base_analise.parquet
Gera: relatorios/13_sensibilidade_dias_sem_coleta.txt
"""
import math
import os
import sys
from pathlib import Path

import duckdb

sys.stdout.reconfigure(encoding="utf-8")

RAIZ = Path(__file__).resolve().parents[1]
os.chdir(RAIZ)

BRAZIL = Path("data/bronze/wildchat_brazil.parquet")
GOLD = Path("data/gold/base_analise.parquet")
RELATORIO = Path("relatorios/13_sensibilidade_dias_sem_coleta.txt")

FUSO = "America/Sao_Paulo"
# Valores do relatório 10b e do relatório 06, para conferência.
DIAS_ESPERADOS = ["2023-10-13", "2023-10-14", "2024-01-17", "2024-01-18", "2024-01-19"]
ESPERADO_06 = {"elegiveis": 2482, "voltaram": 598}


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """IC 95% de Wilson para uma proporção. Supõe usuários independentes."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return c - m, c + m


def main() -> None:
    con = duckdb.connect()
    con.execute("SET TimeZone = 'UTC'")
    RELATORIO.parent.mkdir(parents=True, exist_ok=True)
    out = RELATORIO.open("w", encoding="utf-8")

    def escrever(s: str = "") -> None:
        print(s)
        out.write(s + "\n")

    # Mesma regra do 10b: dia do calendário em Brasília, pela coluna timestamp.
    con.execute(f"""
        CREATE TABLE dia AS
        WITH c AS (
            SELECT CAST(timezone('{FUSO}', "timestamp") AS DATE) AS d
            FROM read_parquet('{BRAZIL.as_posix()}')
        ),
        cal AS (
            SELECT CAST(generate_series AS DATE) AS d
            FROM generate_series((SELECT min(d) FROM c)::TIMESTAMP, (SELECT max(d) FROM c)::TIMESTAMP,
                                 INTERVAL 1 DAY)
        )
        SELECT cal.d, count(c.d) AS conversas
        FROM cal LEFT JOIN c USING (d)
        GROUP BY cal.d
    """)
    dias = [d for (d,) in con.execute(
        "SELECT d::VARCHAR FROM dia WHERE conversas = 0 ORDER BY d").fetchall()]
    escrever(f"Dias sem conversa (horário de Brasília): {', '.join(dias)}")
    escrever(f"Conferência com o 10b: {'OK' if dias == DIAS_ESPERADOS else 'DIFERENTE: investigar'}")

    # Afetado: a janela [primeira conversa, primeira conversa + 7 dias], no horário de
    # Brasília, encosta em algum dia sem coleta.
    con.execute(f"""
        CREATE TABLE base AS
        SELECT g.usuario,
               g.retorno_7d_30min AS voltou,
               strftime(date_trunc('week', timezone('{FUSO}', g.t_inicio_utc)), '%Y-%m-%d') AS semana,
               EXISTS (
                   SELECT 1 FROM dia z
                   WHERE z.conversas = 0
                     AND timezone('{FUSO}', g.t_inicio_utc) < CAST(z.d + 1 AS TIMESTAMP)
                     AND timezone('{FUSO}', g.t_inicio_utc) + INTERVAL 7 DAY >= CAST(z.d AS TIMESTAMP)
               ) AS afetado
        FROM read_parquet('{GOLD.as_posix()}') g
        WHERE g.elegivel_30min
    """)

    n, k = con.execute("SELECT count(*), count(*) FILTER (WHERE voltou) FROM base").fetchall()[0]
    escrever(f"Conferência com o 06: {n} elegíveis, {k} voltaram | "
             f"{'OK' if (n, k) == (ESPERADO_06['elegiveis'], ESPERADO_06['voltaram']) else 'DIFERENTE: investigar'}")

    escrever("\n== [MEDIDO] Retorno em 7 dias com e sem os afetados (sessão de 30 min)")
    escrever("grupo | usuarios | voltaram | taxa | ic95")
    taxas = {}
    for nome, filtro in (("todos", "true"), ("afetados", "afetado"), ("sem os afetados", "NOT afetado")):
        n, k = con.execute(
            f"SELECT count(*), count(*) FILTER (WHERE voltou) FROM base WHERE {filtro}").fetchall()[0]
        lo, hi = wilson(k, n)
        taxas[nome] = (n, k, lo, hi)
        taxa = f"{k / n:.1%}" if n else "—"
        escrever(f"{nome} | {n} | {k} | {taxa} | [{lo:.1%}, {hi:.1%}]")

    escrever("\n== [MEDIDO] Afetados por semana de chegada (segunda a domingo, horário de Brasília)")
    escrever("semana | elegiveis_na_semana | afetados | voltaram_entre_afetados")
    for row in con.execute("""
        SELECT semana, count(*), count(*) FILTER (WHERE afetado),
               count(*) FILTER (WHERE afetado AND voltou)
        FROM base GROUP BY semana HAVING count(*) FILTER (WHERE afetado) > 0 ORDER BY semana
    """).fetchall():
        escrever(" | ".join(str(v) for v in row))

    escrever("\n== Aplicação da leitura fixada")
    n_t, k_t, lo_t, hi_t = taxas["todos"]
    n_s, k_s, _, _ = taxas["sem os afetados"]
    p_s = k_s / n_s
    escrever(f"Sem os afetados: {p_s:.1%}; IC 95% da taxa principal: [{lo_t:.1%}, {hi_t:.1%}]")
    if lo_t <= p_s <= hi_t:
        escrever("Dentro do IC: a lacuna não muda o resultado geral. Todos ficam na análise; "
                 "ressalva nas semanas listadas acima.")
    else:
        escrever("Fora do IC: a taxa principal passa a ser a calculada sem os afetados.")
    out.close()
    print(f"\nRelatório: {RELATORIO}")


if __name__ == "__main__":
    main()