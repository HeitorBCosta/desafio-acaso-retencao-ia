"""
Monta os campos da primeira conversa de cada usuário, todos calculados por regra.

Usuário é o IP com sistema operacional e navegador (BDR-001), e a primeira experiência
é a primeira conversa dele (BDR-002). Para essa conversa o script calcula modelo,
número de turnos, horário e dia da semana em Brasília, idioma, tamanho da pergunta e
da resposta, presença de código, sinais de recusa e o tipo da primeira mensagem
(vazia, só cumprimento, só teste ou pedido). Os rótulos lidos à mão para mensagens
vazias, em docs/rotulos, substituem a regra quando existem.

O resultado tem uma linha por usuário e nenhum texto de conversa. As amostras com
texto, usadas para conferir as regras, vão para data/amostras, que fica fora do Git.

Como rodar:
    python scripts/04_campos_primeira_conversa.py

Lê:   data/bronze/wildchat_brazil.parquet, docs/rotulos/pergunta_vazia_tipo.csv
Gera: data/silver/primeira_conversa.parquet
      relatorios/04_campos_primeira_conversa.txt
      data/amostras/*.csv
"""
import sys
from pathlib import Path

import duckdb

sys.stdout.reconfigure(encoding="utf-8")

BRAZIL = Path("data/bronze/wildchat_brazil.parquet")
SILVER = Path("data/silver/primeira_conversa.parquet")
RELATORIO = Path("relatorios/04_campos_primeira_conversa.txt")
AMOSTRAS = Path("data/amostras")
# Rótulos manuais (BDR-004): substituem a regra de tipo da mensagem vazia.
# Só ids e rótulos, sem texto de conversa; versionado no repositório.
ROTULOS_VAZIA = Path("docs/rotulos/pergunta_vazia_tipo.csv")

FUSO_LOCAL = "America/Sao_Paulo"  # Premissa: fuso do campo horário
SEMENTE = 0.42                    # amostras reproduzíveis
N_AMOSTRA = 100                   # por grupo (marcados / não marcados)

# Padrões de recusa (versão 1). Aplicados à 1ª resposta do assistente,
# em minúsculas. "As an AI language model" sozinho não conta, só junto com uma negação.
# Primeira mensagem do usuário sem pedido (BDR-004). Aplicadas ao texto
# normalizado: minúsculas, sem pontuação, espaços colapsados, sem espaços nas pontas.
# Listas tiradas dos textos mais frequentes (relatorios/05, data/amostras/05_*).
REGEX_SAUDACAO = (
    r"^(oi+e?|ol[aá]+|hi+|hello+|hey+|hola|opa|eae|ea[ií]|e a[ií]|salve"
    r"|bom dia|boa tarde|boa noite)"
    r"( (there|chat|chatgpt|gpt|bot|tudo bem|tudo bom|td bem|como vai|como vai voc[eê]))*$"
)
REGEX_TESTE = r"^test(e|es|ando|ing)?( [0-9]+)?$"

# Tipo da primeira mensagem vazia, pela resposta do assistente (BDR-004, atualização):
#   confirmada    = a resposta diz que a mensagem veio vazia ou incompleta
#   indeterminada = a resposta é só um cumprimento curto (< 150 caracteres)
#   texto_ausente = qualquer outra resposta (ex.: explica um tema): o texto do usuário
#                   provavelmente existia e não está na base
# Testado em Python nas 30 respostas mais frequentes: 15 / 9 / 10 usuários, igual à leitura.
REGEX_RESP_VAZIO = (
    r"(empty|blank|didn'?t come through|did not come through|not have come through"
    r"|not come through|incomplete|haven'?t asked|have not asked|didn'?t get to type"
    r"|not have completed|mensagem (est[aá] )?(vazia|em branco|incompleta)"
    r"|n[aã]o (chegou|veio) (completa|inteira)|n[aã]o recebi (sua|nenhuma) (mensagem|pergunta))"
)
REGEX_CUMPR_INICIO = r"^(hello|hi|hey|ol[aá]|oi)\b"
REGEX_CUMPR_MEIO = r"(how (can|may) i (help|assist)|como posso (te )?ajud|em que posso (te )?ajud)"


def sql_str(rx: str) -> str:
    """Literal SQL entre aspas simples, com as aspas internas escapadas."""
    return "'" + rx.replace("'", "''") + "'"

PADROES_RECUSA = {
    "en_sorry_but_cant": r"i('| a)m sorry,? but i (can('|no)t|am not able|'m not able|am unable|'m unable)",
    "en_i_cant_verbo": r"i (can('|no)t|am unable to|'m unable to|am not able to|'m not able to) "
                       r"(help|assist|provide|fulfill|comply|create|generate|write|do that)",
    "en_ai_model_cant": r"as an ai( language model)?,? i (can('|no)t|am not able|'m not able|am unable|don't have)",
    "pt_desculpe_nao": r"(desculpe|sinto muito|lamento),? (mas )?(eu )?n[ãa]o (posso|consigo|sou capaz)",
    "pt_nao_posso_verbo": r"n[ãa]o (posso|consigo|sou capaz de) "
                          r"(ajudar|fornecer|criar|gerar|atender|cumprir|realizar|escrever|fazer isso)",
    "pt_como_ia_nao": r"como (um |uma )?(modelo de linguagem|assistente|ia|intelig[êe]ncia artificial)"
                      r"[^.]{0,60}n[ãa]o (posso|consigo|tenho|sou capaz)",
    "es_lo_siento_no": r"lo siento,? (pero )?no (puedo|soy capaz)",
}


def main() -> None:
    con = duckdb.connect()
    con.execute("SET TimeZone = 'UTC'")
    for p in (SILVER.parent, RELATORIO.parent, AMOSTRAS):
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
    escrever("  BDR-002 primeira experiência = primeira conversa (pela 1ª resposta do assistente)")
    escrever(f"  fuso do campo horário: {FUSO_LOCAL}")
    escrever("  recusa: padrões v1 na 1ª resposta do assistente (lista no código)")
    escrever("  BDR-004 sem campo 'resposta muito curta'; no lugar: pergunta vazia / só saudação / só teste")
    escrever("  BDR-004 (atualização) pergunta vazia separada em confirmada / indeterminada / texto_ausente")

    # Expressão única que diz qual padrão casou (o primeiro da lista), ou NULL.
    caso_recusa = "CASE " + " ".join(
        f"WHEN regexp_matches(lower(resposta), '{rx.replace(chr(39), chr(39) * 2)}') THEN '{nome}'"
        for nome, rx in PADROES_RECUSA.items()
    ) + " END"

    con.execute(f"""
        CREATE TABLE conv AS
        WITH c AS (
            SELECT
                conversation[1].turn_identifier AS conversa_id,
                conversation_hash, model, turn, language, toxic, redacted,
                hashed_ip, header."user-agent" AS ua,
                conversation[1]."role"          AS role_item1,
                conversation[1]."content"       AS pergunta,
                list_filter(conversation, lambda x: x."role" = 'assistant') AS resp_ia,
                len(list_filter(openai_moderation, lambda m: m.flagged)) > 0 AS moderacao_sinalizada,
                "timestamp" AS t_fim
            FROM read_parquet('{BRAZIL.as_posix()}')
        )
        SELECT *,
            resp_ia[1]."content"                         AS resposta,
            len(resp_ia)                                 AS respostas_ia,
            list_min(list_transform(resp_ia, lambda x: x."timestamp")) AS t_inicio,
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
            count(*) OVER (PARTITION BY conversation_hash) > 1 AS conteudo_repetido
        FROM c
    """)

    con.execute(f"""
        CREATE TABLE primeira AS
        WITH u AS (
            SELECT *, hashed_ip || '|' || so || '|' || navegador AS usuario,
                   trim(regexp_replace(
                       regexp_replace(lower(COALESCE(pergunta, '')), '[[:punct:]¡¿“”‘’…]', '', 'g'),
                       '\\s+', ' ', 'g')) AS pergunta_norm,
                   row_number() OVER (
                       PARTITION BY hashed_ip || '|' || so || '|' || navegador
                       ORDER BY COALESCE(t_inicio, t_fim), t_fim, conversa_id) AS ordem
            FROM conv
        )
        SELECT
            usuario, conversa_id,
            COALESCE(t_inicio, t_fim) AS t_inicio_utc,
            t_fim AS t_fim_utc,
            CASE WHEN model ILIKE 'gpt-4%' THEN 'GPT-4'
                 WHEN model ILIKE 'gpt-3.5%' THEN 'GPT-3.5' ELSE 'Outro' END AS modelo_familia,
            model AS modelo_versao,
            turn AS turnos,
            respostas_ia,
            hour(timezone('{FUSO_LOCAL}', COALESCE(t_inicio, t_fim)))   AS hora_local,
            isodow(timezone('{FUSO_LOCAL}', COALESCE(t_inicio, t_fim))) AS dia_semana_iso,
            language AS idioma,
            CASE language WHEN 'Portuguese' THEN 'Português'
                          WHEN 'English' THEN 'Inglês' ELSE 'Outros' END AS idioma_grupo,
            length(COALESCE(pergunta, '')) AS pergunta_chars,
            CASE WHEN trim(COALESCE(pergunta, '')) = '' THEN 0
                 ELSE len(string_split_regex(trim(pergunta), '\\s+')) END AS pergunta_palavras,
            length(COALESCE(resposta, '')) AS resposta_chars,
            CASE WHEN trim(COALESCE(resposta, '')) = '' THEN 0
                 ELSE len(string_split_regex(trim(resposta), '\\s+')) END AS resposta_palavras,
            (COALESCE(pergunta, '') LIKE '%```%' OR COALESCE(resposta, '') LIKE '%```%') AS tem_codigo,
            {caso_recusa} AS recusa_padrao,
            ({caso_recusa}) IS NOT NULL AS recusa,
            trim(COALESCE(resposta, '')) = '' AS resposta_vazia,
            trim(COALESCE(pergunta, '')) = '' AS pergunta_vazia,
            CASE
                WHEN trim(COALESCE(pergunta, '')) <> '' THEN NULL
                WHEN regexp_matches(lower(COALESCE(resposta, '')), {sql_str(REGEX_RESP_VAZIO)})
                    THEN 'confirmada'
                WHEN regexp_matches(lower(COALESCE(resposta, '')), {sql_str(REGEX_CUMPR_INICIO)})
                 AND regexp_matches(lower(COALESCE(resposta, '')), {sql_str(REGEX_CUMPR_MEIO)})
                 AND length(COALESCE(resposta, '')) < 150
                    THEN 'indeterminada'
                ELSE 'texto_ausente'
            END AS pergunta_vazia_tipo,
            pergunta_norm <> '' AND regexp_matches(pergunta_norm, '{REGEX_SAUDACAO}') AS pergunta_saudacao,
            pergunta_norm <> '' AND regexp_matches(pergunta_norm, '{REGEX_TESTE}') AS pergunta_teste,
            conteudo_repetido, toxic, redacted, moderacao_sinalizada,
            role_item1
        FROM u WHERE ordem = 1
    """)

    # Rótulos manuais da mensagem vazia: a regra fica guardada para auditoria.
    con.execute("ALTER TABLE primeira ADD COLUMN pergunta_vazia_tipo_regra VARCHAR")
    con.execute("UPDATE primeira SET pergunta_vazia_tipo_regra = pergunta_vazia_tipo")
    if ROTULOS_VAZIA.exists():
        con.execute(f"""
            CREATE TABLE rotulos AS
            SELECT CAST(conversa_id AS BIGINT) AS conversa_id, tipo
            FROM read_csv('{ROTULOS_VAZIA.as_posix()}', delim=';', header=true, all_varchar=true)
        """)
        con.execute("""
            UPDATE primeira SET pergunta_vazia_tipo = r.tipo
            FROM rotulos r WHERE primeira.conversa_id = r.conversa_id
        """)
        escrever(f"  rótulos manuais aplicados: {ROTULOS_VAZIA}")
    else:
        escrever(f"  AVISO: {ROTULOS_VAZIA} não encontrado; tipo da mensagem vazia vem só da regra")

    # ------------------------------------------------------------ checagens
    show("[MEDIDO] Consistência da base (todas as conversas)",
         """SELECT count(*) conversas,
                   count(*) FILTER (WHERE role_item1 <> 'user') item1_nao_e_usuario,
                   count(*) FILTER (WHERE turn <> respostas_ia) turn_diferente_de_respostas_ia,
                   count(*) FILTER (WHERE t_inicio IS NULL) sem_horario_de_resposta,
                   count(*) FILTER (WHERE t_inicio > t_fim) inicio_depois_do_fim,
                   count(*) FILTER (WHERE toxic) toxic_true,
                   count(*) FILTER (WHERE redacted) redacted_true
            FROM conv""")
    show("[MEDIDO] Usuários e primeiras conversas",
         """SELECT count(*) usuarios, count(DISTINCT conversa_id) conversas_distintas,
                   min(t_inicio_utc)::VARCHAR primeira_utc, max(t_inicio_utc)::VARCHAR ultima_utc
            FROM primeira""")

    # ------------------------------------------------------------ distribuições
    show("[DERIVADO] Modelo (família e versão)",
         """SELECT modelo_familia, modelo_versao, count(*) usuarios,
                   round(100.0 * count(*) / sum(count(*)) OVER (), 1) pct
            FROM primeira GROUP BY ALL ORDER BY usuarios DESC""")
    show("[MEDIDO] Nº de turnos da primeira conversa",
         """SELECT CASE WHEN turnos >= 5 THEN '5+' ELSE turnos::VARCHAR END faixa,
                   count(*) usuarios, round(100.0 * count(*) / sum(count(*)) OVER (), 1) pct
            FROM primeira GROUP BY faixa ORDER BY min(turnos)""")
    show(f"[DERIVADO] Hora local ({FUSO_LOCAL}) da primeira conversa",
         """SELECT hora_local, count(*) usuarios FROM primeira GROUP BY 1 ORDER BY 1""")
    show("[DERIVADO] Dia da semana (1 = segunda ... 7 = domingo)",
         """SELECT dia_semana_iso, count(*) usuarios FROM primeira GROUP BY 1 ORDER BY 1""")
    show("[DERIVADO] Idioma",
         """SELECT idioma_grupo, count(*) usuarios,
                   round(100.0 * count(*) / sum(count(*)) OVER (), 1) pct
            FROM primeira GROUP BY 1 ORDER BY usuarios DESC""")
    show("[DERIVADO] Tamanho da pergunta e da resposta (caracteres)",
         """SELECT 'pergunta' campo,
                   quantile_cont(pergunta_chars, [0.1, 0.25, 0.5, 0.75, 0.9, 0.99]) p10_p25_p50_p75_p90_p99,
                   min(pergunta_chars) minimo, max(pergunta_chars) maximo FROM primeira
            UNION ALL
            SELECT 'resposta',
                   quantile_cont(resposta_chars, [0.1, 0.25, 0.5, 0.75, 0.9, 0.99]),
                   min(resposta_chars), max(resposta_chars) FROM primeira""")
    show("[DERIVADO] Primeira mensagem sem pedido (BDR-004)",
         """SELECT count(*) usuarios,
                   count(*) FILTER (WHERE pergunta_vazia) vazia,
                   count(*) FILTER (WHERE pergunta_saudacao) so_saudacao,
                   count(*) FILTER (WHERE pergunta_teste) so_teste,
                   count(*) FILTER (WHERE pergunta_vazia OR pergunta_saudacao OR pergunta_teste) algum_dos_tres,
                   count(*) FILTER (WHERE (pergunta_vazia::INT + pergunta_saudacao::INT
                                           + pergunta_teste::INT) > 1) em_mais_de_um
            FROM primeira""")
    show("[DERIVADO] Primeira mensagem vazia, por tipo (rótulo manual; regra quando não houver)",
         """SELECT pergunta_vazia_tipo, count(*) usuarios FROM primeira
            WHERE pergunta_vazia GROUP BY 1 ORDER BY usuarios DESC""")
    show("[MEDIDO] Regra x rótulo manual (mensagens vazias)",
         """SELECT pergunta_vazia_tipo_regra AS regra, pergunta_vazia_tipo AS final, count(*) usuarios
            FROM primeira WHERE pergunta_vazia GROUP BY ALL ORDER BY regra, final""")
    if ROTULOS_VAZIA.exists():
        show("[MEDIDO] Cobertura dos rótulos (mensagens vazias sem rótulo e rótulos sem conversa)",
             """SELECT
                    (SELECT count(*) FROM primeira p WHERE p.pergunta_vazia
                       AND p.conversa_id NOT IN (SELECT conversa_id FROM rotulos)) vazias_sem_rotulo,
                    (SELECT count(*) FROM rotulos r WHERE r.conversa_id NOT IN
                       (SELECT conversa_id FROM primeira WHERE pergunta_vazia)) rotulos_sem_conversa""")
    show("[MEDIDO] Respostas curtas: quantos usuários abaixo de cada tamanho (só descritivo, BDR-004)",
         """SELECT count(*) FILTER (WHERE resposta_vazia) vazia,
                   count(*) FILTER (WHERE resposta_chars < 20) menos_de_20,
                   count(*) FILTER (WHERE resposta_chars < 50) menos_de_50,
                   count(*) FILTER (WHERE resposta_chars < 100) menos_de_100,
                   count(*) usuarios
            FROM primeira""")
    show("[DERIVADO] Código, recusa, conteúdo repetido, moderação",
         """SELECT count(*) usuarios,
                   count(*) FILTER (WHERE tem_codigo) tem_codigo,
                   count(*) FILTER (WHERE recusa) recusa,
                   count(*) FILTER (WHERE conteudo_repetido) conteudo_repetido,
                   count(*) FILTER (WHERE moderacao_sinalizada) moderacao_sinalizada,
                   count(*) FILTER (WHERE toxic) toxic,
                   count(*) FILTER (WHERE redacted) redacted
            FROM primeira""")
    show("[DERIVADO] Recusa por padrão (primeiro padrão que casou)",
         """SELECT recusa_padrao, count(*) usuarios FROM primeira
            WHERE recusa GROUP BY 1 ORDER BY usuarios DESC""")

    # ------------------------------------------------------------ silver (sem texto)
    con.execute(f"""
        COPY (SELECT * EXCLUDE (role_item1) FROM primeira ORDER BY t_inicio_utc)
        TO '{SILVER.as_posix()}' (FORMAT parquet, COMPRESSION zstd)
    """)

    # ------------------------------------------------------------ amostras
    con.execute(f"SELECT setseed({SEMENTE})").fetchall()
    con.execute("""
        CREATE TABLE textos AS
        SELECT p.conversa_id, p.recusa, p.recusa_padrao, p.tem_codigo,
               left(regexp_replace(c.pergunta, '\\s+', ' ', 'g'), 400) AS pergunta_trecho,
               left(regexp_replace(c.resposta, '\\s+', ' ', 'g'), 800) AS resposta_trecho
        FROM primeira p JOIN conv c USING (conversa_id)
    """)

    def amostra(nome: str, filtro: str, ordem_extra: str = "") -> int:
        caminho = AMOSTRAS / f"{nome}.csv"
        con.execute(f"""
            COPY (
                SELECT conversa_id, recusa_padrao, pergunta_trecho, resposta_trecho,
                       NULL::VARCHAR AS avaliacao_sim_nao, NULL::VARCHAR AS comentario
                FROM (SELECT *, random() r FROM textos WHERE {filtro})
                ORDER BY r LIMIT {N_AMOSTRA}
            ) TO '{caminho.as_posix()}' (HEADER, DELIMITER ';')
        """)
        return con.sql(f"SELECT count(*) FROM textos WHERE {filtro}").fetchall()[0][0]

    escrever("\n== Amostras para conferência manual (data/amostras/, até "
             f"{N_AMOSTRA} linhas cada; preencha avaliacao_sim_nao)")
    for nome, filtro, pergunta in [
        ("recusa_marcadas", "recusa", "A resposta é uma recusa?"),
        ("recusa_nao_marcadas", "NOT recusa", "A resposta é uma recusa?"),
        ("codigo_marcadas", "tem_codigo", "Há código na pergunta ou na resposta?"),
        ("codigo_nao_marcadas", "NOT tem_codigo", "Há código na pergunta ou na resposta?"),
    ]:
        total = amostra(nome, filtro)
        escrever(f"  {nome}.csv: população {total}; pergunta: {pergunta}")

    out.close()
    print(f"\nRelatório: {RELATORIO}\nSilver: {SILVER}")


if __name__ == "__main__":
    main()
