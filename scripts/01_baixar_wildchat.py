"""
Baixa o WildChat-1M (Hugging Face, allenai/WildChat-1M) e extrai o recorte Brasil.

Uso:
    pip install huggingface_hub duckdb
    python scripts/01_baixar_wildchat.py

Saídas:
    data/raw/wildchat-1m/...            parquets originais (~3,4 GB), base bruta intocada
    data/bronze/wildchat_brazil.parquet recorte country = 'Brazil', todas as colunas
    relatorios/perfil_brasil.txt        primeiro perfil do recorte (UTF-8)
"""
import sys
from pathlib import Path

import duckdb
from huggingface_hub import snapshot_download

# O console do Windows usa cp1252 e não imprime as bordas das tabelas do DuckDB.
sys.stdout.reconfigure(encoding="utf-8")

RAW_DIR = Path("data/raw/wildchat-1m")
BRAZIL = Path("data/bronze/wildchat_brazil.parquet")
PERFIL = Path("relatorios/perfil_brasil.txt")


def baixar() -> None:
    # Dataset público (ODC-BY), sem login. Retoma de onde parou se cair.
    snapshot_download(
        repo_id="allenai/WildChat-1M",
        repo_type="dataset",
        allow_patterns=["*.parquet"],
        local_dir=RAW_DIR,
    )


def extrair_brasil(con: duckdb.DuckDBPyConnection) -> None:
    BRAZIL.parent.mkdir(parents=True, exist_ok=True)
    con.execute(f"""
        COPY (
            SELECT * FROM read_parquet('{RAW_DIR.as_posix()}/**/*.parquet')
            WHERE country = 'Brazil'
        ) TO '{BRAZIL.as_posix()}' (FORMAT parquet, COMPRESSION zstd)
    """)


def perfil(con: duckdb.DuckDBPyConnection) -> None:
    raw = f"read_parquet('{RAW_DIR.as_posix()}/**/*.parquet')"
    br = f"read_parquet('{BRAZIL.as_posix()}')"

    PERFIL.parent.mkdir(parents=True, exist_ok=True)
    saida = PERFIL.open("w", encoding="utf-8")

    def show(titulo: str, sql: str) -> None:
        try:
            rel = con.sql(sql)
            linhas = [" | ".join(rel.columns)]
            linhas += [" | ".join(str(v) for v in row) for row in rel.fetchall()]
            texto = "\n".join(linhas)
        except duckdb.Error as e:  # uma consulta com erro não derruba o perfil inteiro
            texto = f"ERRO: {e}"
        bloco = f"\n== {titulo}\n{texto}\n"
        print(bloco)
        saida.write(bloco)

    show("Base inteira: linhas e top 10 países",
         f"SELECT country, count(*) n FROM {raw} GROUP BY 1 ORDER BY n DESC LIMIT 10")
    show("Brasil: tamanho e período",
         f"""SELECT count(*) conversas,
                    count(DISTINCT conversation_hash) hashes_distintos,
                    count(DISTINCT hashed_ip) ips_distintos,
                    min(timestamp)::VARCHAR inicio_utc, max(timestamp)::VARCHAR fim_utc
             FROM {br}""")
    show("Brasil: por modelo",
         f"SELECT model, count(*) n FROM {br} GROUP BY 1 ORDER BY n DESC")
    show("Brasil: top 10 idiomas",
         f"SELECT language, count(*) n FROM {br} GROUP BY 1 ORDER BY n DESC LIMIT 10")
    show("Brasil: conversas por mês",
         f"SELECT strftime(timestamp, '%Y-%m') mes, count(*) n FROM {br} GROUP BY 1 ORDER BY 1")
    show("Brasil: distribuição de conversas por IP",
         f"""SELECT count(*) ips, quantile_cont(n, [0.5, 0.9, 0.99]) p50_p90_p99, max(n) maximo,
                    sum(CASE WHEN n = 1 THEN 1 ELSE 0 END) ips_com_1_conversa
             FROM (SELECT hashed_ip, count(*) n FROM {br} GROUP BY 1)""")
    show("Brasil: top 10 IPs por volume",
         f"""SELECT row_number() OVER (ORDER BY count(*) DESC) posicao, count(*) conversas,
                    round(100.0 * count(*) / sum(count(*)) OVER (), 1) pct_base,
                    count(DISTINCT header."user-agent") user_agents,
                    count(DISTINCT strftime(timestamp, '%Y-%m-%d')) dias_ativos,
                    min(timestamp)::DATE::VARCHAR primeiro_dia,
                    max(timestamp)::DATE::VARCHAR ultimo_dia,
                    round(avg(turn), 1) turnos_medios
             FROM {br} GROUP BY hashed_ip ORDER BY conversas DESC LIMIT 10""")
    show("Brasil: IP e user-agent variam dentro da mesma conversa?",
         f"""SELECT count(*) conversas,
                    count(*) FILTER (WHERE len(list_distinct(
                        list_transform(conversation, lambda t: t.hashed_ip))) > 1) ip_varia,
                    count(*) FILTER (WHERE len(list_distinct(
                        list_transform(conversation, lambda t: t.header."user-agent"))) > 1) ua_varia,
                    count(*) FILTER (WHERE header."user-agent" IS NULL) ua_nulo
             FROM {br}""")
    show("Brasil: conversation_hash repetido",
         f"""SELECT n_repeticoes, count(*) hashes FROM (
                 SELECT conversation_hash, count(*) n_repeticoes FROM {br} GROUP BY 1)
             GROUP BY 1 ORDER BY 1 LIMIT 10""")
    show("Brasil: esquema",
         f"DESCRIBE SELECT * FROM {br}")
    saida.close()
    print(f"\nPerfil salvo em {PERFIL}")


if __name__ == "__main__":
    baixar()
    con = duckdb.connect()
    # Datas sempre em UTC até decidirmos o fuso da análise (premissa a registrar).
    con.execute("SET TimeZone = 'UTC'")
    extrair_brasil(con)
    perfil(con)
