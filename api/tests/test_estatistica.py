"""O IC da API tem de bater com o dos scripts de análise (valores dos relatórios 07 e 10)."""
import pytest

from app.estatistica import wilson


@pytest.mark.parametrize("k, n, baixo, alto", [
    (598, 2482, 0.225, 0.258),   # base inteira, relatorios/07_efeitos.txt
    (14, 41, 0.216, 0.495),      # semana 2023-08-14, relatorios/10_semana_atipica.txt
    (0, 9, 0.000, 0.299),        # semana 2023-10-09, idem
    (6, 83, 0.034, 0.149),       # recusa por limitação do produto, relatorios/07b_recusa_motivo.txt
])
def test_wilson_bate_com_a_analise(k, n, baixo, alto):
    b, a = wilson(k, n)
    assert round(b, 3) == pytest.approx(baixo, abs=0.0006)
    assert round(a, 3) == pytest.approx(alto, abs=0.0006)


def test_sem_usuarios_nao_tem_intervalo():
    assert wilson(0, 0) == (None, None)


def test_mais_retornos_que_usuarios_e_erro():
    with pytest.raises(ValueError):
        wilson(5, 3)
