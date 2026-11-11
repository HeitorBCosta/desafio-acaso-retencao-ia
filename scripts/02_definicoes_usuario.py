"""
Testa definições de usuário e de sessão antes de escolher uma.

A base não tem identificador de usuário, então comparamos três jeitos de juntar as
conversas de uma mesma pessoa: só pelo IP, pelo IP com o user-agent completo e pelo IP
com sistema operacional e navegador. Cada um é cruzado com dois intervalos de sessão
(30 minutos e 2 horas) e com um corte opcional que tira IPs com muitos user-agents
diferentes (5, 10 ou 20 ou mais). Para cada combinação, o relatório mostra quantos
usuários aparecem e a taxa de retorno em 7 dias.

A ideia aqui é só medir o quanto o resultado depende da definição. A escolha final
está na BDR-001.

Como rodar:
    python scripts/02_definicoes_usuario.py

Lê:   data/bronze/wildchat_brazil.parquet
Gera: relatorios/02_definicoes_usuario.txt
"""
import math
import sys
from pathlib import Path

import duckdb

sys.stdout.reconfigure(encoding="utf-8")

BRAZIL = Path("data/bronze/wildchat_brazil.parquet")
SAIDA = Path("relatorios/02_definicoes_usuario.txt")

# Premissa: Não existe ID de usuário na base. Candidatos testados:
DEFINICOES_USUARIO = {
    "ip": "hashed_ip",
    "ip+ua_completo": "hashed_ip || '|' || ua",
    "ip+so+navegador": "hashed_ip || '|' || so || '|' || navegador",
}
# Premissa: Intervalo sem uso que separa duas sessões do mesmo usuário.
GAPS_SESSAO = {"30min": "INTERVAL 30 MINUTE", "2h": "INTERVAL 2 HOUR"}
# Premissa: Corte opcional: excluir conversas de IPs com N ou mais user-agents
# distintos. None = sem corte. Vários valores para medir a sensibilidade ao corte.
CORTES_UA_POR_IP = [None, 20, 10, 5]
# Premissa: Retorno = início de uma 2ª sessão em até 7 dias após o início da 1ª.
JANELA_RETORNO = "INTERVAL 7 DAY"
# Premissa: Datas em UTC. Fuso de análise ainda a decidir.
FUSO = "UTC"


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """IC 95% de Wilson para uma proporção. Supõe usuários independentes."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    centro = (p + z * z / (2 * n)) / (1 + z * z / n)
    meia = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return centro - meia, centro + meia


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

    escrever("Premissas desta execução:")
    escrever(f"  fuso: {FUSO}")
    escrever("  horário da conversa: coluna timestamp (último turno)")
    escrever(f"  retorno: 2ª sessão iniciada até {JANELA_RETORNO} após o início da 1ª")
    escrever("  elegíveis: usuários cuja 1ª conversa é pelo menos 7 dias anterior"
             " ao fim dos dados (senão a janela de 7 dias não foi observada inteira)")
    escrever("  IC: Wilson 95%, supondo usuários independentes")

    # Uma linha por conversa. Premissa: o único horário disponível é a coluna
    # timestamp (horário do último turno, segundo o enunciado): os timestamps por
    # turno vêm nulos (ver bloco de qualidade). A conversa é datada por ele.
    con.execute(f"""
        CREATE TABLE base AS
        WITH c AS (
            SELECT
                conversation[1].turn_identifier                     AS conversa_id,
                hashed_ip,
                header."user-agent"                                 AS ua,
                "timestamp"                                         AS t,
                len(conversation)                                   AS n_turnos_lista,
                len(list_filter(conversation, lambda x: x."timestamp" IS NOT NULL))
                                                                    AS n_turnos_com_timestamp
            FROM read_parquet('{BRAZIL.as_posix()}')
        )
        SELECT c.*,
            -- [DERIVADO] sistema operacional e navegador por busca de texto no
            -- user-agent; o que não casa com nenhuma regra fica 'Outro'.
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
            END AS navegador,
            ips.n_ua_no_ip
        FROM c
        JOIN (SELECT hashed_ip, count(DISTINCT ua) AS n_ua_no_ip FROM c GROUP BY 1) ips
          USING (hashed_ip)
    """)

    show("[MEDIDO] Qualidade: chaves e datas",
         """SELECT count(*) conversas,
                   count(DISTINCT conversa_id) conversa_id_distintos,
                   sum(n_turnos_lista) itens_na_lista_conversation,
                   sum(n_turnos_com_timestamp) itens_com_timestamp,
                   count(*) FILTER (WHERE t IS NULL) conversas_sem_timestamp,
                   max(t)::VARCHAR fim_dos_dados_utc
            FROM base""")
    show("[DERIVADO] Cobertura da regra de SO e navegador",
         """SELECT so, navegador, count(*) conversas,
                   round(100.0 * count(*) / sum(count(*)) OVER (), 1) pct
            FROM base GROUP BY ALL ORDER BY conversas DESC LIMIT 15""")
    show("[MEDIDO] Distribuição de user-agents distintos por IP",
         """SELECT faixa, count(*) ips, sum(conversas) conversas
            FROM (SELECT hashed_ip, count(*) conversas, max(n_ua_no_ip) n_ua,
                         CASE WHEN max(n_ua_no_ip) = 1 THEN '1'
                              WHEN max(n_ua_no_ip) <= 4 THEN '2-4'
                              WHEN max(n_ua_no_ip) <= 9 THEN '5-9'
                              WHEN max(n_ua_no_ip) <= 19 THEN '10-19'
                              ELSE '20+' END AS faixa
                  FROM base GROUP BY hashed_ip)
            GROUP BY faixa ORDER BY min(n_ua)""")
    show("[MEDIDO] Quantas chaves de usuário cada definição produz",
         """SELECT count(DISTINCT hashed_ip) ip,
                   count(DISTINCT hashed_ip || '|' || ua) ip_ua_completo,
                   count(DISTINCT hashed_ip || '|' || so || '|' || navegador) ip_so_navegador
            FROM base""")
    show("[MEDIDO] Chaves ip+so+navegador que reúnem mais de um user-agent completo",
         """SELECT count(*) chaves_ip_so_navegador,
                   count(*) FILTER (WHERE n_ua > 1) com_mais_de_um_ua_completo
            FROM (SELECT hashed_ip, so, navegador, count(DISTINCT ua) n_ua
                  FROM base GROUP BY ALL)""")

    resultados = []
    for nome_def, chave in DEFINICOES_USUARIO.items():
        for nome_gap, gap in GAPS_SESSAO.items():
            for corte in CORTES_UA_POR_IP:
                filtro = "" if corte is None else f"WHERE n_ua_no_ip < {corte}"
                n, k, uma = con.sql(f"""
                    WITH u AS (
                        SELECT {chave} AS usuario, t FROM base {filtro}
                    ),
                    marcado AS (
                        SELECT *,
                            CASE WHEN prev_t IS NULL OR t - prev_t > {gap}
                                 THEN 1 ELSE 0 END AS nova_sessao
                        FROM (SELECT *, lag(t) OVER (
                                  PARTITION BY usuario ORDER BY t) AS prev_t
                              FROM u)
                    ),
                    sess AS (
                        SELECT usuario, t,
                               sum(nova_sessao) OVER (PARTITION BY usuario ORDER BY t
                                                      ROWS UNBOUNDED PRECEDING) AS sessao
                        FROM marcado
                    ),
                    usr AS (
                        SELECT usuario,
                               min(t) FILTER (WHERE sessao = 1) AS primeira,
                               min(t) FILTER (WHERE sessao = 2) AS segunda,
                               count(*) AS conversas
                        FROM sess GROUP BY usuario
                    )
                    SELECT count(*),
                           count(*) FILTER (WHERE segunda <= primeira + {JANELA_RETORNO}),
                           count(*) FILTER (WHERE conversas = 1)
                    FROM usr
                    WHERE primeira <= (SELECT max(t) FROM base) - INTERVAL 7 DAY
                """).fetchall()[0]
                lo, hi = wilson(k, n)
                resultados.append((nome_def, nome_gap, corte, n, uma, k, k / n, lo, hi))

    escrever("\n== [MEDIDO sob cada PREMISSA] Retorno em 7 dias")
    escrever("definicao_usuario | gap_sessao | excluir_ip_com_n_ua_ou_mais | usuarios_elegiveis"
             " | com_1_conversa | voltaram_7d | taxa | ic95")
    for d, g, c, n, uma, k, p, lo, hi in resultados:
        corte = "sem corte" if c is None else str(c)
        escrever(f"{d} | {g} | {corte} | {n} | {uma} | {k} | {p:.1%} | [{lo:.1%}, {hi:.1%}]")

    out.close()
    print(f"\nRelatório salvo em {SAIDA}")


if __name__ == "__main__":
    main()
