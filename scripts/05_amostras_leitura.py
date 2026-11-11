"""
Gera listas para leitura manual, a partir das primeiras conversas do script 04:

    1. textos mais frequentes entre as respostas curtas (< 50 caracteres)
    2. textos mais frequentes entre as perguntas curtas (< 20 caracteres)
    3. amostra das conversas com idioma "Outros"
    4. todas as conversas marcadas como recusa
    5. amostra dirigida: não marcadas como recusa, mas com palavras-chave de recusa
    6. conferência dos campos de mensagem sem pedido (BDR-004): textos marcados como
       saudação/teste e textos curtos que nenhuma regra marcou
    7. primeira mensagem vazia: idioma, turnos e o que a IA respondeu
    8. respostas que começam com vírgula

Rode o script 04 antes: este script lê os campos que ele grava no silver.

Uso:
    python scripts/05_amostras_leitura.py

Entradas: data/silver/primeira_conversa.parquet, data/bronze/wildchat_brazil.parquet
Saídas:   data/amostras/05_*.csv (têm texto; não versionar)
          relatorios/05_amostras_leitura.txt (só contagens, sem texto)

CSVs com separador ';' e codificação UTF-8 com BOM, para abrir direto no Excel.
"""
import csv
import sys
from pathlib import Path

import duckdb

sys.stdout.reconfigure(encoding="utf-8")

SILVER = Path("data/silver/primeira_conversa.parquet")
BRAZIL = Path("data/bronze/wildchat_brazil.parquet")
AMOSTRAS = Path("data/amostras")
RELATORIO = Path("relatorios/05_amostras_leitura.txt")
SEMENTE = 0.42
TOP_N = 30
N_IDIOMA = 100
N_DIRIGIDA = 150

# Palavras-chave AMPLAS de recusa, só para achar recusas que a regra v1 deixou
# passar. Não é a regra de recusa: é uma rede mais larga para a amostra dirigida.
PALAVRAS_RECUSA = (
    r"n[ãa]o posso|n[ãa]o consigo|n[ãa]o sou capaz|desculp|sinto muito|lamento"
    r"|sorry|unable|cannot|can't|apologi|lo siento|no puedo"
)


def main() -> None:
    con = duckdb.connect()
    con.execute("SET TimeZone = 'UTC'")
    AMOSTRAS.mkdir(parents=True, exist_ok=True)
    RELATORIO.parent.mkdir(parents=True, exist_ok=True)
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

    def salvar_csv(nome: str, sql: str) -> int:
        rel = con.sql(sql)
        linhas = rel.fetchall()
        caminho = AMOSTRAS / f"{nome}.csv"
        with caminho.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(rel.columns)
            w.writerows(linhas)
        return len(linhas)

    # Primeira conversa (do silver) + textos (do bronze), ligados por conversa_id.
    con.execute(f"""
        CREATE TABLE p AS
        SELECT s.conversa_id, s.idioma, s.idioma_grupo, s.recusa, s.recusa_padrao,
               s.pergunta_chars, s.resposta_chars, s.turnos, s.redacted,
               s.pergunta_vazia, s.pergunta_vazia_tipo, s.pergunta_saudacao, s.pergunta_teste,
               b.pergunta, b.resposta
        FROM read_parquet('{SILVER.as_posix()}') s
        JOIN (
            SELECT conversation[1].turn_identifier AS conversa_id,
                   conversation[1]."content" AS pergunta,
                   list_filter(conversation, lambda x: x."role" = 'assistant')[1]."content" AS resposta
            FROM read_parquet('{BRAZIL.as_posix()}')
        ) b USING (conversa_id)
    """)
    show("[MEDIDO] Ligação silver x bronze",
         "SELECT count(*) linhas, count(DISTINCT conversa_id) conversas FROM p")

    # 1. Respostas curtas
    show("[MEDIDO] Primeiras respostas por faixa de tamanho (caracteres)",
         """SELECT (resposta_chars // 10) * 10 AS faixa_inicio, count(*) usuarios
            FROM p WHERE resposta_chars < 100 GROUP BY 1 ORDER BY 1""")
    show("[MEDIDO] Respostas < 50 caracteres: textos distintos",
         """SELECT count(*) usuarios, count(DISTINCT trim(resposta)) textos_distintos
            FROM p WHERE resposta_chars < 50""")
    n = salvar_csv("05_respostas_curtas_frequentes", f"""
        SELECT trim(resposta) AS texto_resposta, count(*) AS usuarios,
               min(resposta_chars) AS caracteres
        FROM p WHERE resposta_chars < 50
        GROUP BY 1 ORDER BY usuarios DESC, texto_resposta LIMIT {TOP_N}""")
    escrever(f"\n05_respostas_curtas_frequentes.csv: {n} textos (top {TOP_N} por frequência)")

    # 2. Perguntas curtas
    show("[MEDIDO] Perguntas < 20 caracteres: textos distintos (comparados em minúsculas, sem espaços nas pontas)",
         """SELECT count(*) usuarios, count(DISTINCT lower(trim(pergunta))) textos_distintos
            FROM p WHERE pergunta_chars < 20""")
    n = salvar_csv("05_perguntas_curtas_frequentes", f"""
        SELECT lower(trim(pergunta)) AS texto_pergunta, count(*) AS usuarios
        FROM p WHERE pergunta_chars < 20
        GROUP BY 1 ORDER BY usuarios DESC, texto_pergunta LIMIT {TOP_N}""")
    escrever(f"05_perguntas_curtas_frequentes.csv: {n} textos (top {TOP_N} por frequência)")

    # 3. Idioma "Outros"
    show("[MEDIDO] Idioma 'Outros' por rótulo original",
         """SELECT idioma, count(*) usuarios FROM p WHERE idioma_grupo = 'Outros'
            GROUP BY 1 ORDER BY usuarios DESC""")
    con.execute(f"SELECT setseed({SEMENTE})").fetchall()
    n = salvar_csv("05_idioma_outros", f"""
        SELECT conversa_id, idioma AS idioma_na_base,
               left(regexp_replace(pergunta, '\\s+', ' ', 'g'), 400) AS pergunta_trecho,
               left(regexp_replace(resposta, '\\s+', ' ', 'g'), 400) AS resposta_trecho,
               NULL AS idioma_que_voce_identifica, NULL AS comentario
        FROM (SELECT *, random() r FROM p WHERE idioma_grupo = 'Outros')
        ORDER BY r LIMIT {N_IDIOMA}""")
    escrever(f"05_idioma_outros.csv: {n} conversas (amostra aleatória)")

    # 4. Todas as recusas marcadas
    n = salvar_csv("05_recusa_todas_marcadas", """
        SELECT conversa_id, recusa_padrao,
               left(regexp_replace(pergunta, '\\s+', ' ', 'g'), 400) AS pergunta_trecho,
               left(regexp_replace(resposta, '\\s+', ' ', 'g'), 800) AS resposta_trecho,
               NULL AS e_recusa_sim_nao, NULL AS comentario
        FROM p WHERE recusa ORDER BY recusa_padrao, conversa_id""")
    escrever(f"05_recusa_todas_marcadas.csv: {n} conversas (todas)")

    # 5. Amostra dirigida
    show("[MEDIDO] Não marcadas como recusa, com palavra-chave ampla de recusa na resposta",
         f"""SELECT count(*) FILTER (WHERE NOT recusa) nao_marcadas,
                    count(*) FILTER (WHERE NOT recusa
                        AND regexp_matches(lower(resposta), '{PALAVRAS_RECUSA.replace("'", "''")}'))
                        nao_marcadas_com_palavra_chave
             FROM p""")
    con.execute(f"SELECT setseed({SEMENTE})").fetchall()
    n = salvar_csv("05_recusa_dirigida", f"""
        SELECT conversa_id,
               left(regexp_replace(pergunta, '\\s+', ' ', 'g'), 400) AS pergunta_trecho,
               left(regexp_replace(resposta, '\\s+', ' ', 'g'), 800) AS resposta_trecho,
               NULL AS e_recusa_sim_nao, NULL AS comentario
        FROM (SELECT *, random() r FROM p
              WHERE NOT recusa
                AND regexp_matches(lower(resposta), '{PALAVRAS_RECUSA.replace("'", "''")}'))
        ORDER BY r LIMIT {N_DIRIGIDA}""")
    escrever(f"05_recusa_dirigida.csv: {n} conversas (até {N_DIRIGIDA}, aleatórias entre as com palavra-chave)")

    # 6. Conferência dos campos de mensagem sem pedido
    show("[DERIVADO] Primeira mensagem sem pedido (campos do script 04)",
         """SELECT count(*) FILTER (WHERE pergunta_vazia) vazia,
                   count(*) FILTER (WHERE pergunta_saudacao) so_saudacao,
                   count(*) FILTER (WHERE pergunta_teste) so_teste,
                   count(*) FILTER (WHERE pergunta_chars < 20 AND NOT (pergunta_vazia
                       OR pergunta_saudacao OR pergunta_teste)) curtas_sem_marca
            FROM p""")
    n = salvar_csv("05_saudacao_teste_textos", """
        SELECT CASE WHEN pergunta_saudacao THEN 'saudacao' ELSE 'teste' END AS regra,
               lower(trim(pergunta)) AS texto_pergunta, count(*) AS usuarios,
               NULL AS correto_sim_nao
        FROM p WHERE pergunta_saudacao OR pergunta_teste
        GROUP BY ALL ORDER BY regra, usuarios DESC, texto_pergunta""")
    escrever(f"05_saudacao_teste_textos.csv: {n} textos distintos marcados (todos)")
    n = salvar_csv("05_curtas_sem_marca", f"""
        SELECT lower(trim(pergunta)) AS texto_pergunta, count(*) AS usuarios,
               NULL AS deveria_ser_saudacao_ou_teste
        FROM p WHERE pergunta_chars < 20
                 AND NOT (pergunta_vazia OR pergunta_saudacao OR pergunta_teste)
        GROUP BY 1 ORDER BY usuarios DESC, texto_pergunta LIMIT {TOP_N}""")
    escrever(f"05_curtas_sem_marca.csv: {n} textos (top {TOP_N}; perguntas < 20 caracteres sem marca)")

    # 7. Primeira mensagem vazia
    show("[MEDIDO] Primeira mensagem vazia, por idioma atribuído pela base",
         """SELECT idioma, count(*) usuarios FROM p WHERE pergunta_vazia
            GROUP BY 1 ORDER BY usuarios DESC""")
    show("[MEDIDO] Primeira mensagem vazia, por nº de turnos",
         """SELECT CASE WHEN turnos >= 5 THEN '5+' ELSE turnos::VARCHAR END faixa, count(*) usuarios
            FROM p WHERE pergunta_vazia GROUP BY faixa ORDER BY min(turnos)""")
    n = salvar_csv("05_resposta_a_pergunta_vazia", f"""
        SELECT left(regexp_replace(trim(resposta), '\\s+', ' ', 'g'), 300) AS resposta_trecho,
               count(*) AS usuarios
        FROM p WHERE pergunta_vazia
        GROUP BY 1 ORDER BY usuarios DESC, resposta_trecho LIMIT {TOP_N}""")
    escrever(f"05_resposta_a_pergunta_vazia.csv: {n} respostas (top {TOP_N})")
    show("[DERIVADO] Primeira mensagem vazia, por tipo (campo do script 04)",
         """SELECT pergunta_vazia_tipo, count(*) usuarios FROM p WHERE pergunta_vazia
            GROUP BY 1 ORDER BY usuarios DESC""")
    n = salvar_csv("05_pergunta_vazia_todas", """
        SELECT conversa_id, pergunta_vazia_tipo AS tipo_pela_regra, idioma, turnos,
               left(regexp_replace(trim(resposta), '\\s+', ' ', 'g'), 400) AS resposta_trecho,
               NULL AS tipo_correto_sim_nao
        FROM p WHERE pergunta_vazia ORDER BY tipo_pela_regra, conversa_id""")
    escrever(f"05_pergunta_vazia_todas.csv: {n} conversas (todas, com o tipo dado pela regra)")

    # 8. Respostas que começam com vírgula
    show("[MEDIDO] Primeira resposta começando com vírgula",
         """SELECT count(*) usuarios, count(*) FILTER (WHERE redacted) com_redacted
            FROM p WHERE starts_with(trim(resposta), ',')""")
    n = salvar_csv("05_resposta_comeca_virgula", """
        SELECT conversa_id, redacted, turnos,
               left(regexp_replace(pergunta, '\\s+', ' ', 'g'), 400) AS pergunta_trecho,
               left(regexp_replace(resposta, '\\s+', ' ', 'g'), 400) AS resposta_trecho
        FROM p WHERE starts_with(trim(resposta), ',') ORDER BY conversa_id""")
    escrever(f"05_resposta_comeca_virgula.csv: {n} conversas (todas)")

    out.close()
    print(f"\nRelatório: {RELATORIO}")


if __name__ == "__main__":
    main()