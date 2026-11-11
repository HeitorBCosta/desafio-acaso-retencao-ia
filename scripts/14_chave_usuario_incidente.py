"""
Testa na base real o mecanismo suspeito no incidente da seção 4.2 do enunciado.

No incidente, a carga de referência identifica o usuário por hashed_ip + user-agent
completo, e o relatório semanal do time de dados identifica só por hashed_ip. Quando o
navegador de alguém se atualiza, o user-agent muda (muda o número da versão). Pela
chave da carga, essa pessoa vira um usuário "novo", mesmo já tendo usado o
assistente. Isso infla o número de novos e derruba a taxa de retorno.

Os números do enunciado não são desta base: lá são cerca de 1.200 novos por semana, e
aqui são dezenas. Por isso o script não tenta reproduzir o incidente. Ele mede, nas
conversas do Brasil, quanto o número de novos e o retorno mudam conforme a chave:

  ip            só hashed_ip (como o relatório semanal)
  ip+ua         hashed_ip + user-agent completo (como a carga do incidente)
  ip+so+nav     hashed_ip + sistema + navegador, sem versão (nossa BDR-001)

Entre os novos pela chave ip+ua, o script conta quantos tinham o mesmo IP já visto
antes ("IP já visto") e quantos tinham o mesmo IP, sistema e navegador já vistos, ou
seja, só o texto do user-agent mudou ("só o user-agent mudou"; quase sempre a versão,
mas pode ser outro detalhe, como o modelo do celular).

Para isolar o efeito da chave, a regra de retorno é a do endpoint do incidente para as
três chaves: primeira vez = menor horário do último turno; voltou = alguma conversa
mais de 1 hora e até 7 dias depois. Semanas de segunda a domingo, em UTC, como no
endpoint. Isto é descritivo, sem leitura fixada: serve para mostrar se o mecanismo
existe em dados reais e qual o tamanho dele.

Como rodar:
    python scripts/14_chave_usuario_incidente.py

Lê:   data/bronze/wildchat_brazil.parquet
Gera: relatorios/14_chave_usuario_incidente.txt
"""
import os
import sys
from pathlib import Path

import duckdb

sys.stdout.reconfigure(encoding="utf-8")

RAIZ = Path(__file__).resolve().parents[1]
os.chdir(RAIZ)

BRAZIL = Path("data/bronze/wildchat_brazil.parquet")
RELATORIO = Path("relatorios/14_chave_usuario_incidente.txt")
SEMANAS_INCIDENTE = ("2023-11-06", "2023-11-13", "2023-11-20")
CHAVES = {"ip": "k_ip", "ip+ua": "k_ua", "ip+so+nav": "k_sn"}


def main() -> None:
    con = duckdb.connect()
    con.execute("SET TimeZone = 'UTC'")
    RELATORIO.parent.mkdir(parents=True, exist_ok=True)
    out = RELATORIO.open("w", encoding="utf-8")

    def escrever(s: str = "") -> None:
        print(s)
        out.write(s + "\n")

    # Sistema e navegador pela mesma regra dos scripts 04 e 06 (BDR-001).
    con.execute(f"""
        CREATE TABLE conv AS
        WITH c AS (
            SELECT hashed_ip, COALESCE(header."user-agent", '') AS ua, "timestamp" AS t
            FROM read_parquet('{BRAZIL.as_posix()}')
        )
        SELECT hashed_ip, t,
               hashed_ip AS k_ip,
               hashed_ip || '|' || ua AS k_ua,
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
               END AS k_sn
        FROM c
    """)

    # Uma tabela por chave: primeira vez, semana, elegível e voltou (regra do endpoint).
    for nome, col in CHAVES.items():
        tabela = "p_" + col
        con.execute(f"""
            CREATE TABLE {tabela} AS
            WITH p AS (
                SELECT {col} AS u, any_value(hashed_ip) AS ip, any_value(k_sn) AS sn, min(t) AS p0
                FROM conv GROUP BY {col}
            )
            SELECT u, ip, sn, p0,
                   strftime(date_trunc('week', p0), '%Y-%m-%d') AS semana,
                   p0 <= (SELECT max(t) FROM conv) - INTERVAL 7 DAY AS elegivel,
                   EXISTS (SELECT 1 FROM conv c
                           WHERE c.{col} = p.u
                             AND c.t > p.p0 + INTERVAL 1 HOUR
                             AND c.t <= p.p0 + INTERVAL 7 DAY) AS voltou
            FROM p
        """)

    # Entre os novos pela chave ip+ua: IP já visto antes e "só a versão mudou".
    con.execute("""
        CREATE TABLE falso_novo AS
        SELECT p.u, p.semana, p.elegivel,
               EXISTS (SELECT 1 FROM conv c WHERE c.hashed_ip = p.ip AND c.t < p.p0) AS ip_ja_visto,
               EXISTS (SELECT 1 FROM conv c WHERE c.k_sn = p.sn AND c.t < p.p0) AS so_versao
        FROM p_k_ua p
    """)

    con.execute("""
        CREATE TABLE semanal AS
        WITH a AS (SELECT semana, count(*) n, count(*) FILTER (WHERE voltou) v
                   FROM p_k_ip WHERE elegivel GROUP BY 1),
             b AS (SELECT semana, count(*) n, count(*) FILTER (WHERE voltou) v
                   FROM p_k_ua WHERE elegivel GROUP BY 1),
             c AS (SELECT semana, count(*) n, count(*) FILTER (WHERE voltou) v
                   FROM p_k_sn WHERE elegivel GROUP BY 1),
             f AS (SELECT semana, count(*) FILTER (WHERE ip_ja_visto) ip_ja_visto,
                          count(*) FILTER (WHERE so_versao) so_versao
                   FROM falso_novo WHERE elegivel GROUP BY 1)
        SELECT b.semana,
               a.n AS novos_ip, a.v AS voltaram_ip,
               b.n AS novos_ip_ua, b.v AS voltaram_ip_ua,
               c.n AS novos_ip_so_nav, c.v AS voltaram_ip_so_nav,
               f.ip_ja_visto, f.so_versao
        FROM b LEFT JOIN a USING (semana) LEFT JOIN c USING (semana) LEFT JOIN f USING (semana)
    """)

    def pct(v, n) -> str:
        return f"{v / n:.1%}" if n else "—"

    escrever("Regra de retorno igual para as três chaves: a do endpoint do incidente "
             "(último turno; mais de 1 h e até 7 dias). Semanas em UTC.")

    escrever("\n== [MEDIDO] Base inteira (só quem tem 7 dias de base pela frente)")
    escrever("chave | novos | voltaram | retorno")
    for nome, col in CHAVES.items():
        n, v = con.execute(
            f"SELECT count(*), count(*) FILTER (WHERE voltou) FROM p_{col} WHERE elegivel").fetchall()[0]
        escrever(f"{nome} | {n} | {v} | {pct(v, n)}")
    n, ipv, sov = con.execute("""
        SELECT count(*), count(*) FILTER (WHERE ip_ja_visto), count(*) FILTER (WHERE so_versao)
        FROM falso_novo WHERE elegivel""").fetchall()[0]
    escrever(f"Novos pela chave ip+ua com IP já visto antes: {ipv} de {n} ({pct(ipv, n)}); "
             f"mesmo sistema e navegador, só o user-agent mudou: {sov} ({pct(sov, n)})")

    escrever("\n== [MEDIDO] Semanas do incidente (06/11, 13/11 e 20/11/2023)")
    escrever("semana | novos ip | ret. ip | novos ip+ua | ret. ip+ua | novos ip+so+nav | ret. ip+so+nav "
             "| ip+ua com IP já visto | só o user-agent mudou")
    lista = ", ".join(f"'{s}'" for s in SEMANAS_INCIDENTE)
    for r in con.execute(f"SELECT * FROM semanal WHERE semana IN ({lista}) ORDER BY semana").fetchall():
        s, ni, vi, nu, vu, ns, vs, fj, fv = r
        escrever(f"{s} | {ni} | {pct(vi, ni)} | {nu} | {pct(vu, nu)} | {ns} | {pct(vs, ns)} | {fj} | {fv}")

    escrever("\n== [MEDIDO] Semanas com mais novos inflados pela chave ip+ua (pelo menos 20 novos por ip)")
    escrever("semana | novos ip | novos ip+ua | excesso | ret. ip | ret. ip+ua | só o user-agent mudou")
    for r in con.execute("""
        SELECT semana, novos_ip, novos_ip_ua, novos_ip_ua - novos_ip AS excesso,
               voltaram_ip, voltaram_ip_ua, so_versao
        FROM semanal WHERE novos_ip >= 20
        ORDER BY (novos_ip_ua - novos_ip) * 1.0 / novos_ip DESC, semana LIMIT 5
    """).fetchall():
        s, ni, nu, ex, vi, vu, fv = r
        escrever(f"{s} | {ni} | {nu} | +{ex} ({ex / ni:.0%}) | {pct(vi, ni)} | {pct(vu, nu)} | {fv}")

    escrever("\n== [MEDIDO] Série semanal completa")
    escrever("semana | novos_ip | voltaram_ip | novos_ip_ua | voltaram_ip_ua | novos_ip_so_nav | "
             "voltaram_ip_so_nav | ip_ja_visto | so_versao")
    for r in con.execute("SELECT * FROM semanal ORDER BY semana").fetchall():
        escrever(" | ".join(str(v) for v in r))

    out.close()
    print(f"\nRelatório: {RELATORIO}")


if __name__ == "__main__":
    main()
