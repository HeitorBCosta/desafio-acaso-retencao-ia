"""
API do dashboard de retenção (FastAPI).

Lê só a base analítica (schema analytics), nunca a base bruta. Os efeitos chegam
pré-calculados pela carga; aqui só há agregações simples e o IC de Wilson.

Cache: em memória, por endpoint e parâmetros, com a versão da carga na chave. Quando
uma carga nova termina, a chave muda e o cache antigo deixa de ser usado; além disso,
cada entrada expira em CACHE_TTL segundos.

Tempo de resposta: cada requisição gera uma linha de log em JSON (rota, parâmetros,
status, duração, versão da carga) e o cabeçalho Server-Timing.
"""
import json
import logging
import time
from contextlib import asynccontextmanager
from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request

from .banco import consultar, pool
from .estatistica import wilson
from .rotulos import DEFINICOES, FATORES, MIN_COORTE, rotulo_nivel

CACHE_TTL = 600          # segundos
CARGA_TTL = 60           # de quanto em quanto tempo a API confere se houve carga nova
GRANULARIDADE = {"semana": "week", "mes": "month"}

log = logging.getLogger("api")
logging.basicConfig(level=logging.INFO, format="%(message)s")

_cache: dict[tuple, tuple[float, object]] = {}
_carga: dict = {"id": None, "conferida_em": 0.0}


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    pool.open(wait=True)
    yield
    pool.close()


app = FastAPI(title="Retenção do assistente de IA — Brasil", version="1.0", lifespan=ciclo_de_vida)


def carga_atual() -> str | None:
    agora = time.monotonic()
    if agora - _carga["conferida_em"] > CARGA_TTL:
        linhas = consultar("ultima_carga")
        _carga["id"] = linhas[0]["carga_id"] if linhas else None
        _carga["conferida_em"] = agora
    return _carga["id"]


def em_cache(chave: tuple, calcular):
    carga = carga_atual()
    if carga is None:
        raise HTTPException(503, "A base analítica ainda não foi carregada.")
    chave = (carga, *chave)
    agora = time.monotonic()
    if chave in _cache and agora - _cache[chave][0] < CACHE_TTL:
        return _cache[chave][1]
    valor = calcular()
    _cache[chave] = (agora, valor)
    return valor


def numero(v):
    return float(v) if isinstance(v, Decimal) else v


def periodo(inicio: date | None, fim: date | None) -> tuple[date, date]:
    limites = em_cache(("periodo",), lambda: consultar("periodo_dados")[0])
    inicio = inicio or limites["inicio"]
    fim = fim or limites["fim"]
    if inicio > fim:
        raise HTTPException(422, "inicio deve ser anterior ou igual a fim.")
    return inicio, fim


@app.middleware("http")
async def medir_tempo(request: Request, call_next):
    t0 = time.perf_counter()
    resposta = await call_next(request)
    ms = (time.perf_counter() - t0) * 1000
    resposta.headers["Server-Timing"] = f"app;dur={ms:.1f}"
    log.info(json.dumps({"rota": request.url.path, "params": dict(request.query_params),
                         "status": resposta.status_code, "ms": round(ms, 1), "carga": _carga["id"]}))
    return resposta


@app.get("/api/saude")
def saude():
    linhas = consultar("ultima_carga")
    if not linhas:
        raise HTTPException(503, "A base analítica ainda não foi carregada.")
    c = linhas[0]
    return {"status": "ok", "carga_id": c["carga_id"], "carga_fim": c["fim"],
            "versao_codigo": c["versao_codigo"], "linhas": c["linhas"], "checagens": c["checagens"]}


@app.get("/api/definicoes")
def definicoes():
    return {"definicoes": DEFINICOES, "fatores": FATORES, "min_coorte": MIN_COORTE}


@app.get("/api/periodo")
def periodo_disponivel():
    inicio, fim = periodo(None, None)
    return {"inicio": inicio, "fim": fim}


@app.get("/api/visao-geral")
def visao_geral(inicio: date | None = None, fim: date | None = None):
    inicio, fim = periodo(inicio, fim)

    def calcular():
        r = consultar("visao_geral", {"inicio": inicio, "fim": fim})[0]
        novos, voltaram = r["novos"], r["voltaram"]
        baixo, alto = wilson(voltaram, novos)
        carga = consultar("ultima_carga")[0]
        return {"inicio": inicio, "fim": fim, "novos": novos, "voltaram": voltaram,
                "taxa": voltaram / novos if novos else None, "ic_baixo": baixo, "ic_alto": alto,
                "base_pequena": novos < MIN_COORTE, "data_da_carga": carga["fim"]}

    return em_cache(("visao_geral", inicio, fim), calcular)


@app.get("/api/retencao/coortes")
def coortes(inicio: date | None = None, fim: date | None = None,
            granularidade: Literal["semana", "mes"] = Query("semana")):
    inicio, fim = periodo(inicio, fim)

    def calcular():
        linhas = consultar("coortes", {"inicio": inicio, "fim": fim,
                                       "granularidade": GRANULARIDADE[granularidade]})
        saida = []
        for r in linhas:
            n, k = r["novos"], r["voltaram"]
            pequena = n < MIN_COORTE
            baixo, alto = (None, None) if pequena else wilson(k, n)
            saida.append({"periodo": r["periodo"], "novos": n, "voltaram": k, "taxa": k / n,
                          "ic_baixo": baixo, "ic_alto": alto, "base_pequena": pequena})
        return {"granularidade": granularidade, "min_coorte": MIN_COORTE, "coortes": saida}

    return em_cache(("coortes", inicio, fim, granularidade), calcular)


@app.get("/api/efeitos")
def efeitos():
    def calcular():
        saida = []
        for r in consultar("efeitos"):
            r = {k: numero(v) for k, v in r.items()}
            baixo, alto = r["ajustado_ic_baixo"], r["ajustado_ic_alto"]
            r["rotulo_fator"] = FATORES.get(r["fator"], r["fator"])
            r["rotulo_nivel"] = rotulo_nivel(r["fator"], r["nivel"])
            r["rotulo_referencia"] = rotulo_nivel(r["fator"], r["referencia"])
            r["ic_exclui_zero"] = None if baixo is None else (baixo > 0 or alto < 0)
            saida.append(r)
        return {"efeitos": saida}

    return em_cache(("efeitos",), calcular)


@app.get("/api/qualidade/dias-sem-dados")
def dias_sem_dados(inicio: date | None = None, fim: date | None = None):
    inicio, fim = periodo(inicio, fim)
    return em_cache(("dias_sem_dados", inicio, fim),
                    lambda: {"dias": [r["dia"] for r in consultar("dias_sem_dados",
                                                                  {"inicio": inicio, "fim": fim})]})
