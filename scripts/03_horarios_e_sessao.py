"""
1) Verifica quais itens da lista `conversation` têm horário (por role) e se a
   coluna `timestamp` coincide com o horário do último item.
2) Mede o retorno em 7 dias para várias regras de sessão, com duas âncoras de
   horário: só a coluna `timestamp` (último turno) e início/fim por conversa,
   quando os horários por item permitirem.

Uso:
    python scripts/03_horarios_e_sessao.py

Entrada: data/bronze/wildchat_brazil.parquet
Saída:   relatorios/03_horarios_e_sessao.txt

Rótulos: [MEDIDO] consulta direta; [PREMISSA] escolha nossa; [DERIVADO] regra explícita.
"""
import math
import sys
from pathlib import Path

import duckdb

sys.stdout.reconfigure(encoding="utf-8")

BRAZIL = Path("data/bronze/wildchat_brazil.parquet")
SAIDA = Path("relatorios/03_horarios_e_sessao.txt")
FUSO = "UTC"  # [PREMISSA]

# [PREMISSA] Definições de usuário (as mesmas do script 02).
DEFINICOES_USUARIO = {
    "ip": "hashed_ip",
    "ip+ua_completo": "hashed_ip || '|' || ua",
    "ip+so+navegador": "hashed_ip || '|' || so || '|' || navegador",
}
# [PREMISSA] Regras de sessão testadas: intervalo mínimo sem uso entre sessões.
GAPS_SESSAO = {
    "30min": "INTERVAL 30 MINUTE",
    "1h": "INTERVAL 1 HOUR",
    "2h": "INTERVAL 2 HOUR",
    "6h": "INTERVAL 6 HOUR",
    "12h": "INTERVAL 12 HOUR",
    "24h": "INTERVAL 24 HOUR",
}
JANELA = "INTERVAL 7 DAY"  # [PREMISSA] janela de retorno


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return c - m, c + m


def main() -> None:
    con = duckdb.connect()
    con.execute(f"SET TimeZone = '{FUSO}'")
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    out = SAIDA.open("w", encoding="utf-8")

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

    src = f"read_parquet('{BRAZIL.as_posix()}')"

    # ---------------------------------------------------------------- parte 1
    con.execute(f"""
        CREATE TABLE itens AS
        SELECT conversa_id, ts_conversa, pos,
               item."role" AS role, item."timestamp" AS ts_item
        FROM (
            SELECT conversation[1].turn_identifier      AS conversa_id,
                   "timestamp"                         AS ts_conversa,
                   generate_subscripts(conversation, 1) AS pos,
                   unnest(conversation)                AS item
            FROM {src}
        )
    """)

    show("[MEDIDO] Itens de `conversation` com horário, por role",
         """SELECT role, count(*) itens,
                   count(ts_item) com_horario,
                   count(*) - count(ts_item) sem_horario
            FROM itens GROUP BY role ORDER BY role""")
    show("[MEDIDO] Horário por posição do item (1 = primeiro item da conversa)",
         """SELECT pos, count(*) itens, count(ts_item) com_horario
            FROM itens WHERE pos <= 6 GROUP BY pos ORDER BY pos""")
    show("[MEDIDO] A coluna timestamp é igual ao horário do último item com horário?",
         """WITH ult AS (
                SELECT conversa_id, any_value(ts_conversa) ts_conversa,
                       max(ts_item) ultimo_item, min(ts_item) primeiro_item
                FROM itens GROUP BY conversa_id
            )
            SELECT count(*) conversas,
                   count(ultimo_item) com_algum_horario_de_item,
                   count(*) FILTER (WHERE ts_conversa = ultimo_item) igual,
                   count(*) FILTER (WHERE ts_conversa > ultimo_item) timestamp_depois,
                   count(*) FILTER (WHERE ts_conversa < ultimo_item) timestamp_antes
            FROM ult""")
    show("[MEDIDO] Duração da conversa (último menos primeiro item com horário), em minutos",
         """WITH d AS (
                SELECT conversa_id,
                       date_diff('second', min(ts_item), max(ts_item)) / 60.0 AS minutos,
                       count(ts_item) n_horarios
                FROM itens GROUP BY conversa_id HAVING count(ts_item) >= 2
            )
            SELECT count(*) conversas_com_2_ou_mais_horarios,
                   round(quantile_cont(minutos, 0.5), 1) p50,
                   round(quantile_cont(minutos, 0.9), 1) p90,
                   round(quantile_cont(minutos, 0.99), 1) p99,
                   round(max(minutos), 1) maximo
            FROM d""")

    # ---------------------------------------------------------------- parte 2
    # Uma linha por conversa, com duas âncoras:
    #   t_fim    = coluna timestamp (sempre preenchida)
    #   t_inicio = primeiro horário entre os itens; se não houver, t_fim
    con.execute(f"""
        CREATE TABLE base AS
        WITH h AS (
            SELECT conversa_id, min(ts_item) AS primeiro_item FROM itens GROUP BY conversa_id
        ),
        c AS (
            SELECT conversation[1].turn_identifier AS conversa_id,
                   hashed_ip, header."user-agent" AS ua, "timestamp" AS t_fim
            FROM {src}
        )
        SELECT c.*, COALESCE(h.primeiro_item, c.t_fim) AS t_inicio,
            CASE
                WHEN ua ILIKE '%Android%' THEN 'Android'
                WHEN ua ILIKE '%iPhone%' OR ua ILIKE '%iPad%' THEN 'iOS'
                WHEN ua ILIKE '%Windows%' THEN 'Windows'
                WHEN ua ILIKE '%Mac OS X%' THEN 'macOS'
                WHEN ua ILIKE '%CrOS%' THEN 'ChromeOS'
                WHEN ua ILIKE '%Linux%' THEN 'Linux'
                ELSE 'Outro'
            END AS so,
            CASE
                WHEN ua ILIKE '%Edg/%' THEN 'Edge'
                WHEN ua ILIKE '%OPR/%' THEN 'Opera'
                WHEN ua ILIKE '%SamsungBrowser%' THEN 'Samsung'
                WHEN ua ILIKE '%Firefox/%' THEN 'Firefox'
                WHEN ua ILIKE '%Chrome/%' OR ua ILIKE '%CriOS/%' THEN 'Chrome'
                WHEN ua ILIKE '%Safari/%' THEN 'Safari'
                ELSE 'Outro'
            END AS navegador
        FROM c LEFT JOIN h USING (conversa_id)
    """)
    show("[MEDIDO] Âncora de início disponível",
         """SELECT count(*) conversas,
                   count(*) FILTER (WHERE t_inicio < t_fim) inicio_antes_do_fim,
                   count(*) FILTER (WHERE t_inicio = t_fim) inicio_igual_fim,
                   count(*) FILTER (WHERE t_inicio > t_fim) inicio_depois_do_fim
            FROM base""")

    fim_dados = "(SELECT max(t_fim) FROM base)"

    def retorno_por_sessao(chave: str, gap: str, col_ini: str) -> tuple[int, int]:
        # Nova sessão quando o início da conversa vem mais de `gap` depois do
        # maior fim visto até então para o mesmo usuário.
        return con.sql(f"""
            WITH u AS (SELECT {chave} AS usuario, {col_ini} AS ini, t_fim AS fim FROM base),
            m AS (
                SELECT *, max(fim) OVER (PARTITION BY usuario ORDER BY ini, fim
                          ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS prev_fim
                FROM u
            ),
            s AS (
                SELECT usuario, ini,
                       sum(CASE WHEN prev_fim IS NULL OR ini - prev_fim > {gap} THEN 1 ELSE 0 END)
                           OVER (PARTITION BY usuario ORDER BY ini, fim
                                 ROWS UNBOUNDED PRECEDING) AS sessao
                FROM m
            ),
            usr AS (
                SELECT usuario,
                       min(ini) FILTER (WHERE sessao = 1) AS primeira,
                       min(ini) FILTER (WHERE sessao = 2) AS segunda
                FROM s GROUP BY usuario
            )
            SELECT count(*), count(*) FILTER (WHERE segunda <= primeira + {JANELA})
            FROM usr WHERE primeira <= {fim_dados} - INTERVAL 7 DAY
        """).fetchall()[0]

    def retorno_outro_dia(chave: str, col_ini: str) -> tuple[int, int]:
        # Retorno = alguma conversa em data de calendário (no fuso) posterior à
        # da primeira conversa, dentro da janela.
        return con.sql(f"""
            WITH u AS (SELECT {chave} AS usuario, {col_ini} AS ini FROM base),
            p AS (SELECT usuario, min(ini) AS primeira FROM u GROUP BY usuario)
            SELECT count(*),
                   count(*) FILTER (WHERE EXISTS (
                       SELECT 1 FROM u
                       WHERE u.usuario = p.usuario
                         AND CAST(u.ini AS DATE) > CAST(p.primeira AS DATE)
                         AND u.ini <= p.primeira + {JANELA}))
            FROM p WHERE primeira <= {fim_dados} - INTERVAL 7 DAY
        """).fetchall()[0]

    escrever("\n== [MEDIDO sob cada PREMISSA] Retorno em 7 dias por regra de sessão")
    escrever("Âncoras: 'fim' = cada conversa datada pela coluna timestamp;"
             " 'inicio+fim' = início pelo primeiro horário entre os itens (se houver).")
    escrever("Sem corte por user-agents. IC 95% de Wilson, supondo usuários independentes.")
    escrever("definicao_usuario | ancora | regra | usuarios_elegiveis | voltaram_7d | taxa | ic95")
    for nome_def, chave in DEFINICOES_USUARIO.items():
        for nome_anc, col_ini in (("fim", "t_fim"), ("inicio+fim", "t_inicio")):
            linhas = [(nome, *retorno_por_sessao(chave, gap, col_ini))
                      for nome, gap in GAPS_SESSAO.items()]
            linhas.append(("outro_dia_calendario", *retorno_outro_dia(chave, col_ini)))
            for regra, n, k in linhas:
                lo, hi = wilson(k, n)
                escrever(f"{nome_def} | {nome_anc} | {regra} | {n} | {k} | {k / n:.1%}"
                         f" | [{lo:.1%}, {hi:.1%}]")

    out.close()
    print(f"\nRelatório salvo em {SAIDA}")


if __name__ == "__main__":
    main()