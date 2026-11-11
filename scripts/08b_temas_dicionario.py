"""
Classifica o tema da primeira conversa com listas de palavras-chave.

Foi o plano B depois que o agrupamento do script 08 não separou assuntos. Os termos
que o agrupamento mostrou (código, exercícios, imagem e vídeo, tradução, redação,
perguntas sobre o próprio assistente) serviram de ponto de partida para as listas.

O texto é o mesmo do script 08, cortado nos primeiros 2.000 caracteres, em minúsculas
e sem acento. Cada tema é uma lista de expressões regulares, e o usuário recebe o
primeiro tema da ordem que casar, do mais específico ao mais genérico. O relatório
mostra quantos casaram com mais de um tema, para dar a medida do peso da ordem. Quem só
mandou cumprimento, teste ou nada fica como "sem pedido", e quem não casou com nenhuma
lista fica como "outros". O retorno não é usado em nenhum momento.

A primeira versão acertou 54 de 98 numa amostra lida à mão (55%). As listas foram
corrigidas a partir desses erros e testadas numa segunda amostra, só com usuários
novos, onde acertaram 65 de 97 (67%). Como isso ficou abaixo dos 70% combinados antes,
o tema entra só como descrição, fora do modelo de efeitos.

Como rodar:
    python scripts/08b_temas_dicionario.py

Lê:   data/gold/base_analise.parquet, data/bronze/wildchat_brazil.parquet
Gera: data/silver/tema.parquet (sem texto), relatorios/08b_temas_dicionario.txt,
      amostras com texto em data/amostras (fora do Git)
      e o gabarito para preencher em docs/rotulos/tema_validacao_v2.csv
"""
import csv
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

import duckdb
import numpy as np

sys.stdout.reconfigure(encoding="utf-8")

GOLD = Path("data/gold/base_analise.parquet")
BRAZIL = Path("data/bronze/wildchat_brazil.parquet")
SILVER_TEMA = Path("data/silver/tema.parquet")
AMOSTRAS = Path("data/amostras")
ROTULOS = Path("docs/rotulos")
RELATORIO = Path("relatorios/08b_temas_dicionario.txt")

ELEGIVEL = "elegivel_30min"
MAX_CHARS = 2000
VERSAO = "v2"         # v1 (11/11): 54 de 98 corretos na 1ª amostra (55,1%; IC 45,2-64,6)
N_VALIDACAO = 100
SEMENTE = 2026        # v1 usou 42; a v2 é testada em usuários NOVOS (fora da 1ª amostra)
VALIDACAO_V1 = Path("docs/rotulos/tema_validacao.csv")
CHARS_AMOSTRA = 400
REPETIDO_MIN = 5      # texto igual em 5+ usuários entra na lista de repetidos
CHARS_REPETIDO = 200  # compara os primeiros 200 caracteres normalizados

# Ordem = prioridade. Texto já minúsculo e sem acento.
TEMAS: dict[str, list[str]] = {
    "programação e planilhas": [
        r"```", r"\bimport \w", r"\bfrom [\w\.]+ import\b", r"\bdef \w+\s*\(", r"\bfunction\s*\w*\s*\(",
        r"\b(const|let|var) \w+\s*=", r"console\.log|system\.out|println|printf\s*\(|#include",
        r"</?(div|html|body|span|script)\b", r"\bselect\b[^.]{1,80}\bfrom\b",
        r"(?<!\w)(c\+\+|c#)(?!\w)",   # v2: o \b depois de "+" não casava
        r"\b(python|javascript|typescript|java|html|css|php|sql|mysql|postgres|react|node\.?js|"
        r"django|flask|laravel|kotlin|golang|vba|excel|planilha|planilhas|google sheets|power bi)\b",
        r"\b(codigo|programacao|programar|algoritmo|code|coding|algorithm|debug|bug)\b",
        r"\b(unity|wget|curl|linux|bash|powershell|terminal|biblioteca|bibliotecas|landing page|"
        r"engenharia reversa|apps script)\b",   # v2
    ],
    "perguntas sobre o assistente": [
        r"\b(sua|your) versao\b|\bversao (do|de) (chat)?gpt\b|\bwhat version\b|\bqual versao\b",
        r"\bgpt ?-?(3|3\.5|4)\b",
        r"\bquem (e voce|e vc|te criou|criou voce|criou vc)\b|\bwho (are you|created you|made you)\b",
        r"\b(acesso a|access to the|acessar a) internet\b",
        r"\b(fala|falar|sabe falar|entende|speak|speaks) (em )?(portugues|portuguese)\b",
        r"\bapi key\b|\bchave (de |da )?api\b",
        r"\bmodelo de linguagem\b|\blanguage model\b|\bqual modelo\b|\bwhat model\b",   # v2
        r"\b(voce|vc) (responde|fala|entende)\b",                                           # v2
    ],
    "instruções de persona": [
        r"\ba partir de agora\b|\bfrom now on\b|\byou are going to (act|pretend)\b",
        r"\b(act as|aja como|atue como|haja como|pretend to be|pretend you)\b|\bfinja (que|ser)\b",
        r"\b(roleplay|role-play|role play|jailbreak|developer mode|modo desenvolvedor)\b",
    ],
    # v2: só pedido de CRIAR imagem ou vídeo; "foto", "vídeo", "tiktok" como assunto não bastam
    "imagem e vídeo": [
        r"\b(midjourney|dall-?e|stable diffusion)\b",
        r"\b(crie|cria|criar|criacao|gere|gera|gerar|geracao|faca|faz|fazer|desenhe|desenha|desenhar|create|generate|make|draw|design)"
        r"\b(\W+\w+){0,5}?\W+(imagem|imagens|image|images|foto|fotos|photo|photos|picture|pictures|desenho|"
        r"logo|logotipo|thumbnail|ilustracao|illustration|wallpaper)\b",
        r"\b(roteiro|script|texto|text)\b(\W+\w+){0,6}?\W+(video|videos|youtube|tiktok|reels|shorts)\b",
        r"\b(video|videos|youtube|tiktok|reels|shorts)\b(\W+\w+){0,6}?\W+(roteiro|script)\b",
    ],
    "tradução e idiomas": [
        r"\b(traduz\w*|traducao|tradutor|translate|translation|translator)\b",
        r"\bpara o (ingles|espanhol|frances|alemao|italiano)\b|\bto (english|portuguese|spanish)\b",
        r"\bingles nativo\b",
    ],
    # v2: sem "prova", "escola", "professor", "aluno" (apareciam como assunto, não como tarefa)
    "escola e exercícios": [
        r"\b(assinale|alternativa correta|alternativa incorreta|alternativas|gabarito|questao|questoes|"
        r"exercicio|exercicios|justifique)\b",
        r"\b(resolva|calcule|equacao|derivada|calculo integral|matematica|fisica|quimica|biologia)\b",
        r"\b(enem|vestibular|concurso|tcc|monografia|faculdade|universidade|aula|homework|exam|quiz)\b",
        r"\b(estudar|plano de estudo|plano de estudos|\d+ pontos?)\b",
    ],
    "negócios e marketing": [
        r"\b(empresa|negocio|negocios|marketing|vendas|vender|cliente|clientes|instagram|linkedin|anuncio|"
        r"anuncios|publico alvo|startup|business|sales|curriculo|loja|e-?commerce|orcamento)\b",
        r"\b(ads|seo|trafego pago|copy|copywriting|pitch|funil de vendas|leads)\b",   # v2
    ],
    "histórias e ficção": [
        r"\b(story|stories|chapter|capitulo|personagem|personagens|character|characters|fanfic|conto|"
        r"poema|poesia|poem|lyrics|song|letra de musica|enredo|plot)\b",
        r"\bhistoria\b(\W+\w+){0,3}?\W+sobre\b|\b(crie|escreva|conte) uma historia\b",
        r"\b(primeira pessoa|first person)\b",   # v2
    ],
    "redação e textos": [
        r"\b(escreva|escrever|redacao|redija|texto|resuma|resumo|resumir|reescreva|reformule|parafras\w*|"
        r"corrija|revise|revisar|artigo|carta|e-?mail|legenda|essay|write|rewrite|summarize|summary|"
        r"paragrafo|paragraph|dissertacao|apresentacao|slides|resenha|recrie)\b",
    ],
    "perguntas e explicações": [
        r"\b(explique|explica|explain)\b|\bo que (e|sao|significa)\b|\bwhat (is|are)\b",
        r"\bdiferenca\b|\bdifference\b|\bcomo funciona\b|\bhow (does|do|to|can)\b",
        r"\b(por que|porque|why|quem foi|quem e|who is|who was|quando|quanto|quantos|quais|qual|como)\b",
        r"\b(descreva|describe|fale sobre|me fale|tell me|liste|monte|can i|did|does|do you|is there|are there)\b",  # v2
        r"\?",   # v2: qualquer pergunta que não caiu num tema acima
    ],
}

# "Sem pedido": todas as palavras estão nesta lista (cumprimento, teste, assistente, vazias).
SEM_PEDIDO = set("""
oi oie oii ola hi hello hey hola opa eae eai salve bom boa dia tarde noite tudo td bem bom bao
como vai voce vc esta ta tudo certo blz beleza
obrigado obrigada valeu thanks thank you please favor ok okay sim nao yes no
chat chatgpt gpt openai bot ia ai assistente assistant there
teste testes testando test testing
a o e de da do um uma the is are i me eu
""".split())


def sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def normalizar(s: str) -> str:
    s = sem_acento(s[:MAX_CHARS].lower())
    return re.sub(r"https?://\S+|www\.\S+", " ", s)


COMPILADOS = {tema: [re.compile(rx) for rx in lista] for tema, lista in TEMAS.items()}


def classificar(texto: str) -> tuple[str, list[str]]:
    t = normalizar(texto)
    palavras = re.findall(r"[^\W\d_]+", t)
    if all(p in SEM_PEDIDO for p in palavras):   # inclui texto vazio
        return "sem pedido", []
    casados = [tema for tema, rxs in COMPILADOS.items() if any(r.search(t) for r in rxs)]
    return (casados[0] if casados else "outros"), casados


def carregar() -> tuple[list[str], list[str], list[str]]:
    con = duckdb.connect()
    con.execute("SET TimeZone = 'UTC'")
    linhas = con.execute(f"""
        WITH g AS (
            SELECT usuario, conversa_id FROM read_parquet('{GOLD.as_posix()}') WHERE {ELEGIVEL}
        ),
        c AS (
            SELECT conversation[1].turn_identifier AS conversa_id,
                   array_to_string(list_transform(
                       list_filter(conversation, lambda x: x."role" = 'user'),
                       lambda x: COALESCE(x."content", '')), chr(10)) AS texto_usuario
            FROM read_parquet('{BRAZIL.as_posix()}')
        )
        SELECT g.usuario, g.conversa_id::VARCHAR, COALESCE(c.texto_usuario, '')
        FROM g LEFT JOIN c USING (conversa_id)
        ORDER BY g.usuario
    """).fetchall()
    n_eleg = con.execute(
        f"SELECT count(*) FROM read_parquet('{GOLD.as_posix()}') WHERE {ELEGIVEL}").fetchall()[0][0]
    if len(linhas) != n_eleg:
        raise SystemExit(f"ERRO: {len(linhas)} linhas para {n_eleg} elegíveis")
    print(f"Checagem: {n_eleg} elegíveis")
    return [l[0] for l in linhas], [l[1] for l in linhas], [l[2] for l in linhas]


def main() -> None:
    usuarios, conversas, textos = carregar()
    resultado = [classificar(t) for t in textos]
    temas = [r[0] for r in resultado]
    casados = [r[1] for r in resultado]
    n = len(usuarios)

    RELATORIO.parent.mkdir(parents=True, exist_ok=True)
    out = RELATORIO.open("w", encoding="utf-8")

    def escrever(t: str = "") -> None:
        print(t)
        out.write(t + "\n")

    ordem = ["sem pedido"] + list(TEMAS) + ["outros"]
    cont = Counter(temas)
    escrever(f"Usuários elegíveis: {n}")
    escrever()
    escrever(f"{'tema (atribuído)':<32} {'usuários':>9} {'%':>7} {'casaram com este tema (qualquer posição)':>42}")
    qualquer = Counter(t for lista in casados for t in lista)
    for t in ordem:
        q = qualquer.get(t, 0) if t in TEMAS else cont.get(t, 0)
        escrever(f"{t:<32} {cont.get(t, 0):>9} {cont.get(t, 0) / n:>7.1%} {q:>42}")

    multi = sum(1 for c in casados if len(c) >= 2)
    com_pedido = sum(1 for t in temas if t != "sem pedido")
    escrever()
    escrever(f"Casaram com 2+ temas (a ordem decidiu): {multi} de {com_pedido} com pedido ({multi / com_pedido:.1%})")
    pares = Counter((c[0], c[1]) for c in casados if len(c) >= 2)
    escrever("  pares mais comuns (atribuído <- segundo que também casou):")
    for (a, b), q in pares.most_common(10):
        escrever(f"    {a} <- {b}: {q}")

    # Textos repetidos entre usuários diferentes (qualidade dos dados).
    chave = [re.sub(r"\s+", " ", normalizar(t))[:CHARS_REPETIDO].strip() for t in textos]
    rep = Counter(k for k, t in zip(chave, temas) if t != "sem pedido")
    grupos_rep = [(k, q) for k, q in rep.most_common() if q >= REPETIDO_MIN]
    usuarios_rep = sum(q for _, q in grupos_rep)
    escrever()
    escrever(f"Textos iguais (primeiros {CHARS_REPETIDO} caracteres) em {REPETIDO_MIN}+ usuários: "
             f"{len(grupos_rep)} textos, {usuarios_rep} usuários")
    for i, (k, q) in enumerate(grupos_rep[:15]):
        tema_k = temas[chave.index(k)]
        escrever(f"  texto repetido {i + 1:>2}: {q:>3} usuários | tema {tema_k}")

    # Gravações
    SILVER_TEMA.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("CREATE TABLE t (usuario VARCHAR, tema VARCHAR, temas_casados VARCHAR)")
    con.executemany("INSERT INTO t VALUES (?, ?, ?)",
                    [(u, t, " | ".join(c)) for u, t, c in zip(usuarios, temas, casados)])
    con.execute(f"COPY (SELECT * FROM t ORDER BY usuario) TO '{SILVER_TEMA.as_posix()}' (FORMAT parquet)")

    AMOSTRAS.mkdir(parents=True, exist_ok=True)
    with (AMOSTRAS / "08b_textos_repetidos.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["n_usuarios", "tema", "texto_inicio"])
        for k, q in grupos_rep:
            w.writerow([q, temas[chave.index(k)], k])

    # A 1ª amostra serviu para corrigir as listas; testar nela de novo daria acerto inflado.
    ja_lidos = set()
    if VALIDACAO_V1.exists():
        with VALIDACAO_V1.open(encoding="utf-8-sig") as f:
            ja_lidos = {r["conversa_id"] for r in csv.DictReader(f, delimiter=";")}
    candidatos = [i for i in range(n) if conversas[i] not in ja_lidos]
    escrever(f"\nValidação {VERSAO}: sorteio entre {len(candidatos)} usuários fora da 1ª amostra ({len(ja_lidos)} excluídos)")
    rng = np.random.default_rng(SEMENTE)
    sorteio = sorted(rng.choice(candidatos, size=min(N_VALIDACAO, len(candidatos)), replace=False))
    with (AMOSTRAS / f"08b_validacao_{VERSAO}.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["conversa_id", "tema_regra", "temas_casados", "texto_usuario_inicio"])
        for i in sorteio:
            w.writerow([conversas[i], temas[i], " | ".join(casados[i]),
                        textos[i][:CHARS_AMOSTRA].replace("\n", " ⏎ ")])

    ROTULOS.mkdir(parents=True, exist_ok=True)
    gabarito = ROTULOS / f"tema_validacao_{VERSAO}.csv"
    if gabarito.exists():
        escrever(f"\n{gabarito} já existe; não sobrescrevi")
    else:
        with gabarito.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["conversa_id", "tema_regra", "tema_correto", "regra_cobre_algum_pedido", "motivo", "conferido_por"])
            for i in sorteio:
                w.writerow([conversas[i], temas[i], "", "", "", ""])

    out.close()
    print(f"\nGravado: {SILVER_TEMA}, {RELATORIO}, {AMOSTRAS / f'08b_validacao_{VERSAO}.csv'}, "
          f"{AMOSTRAS / '08b_textos_repetidos.csv'}, {gabarito}")


if __name__ == "__main__":
    main()
