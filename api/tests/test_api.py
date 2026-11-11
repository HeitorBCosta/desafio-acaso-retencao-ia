"""Contrato dos endpoints, sem banco: as consultas são substituídas por dados fixos."""
from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient

import app.main as api

CARGA = {"carga_id": "c1", "fim": datetime(2026, 11, 11, tzinfo=timezone.utc),
         "versao_codigo": "teste", "linhas": {}, "checagens": {}}

RESPOSTAS = {
    "ultima_carga": [CARGA],
    "periodo_dados": [{"inicio": date(2023, 4, 8), "fim": date(2024, 4, 22)}],
    "visao_geral": [{"novos": 2482, "voltaram": 598,
                     "primeira_data": date(2023, 4, 8), "ultima_data": date(2024, 4, 22)}],
    "coortes": [{"periodo": date(2023, 8, 14), "novos": 41, "voltaram": 14},
                {"periodo": date(2023, 10, 9), "novos": 9, "voltaram": 0}],
    "dias_sem_dados": [{"dia": date(2023, 10, 13)}],
    "efeitos": [],
}


@pytest.fixture
def cliente(monkeypatch):
    monkeypatch.setattr(api, "consultar", lambda nome, params=None: RESPOSTAS[nome])
    monkeypatch.setattr(api.pool, "open", lambda **kw: None)
    monkeypatch.setattr(api.pool, "close", lambda: None)
    api._cache.clear()
    api._carga.update({"id": None, "conferida_em": 0.0})
    with TestClient(api.app) as c:
        yield c


def test_visao_geral_calcula_taxa_e_ic(cliente):
    r = cliente.get("/api/visao-geral").json()
    assert r["novos"] == 2482 and r["voltaram"] == 598
    assert r["taxa"] == pytest.approx(598 / 2482)
    assert r["ic_baixo"] == pytest.approx(0.225, abs=0.001)
    assert r["base_pequena"] is False


def test_coorte_pequena_nao_mostra_intervalo(cliente):
    coortes = cliente.get("/api/retencao/coortes").json()["coortes"]
    grande, pequena = coortes
    assert grande["base_pequena"] is False and grande["ic_baixo"] is not None
    assert pequena["base_pequena"] is True and pequena["ic_baixo"] is None


def test_granularidade_invalida_e_recusada(cliente):
    assert cliente.get("/api/retencao/coortes?granularidade=dia").status_code == 422


def test_inicio_depois_do_fim_e_recusado(cliente):
    assert cliente.get("/api/visao-geral?inicio=2024-01-01&fim=2023-01-01").status_code == 422


def test_sem_carga_responde_503(cliente, monkeypatch):
    monkeypatch.setitem(RESPOSTAS, "ultima_carga", [])
    api._carga.update({"id": None, "conferida_em": 0.0})
    assert cliente.get("/api/visao-geral").status_code == 503


def test_toda_resposta_traz_tempo(cliente):
    assert "Server-Timing" in cliente.get("/api/definicoes").headers
