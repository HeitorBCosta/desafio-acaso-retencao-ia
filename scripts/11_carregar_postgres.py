"""
Carrega a base analítica do dashboard no PostgreSQL a partir dos resultados da análise.

Primeiro aplica as migrações de db/migracoes que ainda não rodaram. Depois, numa
transação só, apaga e regrava as tabelas do schema analytics: uma linha por usuário com
os fatores da primeira conversa e o desfecho, o volume de conversas por dia e os
efeitos já calculados pelos scripts 07, 07b e 09. Antes de confirmar, compara os totais
gravados com os da origem (usuários, elegíveis, retornos, conversas e efeitos). Se algum
não bater, a transação é desfeita inteira. Cada carga fica registrada em
analytics.carga_execucao.

A recarga é completa a cada execução. A base é pequena, e assim rodar de novo sempre
dá o mesmo resultado. Nenhuma tabela recebe texto de conversa, IP ou user-agent; o
usuário é gravado como o sha256 de "IP anonimizado|sistema|navegador".

Como rodar:
    $env:DATABASE_URL = "postgresql://acaso:acaso@localhost:5432/acaso"
    python scripts/11_carregar_postgres.py

Lê:   data/gold/, data/silver/tema.parquet, data/bronze/wildchat_brazil.parquet
Grava: o schema analytics do banco indicado em DATABASE_URL
"""
import hashlib
import importlib.util
import json
import math
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd
import psycopg

sys.stdout.reconfigure(encoding="utf-8")

_spec = importlib.util.spec_from_file_location("efeitos07", Path(__file__).with_name("07_efeitos.py"))
e07 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(e07)

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://acaso:acaso@localhost:5432/acaso")
MIGRACOES = Path("db/migracoes")
BRAZIL = Path("data/bronze/wildchat_brazil.parquet")
TEMA = Path("data/silver/tema.parquet")
EFEITOS_07 = Path("data/gold/efeitos.csv")
EFEITOS_07B = Path("data/gold/efeitos_recusa_motivo.csv")
EFEITO_09 = Path("data/gold/efeito_gpt4_iptw.csv")
MIN_USUARIOS, MIN_RETORNOS = 30, 10
AVISO_POUCOS = "poucos casos: intervalo pouco confiável"

COLUNAS_USUARIO = [
    "usuario_id", "data_chegada", "semana_chegada", "trimestre", "modelo", "turnos_faixa",
    "periodo_dia", "fim_de_semana", "primeira_mensagem", "resposta_tamanho", "recusa",
    "recusa_nivel", "recusa_motivo", "idioma", "codigo", "tema", "elegivel", "voltou_7d",
]
COLUNAS_EFEITO = [
    "analise", "fator", "nivel", "referencia", "usuarios", "voltaram", "taxa", "taxa_referencia",
    "bruto", "bruto_ic_baixo", "bruto_ic_alto", "ajustado", "ajustado_ic_baixo", "ajustado_ic_alto",
    "metodo", "aviso", "fonte",
]


def nativo(v):
    """Converte valores do pandas/numpy para tipos que o psycopg grava (NaN, NaT e pd.NA viram NULL)."""
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):   # pd.isna de algo que não é escalar
        pass
    if hasattr(v, "item"):
        v = v.item()
    if isinstance(v, float) and math.isnan(v):
        return None
    return v


def sha256_arquivo(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def aplicar_migracoes(con: psycopg.Connection) -> list[str]:
    con.execute("CREATE TABLE IF NOT EXISTS public.schema_migrations "
                "(versao TEXT PRIMARY KEY, aplicada_em TIMESTAMPTZ NOT NULL DEFAULT now())")
    feitas = {r[0] for r in con.execute("SELECT versao FROM public.schema_migrations").fetchall()}
    novas = []
    for arq in sorted(MIGRACOES.glob("*.sql")):
        if arq.stem in feitas:
            continue
        with con.transaction():
            con.execute(arq.read_text(encoding="utf-8"))
            con.execute("INSERT INTO public.schema_migrations (versao) VALUES (%s)", (arq.stem,))
        novas.append(arq.stem)
    return novas


def linhas_usuario() -> list[tuple]:
    df = e07.carregar()
    df["elegivel"] = df[e07.DESFECHO].notna()
    df["voltou_7d"] = df[e07.DESFECHO].map(lambda v: None if pd.isna(v) else bool(v))
    if TEMA.exists():
        tema = duckdb.sql(f"SELECT usuario, tema FROM read_parquet('{TEMA.as_posix()}')").df()
        df = df.merge(tema, on="usuario", how="left")
    else:
        df["tema"] = None
    df["usuario_id"] = df["usuario"].map(lambda u: hashlib.sha256(u.encode("utf-8")).hexdigest())
    df = df.rename(columns={"semana": "semana_chegada"})
    if df["usuario_id"].duplicated().any():
        raise SystemExit("ERRO: usuario_id repetido")
    return [tuple(nativo(v) for v in r) for r in df[COLUNAS_USUARIO].itertuples(index=False)]


def linhas_conversas_dia() -> list[tuple]:
    return duckdb.sql(f"""
        WITH c AS (
            SELECT CAST(timezone('America/Sao_Paulo', "timestamp") AS DATE) AS d
            FROM read_parquet('{BRAZIL.as_posix()}')
        ),
        cal AS (
            SELECT CAST(generate_series AS DATE) AS d
            FROM generate_series((SELECT min(d) FROM c)::TIMESTAMP, (SELECT max(d) FROM c)::TIMESTAMP,
                                 INTERVAL 1 DAY)
        )
        SELECT strftime(cal.d, '%Y-%m-%d'), count(c.d)::INTEGER
        FROM cal LEFT JOIN c USING (d) GROUP BY cal.d ORDER BY cal.d
    """).fetchall()


def linhas_efeitos() -> list[dict]:
    linhas = []

    t = pd.read_csv(EFEITOS_07, sep=";", encoding="utf-8-sig")
    taxa_ref = {(r.fator, r.nivel): r.taxa for r in t.itertuples() if r.nivel == e07.TODOS[r.fator][1]}
    for r in t[t["efeito"].notna()].itertuples():
        ref = e07.TODOS[r.fator][1]
        alt = r.fator == "recusa_nivel"
        linhas.append({
            "analise": "principal", "fator": r.fator, "nivel": r.nivel, "referencia": ref,
            "usuarios": r.usuarios, "voltaram": r.voltaram, "taxa": r.taxa,
            "taxa_referencia": taxa_ref[(r.fator, ref)],
            "bruto": r.bruto, "bruto_ic_baixo": r.bruto_ic_baixo, "bruto_ic_alto": r.bruto_ic_alto,
            "ajustado": r.efeito, "ajustado_ic_baixo": r.ic_baixo, "ajustado_ic_alto": r.ic_alto,
            "metodo": ("regressão logística, efeito marginal médio (IC pelo método delta); "
                       + ("modelo alternativo com a recusa em 3 níveis; " if alt else "")
                       + "bruto: diferença de taxas (IC de Newcombe)"),
            "aviso": AVISO_POUCOS if (r.usuarios < MIN_USUARIOS or r.voltaram < MIN_RETORNOS) else None,
            "fonte": "scripts/07_efeitos.py -> relatorios/07_efeitos.txt",
        })

    for r in pd.read_csv(EFEITOS_07B, sep=";", encoding="utf-8-sig").itertuples():
        linhas.append({
            "analise": "recusa_por_motivo", "fator": r.fator, "nivel": r.nivel, "referencia": r.referencia,
            "usuarios": r.usuarios, "voltaram": r.voltaram, "taxa": r.taxa, "taxa_referencia": r.taxa_referencia,
            "bruto": r.bruto, "bruto_ic_baixo": r.bruto_ic_baixo, "bruto_ic_alto": r.bruto_ic_alto,
            "ajustado": r.efeito, "ajustado_ic_baixo": r.ic_baixo, "ajustado_ic_alto": r.ic_alto,
            "metodo": "mesmo modelo do script 07 com a recusa trocada pelo motivo; bruto: Newcombe",
            "aviso": AVISO_POUCOS if (r.usuarios < MIN_USUARIOS or r.voltaram < MIN_RETORNOS) else None,
            "fonte": "scripts/07b_recusa_motivo.py -> relatorios/07b_recusa_motivo.txt",
        })

    for r in pd.read_csv(EFEITO_09, sep=";", encoding="utf-8-sig").itertuples():
        linhas.append({
            "analise": "gpt4_selecao", "fator": r.fator, "nivel": r.nivel, "referencia": r.referencia,
            "usuarios": r.usuarios, "voltaram": r.voltaram, "taxa": r.taxa, "taxa_referencia": r.taxa_referencia,
            "bruto": r.bruto, "bruto_ic_baixo": r.bruto_ic_baixo, "bruto_ic_alto": r.bruto_ic_alto,
            "ajustado": r.efeito, "ajustado_ic_baixo": r.ic_baixo, "ajustado_ic_alto": r.ic_alto,
            "metodo": (f"ponderação pela probabilidade de escolha (IPTW), IC por bootstrap "
                       f"({int(r.reamostragens)} reamostragens); só trimestres com os dois modelos: {r.recorte}"),
            "aviso": None,
            "fonte": "scripts/09_gpt4_selecao.py -> relatorios/09_gpt4_selecao.txt",
        })
    return [{k: nativo(v) for k, v in l.items()} for l in linhas]


def main() -> None:
    inicio = datetime.now(timezone.utc)
    usuarios = linhas_usuario()
    dias = linhas_conversas_dia()
    efeitos = linhas_efeitos()

    elegiveis = sum(1 for u in usuarios if u[COLUNAS_USUARIO.index("elegivel")])
    voltaram = sum(1 for u in usuarios if u[COLUNAS_USUARIO.index("voltou_7d")])
    total_conversas = duckdb.sql(f"SELECT count(*) FROM read_parquet('{BRAZIL.as_posix()}')").fetchall()[0][0]

    with psycopg.connect(DATABASE_URL) as con:
        novas = aplicar_migracoes(con)
        print(f"Migrações aplicadas nesta execução: {novas or 'nenhuma'}")
        with con.transaction():
            con.execute("TRUNCATE analytics.usuario_primeira_experiencia, analytics.conversas_dia, analytics.efeitos")
            with con.cursor() as cur:
                with cur.copy(f"COPY analytics.usuario_primeira_experiencia ({', '.join(COLUNAS_USUARIO)}) "
                              "FROM STDIN") as cp:
                    for u in usuarios:
                        cp.write_row(u)
                with cur.copy("COPY analytics.conversas_dia (dia, conversas) FROM STDIN") as cp:
                    for d in dias:
                        cp.write_row(d)
                cur.executemany(
                    f"INSERT INTO analytics.efeitos ({', '.join(COLUNAS_EFEITO)}) "
                    f"VALUES ({', '.join('%(' + c + ')s' for c in COLUNAS_EFEITO)})", efeitos)

            # Conferência contra a origem: se algo não bater, a transação inteira é desfeita.
            banco = con.execute("""
                SELECT count(*), count(*) FILTER (WHERE elegivel), count(*) FILTER (WHERE voltou_7d),
                       (SELECT sum(conversas) FROM analytics.conversas_dia),
                       (SELECT count(*) FROM analytics.efeitos)
                FROM analytics.usuario_primeira_experiencia
            """).fetchone()
            esperado = (len(usuarios), elegiveis, voltaram, total_conversas, len(efeitos))
            checagens = {
                "usuarios": [banco[0], esperado[0]], "elegiveis": [banco[1], esperado[1]],
                "voltaram": [banco[2], esperado[2]], "conversas": [banco[3], esperado[3]],
                "efeitos": [banco[4], esperado[4]],
            }
            divergentes = {k: v for k, v in checagens.items() if v[0] != v[1]}
            if divergentes:
                raise SystemExit(f"ERRO: banco diverge da origem {divergentes}; carga desfeita")

            con.execute(
                "INSERT INTO analytics.carga_execucao VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (uuid.uuid4(), inicio, datetime.now(timezone.utc), os.environ.get("VERSAO_CODIGO", "local"),
                 sha256_arquivo(BRAZIL),
                 json.dumps({"usuarios": len(usuarios), "conversas_dia": len(dias), "efeitos": len(efeitos)}),
                 json.dumps(checagens)),
            )

    print(f"Carga concluída: {len(usuarios)} usuários ({elegiveis} elegíveis, {voltaram} voltaram), "
          f"{len(dias)} dias, {len(efeitos)} efeitos. Totais conferidos com a origem.")


if __name__ == "__main__":
    main()
