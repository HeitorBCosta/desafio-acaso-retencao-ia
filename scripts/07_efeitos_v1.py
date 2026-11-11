"""
Efeito de cada fator da primeira conversa no retorno em 7 dias (BDR-003, sessão de 30 min).

Para cada nível de cada fator, comparado com um nível de referência:
    bruto     diferença simples de taxas, em pontos percentuais (IC 95% de Newcombe)
    ajustado  efeito marginal médio de uma regressão logística com todos os fatores
              e o trimestre de chegada como controle (IC 95% pelo método delta)
Ordenado pelo tamanho do efeito ajustado.

Sensibilidade: o mesmo modelo ajustado para outras regras de retorno (1 h, 24 h,
outro dia em America/Sao_Paulo), para ver se a direção do efeito se mantém.

Fatores incluídos (já conferidos): modelo, turnos, período do dia, fim de semana,
tamanho da pergunta, tamanho da resposta, tipo da primeira mensagem.
Ficam de fora até a conferência fechar: recusa (BDR-005), idioma, código, tema.

Uso:
    pip install pandas statsmodels
    python scripts/07_efeitos.py

Entrada: data/gold/base_analise.parquet (script 06)
Saídas:  relatorios/07_efeitos.txt, data/gold/efeitos.csv
"""
import math
import sys
from pathlib import Path

import duckdb
import pandas as pd
import statsmodels.formula.api as smf

sys.stdout.reconfigure(encoding="utf-8")

GOLD = Path("data/gold/base_analise.parquet")
RELATORIO = Path("relatorios/07_efeitos.txt")
EFEITOS = Path("data/gold/efeitos.csv")

DESFECHO = "retorno_7d_30min"  # BDR-003
SENSIBILIDADE = ["retorno_7d_1h", "retorno_7d_24h", "retorno_7d_outro_dia_sp"]
MIN_GRUPO = 30  # abaixo disso o nível é sinalizado como base pequena

# Fator -> (rótulo para o relatório, nível de referência)
FATORES = {
    "modelo": ("Modelo", "GPT-3.5"),
    "turnos_faixa": ("Nº de turnos da 1ª conversa", "1"),
    "periodo_dia": ("Período do dia (Brasília)", "tarde (12-17h)"),
    "fim_de_semana": ("Fim de semana", "não"),
    "pergunta_tamanho": ("Tamanho da 1ª pergunta", "média (20-194)"),
    "resposta_tamanho": ("Tamanho da 1ª resposta", "média (137-2.086)"),
    "primeira_mensagem": ("Tipo da 1ª mensagem", "pedido"),
}
CONTROLES = ["trimestre"]


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return c - m, c + m


def newcombe(k1: int, n1: int, k2: int, n2: int) -> tuple[float, float, float]:
    """Diferença p1 - p2 com IC 95% de Newcombe (método 10, a partir de Wilson)."""
    p1, p2 = k1 / n1, k2 / n2
    l1, u1 = wilson(k1, n1)
    l2, u2 = wilson(k2, n2)
    d = p1 - p2
    return d, d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2), d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)


def carregar() -> pd.DataFrame:
    # Faixas de tamanho: p25 e p75 medidos no script 04 (pergunta 19 / 194; resposta 137 / 2.086).
    return duckdb.sql(f"""
        SELECT usuario,
               modelo_familia AS modelo,
               CASE WHEN turnos = 1 THEN '1' WHEN turnos = 2 THEN '2'
                    WHEN turnos <= 4 THEN '3-4' ELSE '5+' END AS turnos_faixa,
               CASE WHEN hora_local < 6 THEN 'madrugada (0-5h)'
                    WHEN hora_local < 12 THEN 'manhã (6-11h)'
                    WHEN hora_local < 18 THEN 'tarde (12-17h)'
                    ELSE 'noite (18-23h)' END AS periodo_dia,
               CASE WHEN dia_semana_iso >= 6 THEN 'sim' ELSE 'não' END AS fim_de_semana,
               CASE WHEN pergunta_chars < 20 THEN 'curta (<20)'
                    WHEN pergunta_chars <= 194 THEN 'média (20-194)'
                    ELSE 'longa (>194)' END AS pergunta_tamanho,
               CASE WHEN resposta_chars < 137 THEN 'curta (<137)'
                    WHEN resposta_chars <= 2086 THEN 'média (137-2.086)'
                    ELSE 'longa (>2.086)' END AS resposta_tamanho,
               -- BDR-004: texto_ausente conta como pedido (a IA respondeu a algo);
               -- confirmada e indeterminada contam como vazia.
               CASE WHEN pergunta_saudacao OR pergunta_teste THEN 'só saudação ou teste'
                    WHEN pergunta_vazia AND pergunta_vazia_tipo <> 'texto_ausente' THEN 'vazia'
                    ELSE 'pedido' END AS primeira_mensagem,
               strftime(timezone('America/Sao_Paulo', t_inicio_utc), '%Y') || '-T' ||
                   CAST(quarter(timezone('America/Sao_Paulo', t_inicio_utc)) AS VARCHAR) AS trimestre,
               {DESFECHO}, {", ".join(SENSIBILIDADE)}
        FROM read_parquet('{GOLD.as_posix()}')
    """).df()


def formula(y: str) -> str:
    termos = [f'C({f}, Treatment("{ref}"))' for f, (_, ref) in FATORES.items()]
    termos += [f"C({c})" for c in CONTROLES]
    return f"{y} ~ " + " + ".join(termos)


def efeitos_ajustados(df: pd.DataFrame, y: str) -> pd.DataFrame:
    d = df[df[y].notna()].copy()
    d[y] = d[y].astype(int)
    modelo = smf.logit(formula(y), data=d).fit(disp=False)
    me = modelo.get_margeff(at="overall", dummy=True).summary_frame()
    # Colunas por posição: dy/dx, erro padrão, z, p, IC baixo, IC alto.
    linhas = []
    for nome, r in me.iterrows():
        for f in FATORES:
            if nome.startswith(f"C({f},") and "[T." in nome:
                nivel = nome[nome.index("[T.") + 3:-1]
                linhas.append({"fator": f, "nivel": nivel, "efeito": r.iloc[0],
                               "ic_baixo": r.iloc[4], "ic_alto": r.iloc[5]})
    return pd.DataFrame(linhas), modelo


def main() -> None:
    RELATORIO.parent.mkdir(parents=True, exist_ok=True)
    out = RELATORIO.open("w", encoding="utf-8")

    def escrever(texto: str = "") -> None:
        print(texto)
        out.write(texto + "\n")

    df = carregar()
    base = df[df[DESFECHO].notna()].copy()
    base[DESFECHO] = base[DESFECHO].astype(int)
    n, k = len(base), int(base[DESFECHO].sum())
    lo, hi = wilson(k, n)

    escrever("Decisões e premissas desta execução:")
    escrever("  BDR-001 usuário = hashed_ip + SO + navegador | BDR-002 primeira conversa")
    escrever(f"  BDR-003 desfecho = {DESFECHO} | só usuários elegíveis (janela de 7 dias observada)")
    escrever("  BDR-004 tipo da 1ª mensagem: texto_ausente conta como pedido; confirmada/indeterminada como vazia")
    escrever("  faixas de tamanho pelos p25/p75 do script 04; controle: trimestre de chegada (Brasília)")
    escrever("  IC 95%: Newcombe (bruto) e método delta (ajustado); usuários supostos independentes")
    escrever("  fora desta versão: recusa, idioma, código, tema (conferência pendente)")
    escrever(f"\n[MEDIDO] Base: {n} usuários elegíveis, {k} voltaram, taxa {k / n:.1%} (IC95 {lo:.1%} a {hi:.1%})")

    # ------------------------------------------------------------ bruto
    brutos = []
    for f, (rotulo, ref) in FATORES.items():
        g = base.groupby(f)[DESFECHO].agg(["sum", "count"])
        if ref not in g.index:
            escrever(f"\nERRO: referência '{ref}' não encontrada em {f}: {list(g.index)}")
            continue
        k2, n2 = int(g.loc[ref, "sum"]), int(g.loc[ref, "count"])
        for nivel, r in g.iterrows():
            k1, n1 = int(r["sum"]), int(r["count"])
            linha = {"fator": f, "nivel": nivel, "usuarios": n1, "voltaram": k1, "taxa": k1 / n1}
            if nivel != ref:
                d, dl, dh = newcombe(k1, n1, k2, n2)
                linha.update({"bruto": d, "bruto_ic_baixo": dl, "bruto_ic_alto": dh})
            brutos.append(linha)
    brutos = pd.DataFrame(brutos)

    # ------------------------------------------------------------ ajustado
    ajust, modelo = efeitos_ajustados(df, DESFECHO)
    escrever(f"\n[MEDIDO] Regressão logística: {int(modelo.nobs)} usuários, "
             f"pseudo-R² de McFadden {modelo.prsquared:.3f}")

    tab = brutos.merge(ajust, on=["fator", "nivel"], how="left")
    for y in SENSIBILIDADE:
        s, _ = efeitos_ajustados(df, y)
        tab = tab.merge(s[["fator", "nivel", "efeito"]].rename(columns={"efeito": f"ajustado_{y}"}),
                        on=["fator", "nivel"], how="left")

    def mesmo_sinal(r: pd.Series) -> str:
        if pd.isna(r["efeito"]):
            return ""
        sinais = {math.copysign(1, r["efeito"])} | {
            math.copysign(1, r[f"ajustado_{y}"]) for y in SENSIBILIDADE if pd.notna(r[f"ajustado_{y}"])}
        return "sim" if len(sinais) == 1 else "não"

    tab["direcao_mantida_nas_outras_regras"] = tab.apply(mesmo_sinal, axis=1)
    tab["ic_exclui_zero"] = (tab["ic_baixo"] > 0) | (tab["ic_alto"] < 0)
    tab["base_pequena"] = tab["usuarios"] < MIN_GRUPO
    tab.to_csv(EFEITOS, index=False, sep=";", encoding="utf-8-sig")

    # ------------------------------------------------------------ relatório
    pp = lambda x: "" if pd.isna(x) else f"{x * 100:+.1f}"
    escrever("\n== Taxa por nível (bruto)")
    escrever("fator | nivel | usuarios | voltaram | taxa")
    for _, r in brutos.iterrows():
        marca = " (referência)" if r["nivel"] == FATORES[r["fator"]][1] else ""
        escrever(f"{FATORES[r['fator']][0]} | {r['nivel']}{marca} | {r['usuarios']} | {r['voltaram']} | {r['taxa']:.1%}")

    escrever("\n== Efeitos, ordenados pelo tamanho do efeito ajustado (pontos percentuais vs referência)")
    escrever("fator | nivel | usuarios | bruto [IC95] | ajustado [IC95] | IC exclui 0 | "
             "mesma direção em 1h/24h/outro dia | base pequena")
    ordem = tab[tab["efeito"].notna()].reindex(
        tab[tab["efeito"].notna()]["efeito"].abs().sort_values(ascending=False).index)
    for _, r in ordem.iterrows():
        escrever(f"{FATORES[r['fator']][0]} | {r['nivel']} | {r['usuarios']} | "
                 f"{pp(r['bruto'])} [{pp(r['bruto_ic_baixo'])}; {pp(r['bruto_ic_alto'])}] | "
                 f"{pp(r['efeito'])} [{pp(r['ic_baixo'])}; {pp(r['ic_alto'])}] | "
                 f"{'sim' if r['ic_exclui_zero'] else 'não'} | {r['direcao_mantida_nas_outras_regras']} | "
                 f"{'sim' if r['base_pequena'] else ''}")

    escrever("\nLeitura: 'ajustado' compara usuários com os mesmos valores nos outros fatores e no "
             "trimestre de chegada. Não prova causa: fatores não medidos (ex.: intenção de uso) "
             "continuam podendo explicar parte do efeito.")
    out.close()
    print(f"\nRelatório: {RELATORIO}\nTabela: {EFEITOS}")


if __name__ == "__main__":
    main()