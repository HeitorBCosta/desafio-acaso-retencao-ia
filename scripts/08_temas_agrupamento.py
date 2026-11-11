"""
Tenta descobrir o tema da primeira conversa agrupando os textos, sem modelo de linguagem.

O texto de cada usuário é a junção das mensagens dele na primeira conversa, porque
quem começa com "oi" só faz o pedido depois. Os textos viram vetores TF-IDF (palavras e
pares de palavras, sem acento, sem números e sem palavras vazias em português e
inglês), são reduzidos a 100 dimensões e agrupados com k-means, seguindo o exemplo de
agrupamento de textos da documentação do scikit-learn.

O número de grupos foi escolhido sem olhar o retorno, para os grupos não se ajustarem
ao resultado. Cada número de grupos roda com 5 sementes, e a regra combinada antes era
ficar com o maior número que desse grupos estáveis (concordância de pelo menos 0,80
entre as rodadas) e com pelo menos 30 usuários cada.

Não funcionou. Na primeira tentativa, só o menor número de grupos (6) ficou estável, e
os grupos se formavam por idioma e por cumprimento, não por assunto. Na segunda, sem as
palavras de cumprimento e as que falam do próprio assistente, e exigindo que nenhum
grupo passasse de 40% dos usuários, nenhum número de grupos passou. O tema passou a
ser classificado por dicionário, no script 08b.

Como rodar:
    python scripts/08_temas_agrupamento.py           (compara os números de grupos)
    python scripts/08_temas_agrupamento.py --k 12    (grava os grupos de um número escolhido)

Lê:   data/gold/base_analise.parquet, data/bronze/wildchat_brazil.parquet
Gera: relatorios/08_temas_escolha_k.txt e, com --k, os grupos, uma amostra para leitura
      e um mapa grupo-tema para preencher
"""
import argparse
import csv
import itertools
import re
import sys
import unicodedata
from pathlib import Path

import duckdb
import numpy as np
from sklearn.cluster import KMeans
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import Normalizer

sys.stdout.reconfigure(encoding="utf-8")

GOLD = Path("data/gold/base_analise.parquet")
BRAZIL = Path("data/bronze/wildchat_brazil.parquet")
SILVER_TEMA = Path("data/silver/tema_grupo.parquet")
AMOSTRAS = Path("data/amostras")
ROTULOS = Path("docs/rotulos")
RELATORIOS = Path("relatorios")

ELEGIVEL = "elegivel_30min"   # mesma base do script 07 (BDR-003)
MAX_CHARS = 2000              # Premissa: só o começo do texto: código ou texto colado não domina
K_LISTA = [6, 8, 10, 12, 15, 20]
SEMENTES = [0, 1, 2, 3, 4]
ESTAB_MIN = 0.80              # premissa
MAIOR_GRUPO_MAX = 0.40        # Premissa: acima disso o maior grupo é um "resto", não um tema
GRUPO_MIN = 30                # mesmo mínimo do script 07
N_COMPONENTES = 100
N_TERMOS = 12
N_AMOSTRA_GRUPO = 15
CHARS_AMOSTRA = 400

# Palavras vazias do português (lista própria, sem acento, porque o texto é
# normalizado sem acento antes do TF-IDF). Inglês: lista do scikit-learn.
STOP_PT = """
a ao aos aquela aquelas aquele aqueles aquilo as ate com como da das de dela delas dele
deles depois do dos e ela elas ele eles em entre era eram essa essas esse esses esta estas
este estes eu foi foram ha isso isto ja la lhe lhes mais mas me mesmo meu meus minha minhas
muito na nas nem no nos nossa nossas nosso nossos num numa o os ou para pela pelas pelo pelos
por qual quando que quem se sem ser seu seus so sua suas tambem te tem ter teu teus tu tua
tuas um uma umas uns voce voces vos sao estou esta estao seria pode poderia fazer faz
sobre ate onde porque pra pro tudo todo toda todos todas cada outro outra outros outras
aqui ai entao assim ainda bem tipo vai vou ser sim nao
""".split()


# v2 (11/11): na v1 os grupos se formaram por cumprimento e por perguntas sobre o
# próprio assistente ("oi", "ola", "hi", "versao", "gpt"), não por assunto. Essas
# palavras saem do vocabulário. A lista é fixa e fica registrada aqui.
STOP_DOMINIO = """
oi oie ola hi hello hey hola opa eae salve bom boa dia tarde noite tudo td
obrigado obrigada valeu thanks thank please favor
chat chatgpt gpt openai bot ia ai assistente assistant versao version vc
""".split()


def sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def preparar(s: str) -> str:
    s = s[:MAX_CHARS].lower()
    s = re.sub(r"https?://\S+|www\.\S+", " ", s)
    return sem_acento(s)


def carregar() -> tuple[list[str], list[str], list[str]]:
    con = duckdb.connect()
    con.execute("SET TimeZone = 'UTC'")
    linhas = con.execute(f"""
        WITH g AS (
            SELECT usuario, conversa_id FROM read_parquet('{GOLD.as_posix()}')
            WHERE {ELEGIVEL}
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
    # Checagens: cada elegível tem exatamente uma conversa no bronze.
    n_eleg, sem_par = con.execute(f"""
        WITH g AS (SELECT conversa_id FROM read_parquet('{GOLD.as_posix()}') WHERE {ELEGIVEL}),
             b AS (SELECT conversation[1].turn_identifier AS conversa_id
                   FROM read_parquet('{BRAZIL.as_posix()}'))
        SELECT (SELECT count(*) FROM g),
               (SELECT count(*) FROM g ANTI JOIN b USING (conversa_id))
    """).fetchall()[0]
    if sem_par:
        raise SystemExit(f"ERRO: {sem_par} usuários elegíveis sem conversa no bronze")
    if len(linhas) != n_eleg:
        raise SystemExit(f"ERRO: {len(linhas)} linhas para {n_eleg} elegíveis (conversa_id repetido no bronze?)")
    print(f"Checagem: {n_eleg} elegíveis, todos com 1 conversa no bronze")
    return [l[0] for l in linhas], [l[1] for l in linhas], [l[2] for l in linhas]


def vetorizar(textos: list[str]):
    vet = TfidfVectorizer(
        preprocessor=preparar,
        token_pattern=r"(?u)\b[^\W\d_]{2,}\b",   # só letras, 2+ caracteres
        stop_words=sorted(set(STOP_PT) | set(ENGLISH_STOP_WORDS) | set(STOP_DOMINIO)),
        ngram_range=(1, 2), min_df=5, max_df=0.4, sublinear_tf=True,
    )
    X = vet.fit_transform(textos)
    com_termos = np.asarray(X.getnnz(axis=1) > 0)
    lsa = make_pipeline(TruncatedSVD(n_components=min(N_COMPONENTES, X.shape[1] - 1), random_state=42), Normalizer(copy=False))
    Z = lsa.fit_transform(X[com_termos])
    return vet, lsa, X, com_termos, Z


def termos_por_grupo(km: KMeans, lsa, vet) -> list[list[str]]:
    centros = lsa[0].inverse_transform(km.cluster_centers_)
    nomes = vet.get_feature_names_out()
    return [[nomes[i] for i in c.argsort()[::-1][:N_TERMOS]] for c in centros]


def passo1(vet, lsa, Z, n_sem_termos: int, n_total: int) -> None:
    rel = RELATORIOS / "08_temas_escolha_k.txt"
    out = rel.open("w", encoding="utf-8")

    def escrever(t: str = "") -> None:
        print(t)
        out.write(t + "\n")

    escrever(f"Usuários elegíveis: {n_total}")
    escrever(f"  sem nenhum termo depois da limpeza (vazios, só números, só palavras vazias): {n_sem_termos}")
    escrever(f"  agrupados: {Z.shape[0]}")
    escrever(f"Vocabulário TF-IDF: {len(vet.vocabulary_)} termos")
    escrever(f"Variância explicada pelas {N_COMPONENTES} dimensões: {lsa[0].explained_variance_ratio_.sum():.1%}")
    escrever()
    escrever(f"{'k':>3} {'estabilidade (ARI médio)':>25} {'ARI mín':>8} {'silhueta':>9} {'menor grupo':>12} {'maior grupo':>12}")

    resultados = {}
    resultados_maior = {}
    for k in K_LISTA:
        rotulos = [KMeans(n_clusters=k, n_init=10, random_state=s).fit_predict(Z) for s in SEMENTES]
        aris = [adjusted_rand_score(a, b) for a, b in itertools.combinations(rotulos, 2)]
        tamanhos = np.bincount(rotulos[0], minlength=k)
        sil = silhouette_score(Z, rotulos[0], metric="cosine")
        resultados[k] = (float(np.mean(aris)), int(tamanhos.min()))
        resultados_maior[k] = int(tamanhos.max())
        escrever(f"{k:>3} {np.mean(aris):>25.3f} {min(aris):>8.3f} {sil:>9.3f} {tamanhos.min():>12} {tamanhos.max():>12}")

    passam = [k for k, (ari, menor) in resultados.items() if ari >= ESTAB_MIN and menor >= GRUPO_MIN]
    escolhido = max(passam) if passam else max(resultados, key=lambda k: resultados[k][0])
    escrever()
    escrever(f"Regra [PREMISSA]: maior k com estabilidade >= {ESTAB_MIN} e todos os grupos >= {GRUPO_MIN}.")
    escrever(f"  passam: {passam if passam else 'nenhum (usado o k mais estável)'}")
    escrever(f"  k sugerido pela regra: {escolhido}")
    maior = resultados_maior[escolhido] / Z.shape[0]
    escrever(f"  maior grupo no k sugerido: {maior:.0%} dos agrupados "
             f"({'OK' if maior <= MAIOR_GRUPO_MAX else 'ACIMA do limite: agrupamento não serve para tema'})")

    for k in K_LISTA:
        km = KMeans(n_clusters=k, n_init=10, random_state=SEMENTES[0]).fit(Z)
        tamanhos = np.bincount(km.labels_, minlength=k)
        escrever()
        escrever(f"=== k = {k}: termos mais fortes de cada grupo (semente {SEMENTES[0]}) ===")
        for g, termos in enumerate(termos_por_grupo(km, lsa, vet)):
            escrever(f"  grupo {g:>2} | {tamanhos[g]:>4} usuários | {', '.join(termos)}")
    out.close()
    print(f"\nRelatório: {rel}")


def passo2(k: int, usuarios, conversas, textos, vet, lsa, com_termos, Z) -> None:
    km = KMeans(n_clusters=k, n_init=10, random_state=SEMENTES[0]).fit(Z)
    grupo = np.full(len(usuarios), -1)
    grupo[com_termos] = km.labels_     # -1 = sem termos
    termos = termos_por_grupo(km, lsa, vet)
    tamanhos = np.bincount(km.labels_, minlength=k)

    SILVER_TEMA.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("CREATE TABLE t (usuario VARCHAR, grupo INTEGER)")
    con.executemany("INSERT INTO t VALUES (?, ?)", list(zip(usuarios, grupo.tolist())))
    con.execute(f"COPY (SELECT *, {k} AS k FROM t ORDER BY usuario) TO '{SILVER_TEMA.as_posix()}' (FORMAT parquet)")

    rng = np.random.default_rng(42)
    AMOSTRAS.mkdir(parents=True, exist_ok=True)
    amostra = AMOSTRAS / f"08_temas_k{k}.csv"
    with amostra.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["grupo", "conversa_id", "texto_usuario_inicio"])
        for g in list(range(k)) + [-1]:
            idx = np.flatnonzero(grupo == g)
            for i in sorted(rng.choice(idx, size=min(N_AMOSTRA_GRUPO, len(idx)), replace=False)):
                w.writerow([g, conversas[i], textos[i][:CHARS_AMOSTRA].replace("\n", " ⏎ ")])

    ROTULOS.mkdir(parents=True, exist_ok=True)
    mapa = ROTULOS / f"tema_mapa_k{k}.csv"
    if mapa.exists():
        print(f"{mapa} já existe; não sobrescrevi")
    else:
        with mapa.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["grupo", "usuarios", "termos", "tema", "motivo", "conferido_por"])
            for g in range(k):
                w.writerow([g, int(tamanhos[g]), ", ".join(termos[g]), "", "", ""])
            w.writerow([-1, int((grupo == -1).sum()), "(sem termos)", "", "", ""])

    rel = RELATORIOS / f"08_temas_k{k}.txt"
    with rel.open("w", encoding="utf-8") as out:
        linhas = [f"k = {k}, semente {SEMENTES[0]}; {len(usuarios)} usuários elegíveis"]
        linhas += [f"  grupo {g:>2} | {tamanhos[g]:>4} usuários | {', '.join(termos[g])}" for g in range(k)]
        linhas += [f"  grupo -1 | {(grupo == -1).sum():>4} usuários | sem termos"]
        for l in linhas:
            print(l)
            out.write(l + "\n")
    print(f"\nGravado: {SILVER_TEMA}, {amostra}, {mapa}, {rel}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, help="grava os grupos para este k (passo 2)")
    args = ap.parse_args()

    RELATORIOS.mkdir(parents=True, exist_ok=True)
    usuarios, conversas, textos = carregar()
    vet, lsa, X, com_termos, Z = vetorizar(textos)
    if args.k is None:
        passo1(vet, lsa, Z, int((~com_termos).sum()), len(usuarios))
    else:
        passo2(args.k, usuarios, conversas, textos, vet, lsa, com_termos, Z)


if __name__ == "__main__":
    main()
