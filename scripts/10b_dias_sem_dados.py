"""
A queda de 17/07 a 13/08/2023 é de usuário que não voltou ou de conversa que não foi
registrada?

O retorno é medido pelas conversas que estão na base. Se a coleta parou alguns dias
logo depois do período, quem voltou nesses dias aparece como "não voltou". Este script
conta as conversas de TODOS os usuários do Brasil por dia (horário de Brasília) no
intervalo inteiro da base e lista os dias sem nenhuma conversa.

Leitura fixada antes de rodar [PREMISSA]:
    - dias sem conversa dentro da janela de retorno do período (17/07 a 20/08/2023)
      -> parte da queda pode ser falha de registro; o achado vira ressalva de dados
    - nenhum dia sem conversa na janela -> registro contínuo; falha de coleta deixa
      de explicar a queda (não exclui queda parcial de volume)

Uso:
    python scripts/10b_dias_sem_dados.py

Entrada: data/bronze/wildchat_brazil.parquet
Saída:   relatorios/10b_dias_sem_dados.txt
"""
import sys
from pathlib import Path

import duckdb

sys.stdout.reconfigure(encoding="utf-8")

BRAZIL = Path("data/bronze/wildchat_brazil.parquet")
RELATORIO = Path("relatorios/10b_dias_sem_dados.txt")
JANELA = ("2023-07-17", "2023-08-20")   # período + 7 dias de retorno da última semana


def main() -> None:
    con = duckdb.connect()
    con.execute("SET TimeZone = 'UTC'")
    con.execute(f"""
        CREATE TABLE dia AS
        WITH c AS (
            SELECT CAST(timezone('America/Sao_Paulo', "timestamp") AS DATE) AS d
            FROM read_parquet('{BRAZIL.as_posix()}')
        ),
        cal AS (
            SELECT CAST(generate_series AS DATE) AS d
            FROM generate_series((SELECT min(d) FROM c)::TIMESTAMP, (SELECT max(d) FROM c)::TIMESTAMP,
                                 INTERVAL 1 DAY)
        )
        SELECT cal.d, count(c.d) AS conversas
        FROM cal LEFT JOIN c USING (d)
        GROUP BY cal.d ORDER BY cal.d
    """)

    RELATORIO.parent.mkdir(parents=True, exist_ok=True)
    out = RELATORIO.open("w", encoding="utf-8")

    def escrever(s: str = "") -> None:
        print(s)
        out.write(s + "\n")

    ini, fim, dias, total, med = con.execute("""
        SELECT min(d)::VARCHAR, max(d)::VARCHAR, count(*), sum(conversas), median(conversas) FROM dia
    """).fetchall()[0]
    escrever(f"Base: {ini} a {fim} | {dias} dias | {total} conversas | mediana {med} por dia")

    zeros = con.execute("SELECT d::VARCHAR FROM dia WHERE conversas = 0 ORDER BY d").fetchall()
    escrever(f"\nDias sem nenhuma conversa: {len(zeros)}")
    for (d,) in zeros:
        escrever(f"  {d}")

    escrever(f"\n== Janela do período de queda ({JANELA[0]} a {JANELA[1]})")
    linhas = con.execute(f"""
        SELECT d::VARCHAR, conversas FROM dia
        WHERE d BETWEEN DATE '{JANELA[0]}' AND DATE '{JANELA[1]}' ORDER BY d
    """).fetchall()
    for d, n in linhas:
        escrever(f"  {d} | {n}{'  <- sem conversa' if n == 0 else ''}")
    zeros_janela = sum(1 for _, n in linhas if n == 0)

    escrever("\n== Conversas por semana (segunda a domingo), base inteira")
    for s, n in con.execute("""
        SELECT strftime(date_trunc('week', d), '%Y-%m-%d'), sum(conversas)
        FROM dia GROUP BY 1 ORDER BY 1
    """).fetchall():
        escrever(f"  {s} | {n}")

    escrever("\n== Aplicação da leitura fixada")
    if zeros_janela:
        escrever(f"{zeros_janela} dia(s) sem conversa na janela: parte da queda pode ser falha de registro.")
    else:
        escrever("Nenhum dia sem conversa na janela: registro contínuo; falha de coleta deixa de explicar "
                 "a queda (não exclui queda parcial de volume).")
    out.close()
    print(f"\nRelatório: {RELATORIO}")


if __name__ == "__main__":
    main()