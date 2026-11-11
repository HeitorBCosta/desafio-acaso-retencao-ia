"""
Calcula, para cada usuário, se ele voltou em até 7 dias.

Voltar quer dizer começar uma segunda sessão em até 7 dias depois do início da
primeira conversa, e uma sessão termina depois de 30 minutos sem uso (BDR-003). Para a
análise de sensibilidade, o mesmo cálculo é repetido com sessões de 1, 2, 6, 12 e 24
horas e com a regra "voltou em outro dia do calendário", em UTC e no horário de
Brasília. Só entra na conta quem chegou com pelo menos 7 dias de base pela frente.

Como rodar:
    python scripts/06_desfecho_retorno.py

Lê:   data/bronze/wildchat_brazil.parquet, data/silver/primeira_conversa.parquet
Gera: data/gold/base_analise.parquet (uma linha por usuário, sem texto)
      relatorios/06_desfecho_retorno.txt
"""
import math
import sys
from pathlib import Path

import duckdb

sys.stdout.reconfigure(encoding="utf-8")

BRAZIL = Path("data/bronze/wildchat_brazil.parquet")
SILVER = Path("data/silver/primeira_conversa.parquet")
GOLD = Path("data/gold/base_analise.parquet")
RELATORIO = Path("relatorios/06_desfecho_retorno.txt")

JANELA = "INTERVAL 7 DAY"
GAP_PRINCIPAL = "30min"
GAPS = {  # Premissa: BDR-003: 30 min é a regra principal; as demais são sensibilidade
    "30min": "INTERVAL 30 MINUTE",
    "1h": "INTERVAL 1 HOUR",
    "2h": "INTERVAL 2 HOUR",
    "6h": "INTERVAL 6 HOUR",
    "12h": "INTERVAL 12 HOUR",
    "24h": "INTERVAL 24 HOUR",
}
FUSOS_OUTRO_DIA = {"utc": "UTC", "sp": "America/Sao_Paulo"}

# Valor do script 03 (relatorios/03_horarios_e_sessao.txt) para a mesma regra:
# ip+so+navegador | inicio+fim | 30min | 2482 elegíveis | 598 voltaram.
ESPERADO_03 = {"elegiveis": 2482, "voltaram": 598}


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """IC 95% de Wilson para uma proporção. Supõe usuários independentes."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return c - m, c + m


def trocar_desfecho(con: duckdb.DuckDBPyConnection) -> None:
    """Substitui a tabela desfecho pela versão com as colunas novas."""
    con.execute("DROP TABLE desfecho")
    con.execute("ALTER TABLE desfecho_novo RENAME TO desfecho")


def main() -> None:
    con = duckdb.connect()
    con.execute("SET TimeZone = 'UTC'")
    for p in (GOLD.parent, RELATORIO.parent):
        p.mkdir(parents=True, exist_ok=True)
    out = RELATORIO.open("w", encoding="utf-8")

    def escrever(texto: str) -> None:
        print(texto)
        out.write(texto + "\n")

    def show(titulo: str, sql: str) -> None:
        try:
            rel = con.sql(sql)
            linhas = [" | ".join(rel.columns)]
            linhas += [" | ".join(str(v) for v in row) for row in rel.fetchall()]
            escrever(f"\n== {titulo}\n" + "\n".join(linhas))
        except duckdb.Error as e:
            escrever(f"\n== {titulo}\nERRO: {e}")

    escrever("Decisões e premissas desta execução:")
    escrever("  BDR-001 usuário = hashed_ip + SO + navegador")
    escrever("  BDR-002 primeira experiência = primeira conversa")
    escrever(f"  BDR-003 retorno = 2ª sessão até 7 dias após a 1ª conversa; regra principal: {GAP_PRINCIPAL}")
    escrever("  início da conversa = 1ª resposta do assistente; fim = coluna timestamp (última resposta)")
    escrever("  elegível = 1ª conversa pelo menos 7 dias antes do fim dos dados")
    escrever("  IC 95% de Wilson, supondo usuários independentes")

    # Todas as conversas, com a mesma chave de usuário do script 04.
    con.execute(f"""
        CREATE TABLE conv AS
        WITH c AS (
            SELECT conversation[1].turn_identifier AS conversa_id,
                   hashed_ip, header."user-agent" AS ua,
                   list_min(list_transform(
                       list_filter(conversation, lambda x: x."role" = 'assistant'),
                       lambda x: x."timestamp")) AS t_resp1,
                   "timestamp" AS fim
            FROM read_parquet('{BRAZIL.as_posix()}')
        )
        SELECT conversa_id, fim, COALESCE(t_resp1, fim) AS ini,
               hashed_ip || '|' ||
               CASE
                   WHEN ua ILIKE '%Android%' THEN 'Android'
                   WHEN ua ILIKE '%iPhone%' OR ua ILIKE '%iPad%' THEN 'iOS'
                   WHEN ua ILIKE '%Windows%' THEN 'Windows'
                   WHEN ua ILIKE '%Mac OS X%' THEN 'macOS'
                   WHEN ua ILIKE '%CrOS%' THEN 'ChromeOS'
                   WHEN ua ILIKE '%Linux%' THEN 'Linux'
                   ELSE 'Outro'
               END || '|' ||
               CASE
                   WHEN ua ILIKE '%Edg/%' THEN 'Edge'
                   WHEN ua ILIKE '%OPR/%' THEN 'Opera'
                   WHEN ua ILIKE '%SamsungBrowser%' THEN 'Samsung'
                   WHEN ua ILIKE '%Firefox/%' THEN 'Firefox'
                   WHEN ua ILIKE '%Chrome/%' OR ua ILIKE '%CriOS/%' THEN 'Chrome'
                   WHEN ua ILIKE '%Safari/%' THEN 'Safari'
                   ELSE 'Outro'
               END AS usuario
        FROM c
    """)
    con.execute(f"CREATE TABLE silver AS SELECT * FROM read_parquet('{SILVER.as_posix()}')")
    fim_dados = "(SELECT max(fim) FROM conv)"

    # ------------------------------------------------------------ consistência com o silver
    show("[MEDIDO] Consistência com o silver (todos devem ser 0, exceto os totais)",
         f"""WITH p AS (
                SELECT usuario, conversa_id,
                       row_number() OVER (PARTITION BY usuario ORDER BY ini, fim, conversa_id) o
                FROM conv
             )
             SELECT (SELECT count(DISTINCT usuario) FROM conv) usuarios_conv,
                    (SELECT count(*) FROM silver) usuarios_silver,
                    (SELECT count(*) FROM silver s WHERE s.usuario NOT IN (SELECT usuario FROM conv))
                        silver_sem_conversa,
                    (SELECT count(DISTINCT usuario) FROM conv
                     WHERE usuario NOT IN (SELECT usuario FROM silver)) conv_sem_silver,
                    (SELECT count(*) FROM p JOIN silver s USING (usuario)
                     WHERE p.o = 1 AND p.conversa_id <> s.conversa_id) primeira_conversa_diferente""")

    # ------------------------------------------------------------ desfechos por sessão
    con.execute("CREATE TABLE desfecho AS SELECT usuario FROM silver")
    for nome, gap in GAPS.items():
        con.execute(f"""
            CREATE TABLE d AS
            WITH m AS (
                SELECT usuario, ini, fim, conversa_id,
                       max(fim) OVER (PARTITION BY usuario ORDER BY ini, fim, conversa_id
                                      ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS prev_fim
                FROM conv
            ),
            s AS (
                SELECT usuario, ini,
                       sum(CASE WHEN prev_fim IS NULL OR ini - prev_fim > {gap} THEN 1 ELSE 0 END)
                           OVER (PARTITION BY usuario ORDER BY ini, fim, conversa_id
                                 ROWS UNBOUNDED PRECEDING) AS sessao
                FROM m
            )
            SELECT usuario,
                   min(ini) FILTER (WHERE sessao = 1) AS primeira,
                   min(ini) FILTER (WHERE sessao = 2) AS segunda
            FROM s GROUP BY usuario
        """)
        con.execute(f"""
            CREATE TABLE desfecho_novo AS
            SELECT x.*,
                   d.primeira <= {fim_dados} - {JANELA} AS elegivel_{nome},
                   CASE WHEN d.primeira <= {fim_dados} - {JANELA}
                        THEN COALESCE(d.segunda <= d.primeira + {JANELA}, false) END
                       AS retorno_7d_{nome},
                   date_diff('minute', d.primeira, d.segunda) / 60.0 AS horas_ate_2a_sessao_{nome}
            FROM desfecho x JOIN d USING (usuario)
        """)
        con.execute("DROP TABLE d")
        trocar_desfecho(con)

    # ------------------------------------------------------------ desfechos por dia do calendário
    for nome, fuso in FUSOS_OUTRO_DIA.items():
        con.execute(f"""
            CREATE TABLE desfecho_novo AS
            WITH p AS (SELECT usuario, min(ini) AS primeira FROM conv GROUP BY usuario),
            r AS (
                SELECT p.usuario,
                       bool_or(CAST(timezone('{fuso}', c.ini) AS DATE)
                                   > CAST(timezone('{fuso}', p.primeira) AS DATE)
                               AND c.ini <= p.primeira + {JANELA}) AS voltou
                FROM p JOIN conv c USING (usuario) GROUP BY p.usuario
            )
            SELECT x.*,
                   CASE WHEN p.primeira <= {fim_dados} - {JANELA} THEN r.voltou END
                       AS retorno_7d_outro_dia_{nome}
            FROM desfecho x JOIN p USING (usuario) JOIN r USING (usuario)
        """)
        trocar_desfecho(con)

    # ------------------------------------------------------------ taxas
    escrever("\n== [MEDIDO sob cada PREMISSA] Retorno em 7 dias")
    escrever("regra | elegiveis | voltaram | taxa | ic95")
    colunas = [f"retorno_7d_{n}" for n in GAPS] + [f"retorno_7d_outro_dia_{n}" for n in FUSOS_OUTRO_DIA]
    resultados = {}
    for col in colunas:
        n, k = con.sql(f"SELECT count({col}), count(*) FILTER (WHERE {col}) FROM desfecho").fetchall()[0]
        lo, hi = wilson(k, n)
        resultados[col] = (n, k)
        marca = "  <- principal (BDR-003)" if col == f"retorno_7d_{GAP_PRINCIPAL}" else ""
        escrever(f"{col.removeprefix('retorno_7d_')} | {n} | {k} | {k / n:.1%} | [{lo:.1%}, {hi:.1%}]{marca}")

    n, k = resultados[f"retorno_7d_{GAP_PRINCIPAL}"]
    ok = (n, k) == (ESPERADO_03["elegiveis"], ESPERADO_03["voltaram"])
    escrever(f"\n== [MEDIDO] Conferência com o script 03 (30 min, ip+so+navegador, início+fim)")
    escrever(f"esperado: {ESPERADO_03['elegiveis']} elegíveis, {ESPERADO_03['voltaram']} voltaram | "
             f"obtido: {n} elegíveis, {k} voltaram | {'OK' if ok else 'DIFERENTE: investigar'}")

    show("[MEDIDO] Horas até a 2ª sessão, entre quem voltou em 7 dias (regra principal)",
         f"""SELECT count(*) usuarios,
                    quantile_cont(horas_ate_2a_sessao_{GAP_PRINCIPAL}, [0.1, 0.25, 0.5, 0.75, 0.9])
                        p10_p25_p50_p75_p90
             FROM desfecho WHERE retorno_7d_{GAP_PRINCIPAL}""")

    # ------------------------------------------------------------ gold
    con.execute(f"""
        COPY (SELECT s.*, d.* EXCLUDE (usuario)
              FROM silver s JOIN desfecho d USING (usuario)
              ORDER BY s.t_inicio_utc)
        TO '{GOLD.as_posix()}' (FORMAT parquet, COMPRESSION zstd)
    """)
    show("[MEDIDO] Base de análise gravada",
         f"SELECT count(*) linhas, count(DISTINCT usuario) usuarios FROM read_parquet('{GOLD.as_posix()}')")

    out.close()
    print(f"\nRelatório: {RELATORIO}\nGold: {GOLD}")


if __name__ == "__main__":
    main()
