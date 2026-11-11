"""
GPT-4: quem escolhe é diferente? E, comparando grupos semelhantes, o modelo muda o retorno?

O enunciado cita esse fator de confusão ("quem escolhe o GPT-4 já ser mais engajado").
O script 07 deu GPT-4 -1,3 pp [-6,1; +3,5], mas aquele modelo controla variáveis que
acontecem DEPOIS da escolha do modelo (turnos, tamanho da resposta, recusa, código):
isso mede um efeito "a turnos iguais", não o efeito total de escolher o GPT-4.

Aqui:
    1. Balanço: diferença padronizada (SMD) entre quem usou GPT-4 e GPT-3.5 em cada
       característica. |SMD| < 0,10 é a regra usual de balanço aceitável (Austin, 2009,
       Statistics in Medicine 28:3083-3107).
         - antes da escolha (entram no peso): período do dia, fim de semana, trimestre,
           1ª mensagem, idioma, sistema operacional, navegador
         - depois da escolha (só descritivo, NÃO entram no peso, porque podem ser
           consequência do modelo): turnos, tamanho da resposta, recusa, código
    2. Ponderação pelo inverso da probabilidade de escolha (IPTW, pesos estabilizados;
       Austin e Stuart, 2015, Statistics in Medicine 34:3661-3679): cada grupo é
       re-pesado para ficar parecido com a base inteira nas características de antes.
    3. Efeito total do GPT-4 = taxa ponderada GPT-4 - taxa ponderada GPT-3.5, com IC 95%
       por bootstrap (o modelo de probabilidade é reestimado em cada reamostragem).
    4. Por trimestre: participação do GPT-4 e retorno de cada modelo.

v2 (11/11): a v1 violou a sobreposição. Em 2023-T3 nenhum usuário começou no GPT-4,
e em 2024 quase ninguém começou no GPT-3.5 (43 e 10). Com isso, a probabilidade de
escolha foi de 0,000 a 0,989, o maior peso chegou a 23,7 e o trimestre continuou
desequilibrado depois do peso (SMD de -0,67 em 2023-T3). Comparar GPT-4 e GPT-3.5 só
faz sentido onde os dois estavam em uso. Regra [PREMISSA]: o efeito é estimado só nos
trimestres em que cada modelo tem pelo menos 100 usuários. Os outros trimestres
aparecem na tabela por trimestre, mas não entram no peso nem no efeito.

Leitura fixada antes de rodar [PREMISSA]:
    - IC do efeito ponderado inclui zero -> sem evidência de efeito do modelo no retorno,
      mesmo comparando grupos parecidos no que é observável
    - balanço depois do peso com algum |SMD| >= 0,10 -> o peso não resolveu; reportar
    - não prova ausência de efeito: o que não foi medido (ex.: intenção de uso) continua
      podendo diferir entre os grupos

Uso:
    python scripts/09_gpt4_selecao.py

Entradas: as do script 07 (a carga vem do próprio 07)
Saídas:   relatorios/09_gpt4_selecao.txt, data/gold/efeito_gpt4_iptw.csv
"""
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

sys.stdout.reconfigure(encoding="utf-8")

_spec = importlib.util.spec_from_file_location("efeitos07", Path(__file__).with_name("07_efeitos.py"))
e07 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(e07)

RELATORIO = Path("relatorios/09_gpt4_selecao.txt")
TABELA = Path("data/gold/efeito_gpt4_iptw.csv")   # lida pela carga do dashboard
ANTES = ["periodo_dia", "fim_de_semana", "trimestre", "primeira_mensagem", "idioma", "so", "navegador"]
DEPOIS = ["turnos_faixa", "resposta_tamanho", "recusa", "codigo"]
SMD_MAX = 0.10
MIN_POR_MODELO_TRI = 100   # sobreposição: trimestre entra no efeito se cada modelo tem >= 100
MIN_NIVEL = 30          # níveis com menos usuários viram "outro" no modelo de probabilidade
N_BOOT = 1000
SEMENTE = 42


def smd(x: np.ndarray, t: np.ndarray, w: np.ndarray | None = None) -> float:
    """Diferença padronizada de uma variável 0/1 entre tratados (t=1) e controles."""
    w = np.ones_like(x, dtype=float) if w is None else w
    p1 = np.average(x[t == 1], weights=w[t == 1])
    p0 = np.average(x[t == 0], weights=w[t == 0])
    den = np.sqrt((p1 * (1 - p1) + p0 * (1 - p0)) / 2)
    return 0.0 if den == 0 else (p1 - p0) / den


def pesos(X: np.ndarray, t: np.ndarray) -> np.ndarray:
    # C muito alto = regressão logística praticamente sem penalização
    ps = LogisticRegression(C=1e6, max_iter=5000).fit(X, t).predict_proba(X)[:, 1]
    p = t.mean()
    return np.where(t == 1, p / ps, (1 - p) / (1 - ps)), ps


def efeito(y: np.ndarray, t: np.ndarray, w: np.ndarray) -> tuple[float, float, float]:
    r1 = np.average(y[t == 1], weights=w[t == 1])
    r0 = np.average(y[t == 0], weights=w[t == 0])
    return r1, r0, r1 - r0


def ess(w: np.ndarray) -> float:
    return w.sum() ** 2 / (w ** 2).sum()


def main() -> None:
    RELATORIO.parent.mkdir(parents=True, exist_ok=True)
    out = RELATORIO.open("w", encoding="utf-8")

    def escrever(s: str = "") -> None:
        print(s)
        out.write(s + "\n")

    y_col = e07.DESFECHO
    df = e07.carregar()
    df = df[df[y_col].notna() & df["modelo"].isin(["GPT-3.5", "GPT-4"])].copy()
    partes = df["usuario"].str.split("|", expand=True)
    df["so"], df["navegador"] = partes[1], partes[2]
    for c in ["so", "navegador"]:
        cont = df[c].value_counts()
        df[c] = df[c].where(df[c].map(cont) >= MIN_NIVEL, "outro (<30)")

    escrever(f"Desfecho: {y_col} | base: {len(df)} elegíveis | GPT-4: {(df['modelo'] == 'GPT-4').sum()} | "
             f"GPT-3.5: {(df['modelo'] == 'GPT-3.5').sum()}")
    escrever("Leitura fixada antes de rodar: ver cabeçalho do script.")

    # ------------------------------------------------------------ por trimestre (base inteira)
    escrever("\n== Por trimestre de chegada (base inteira)")
    escrever("trimestre | usuários | % GPT-4 | retorno GPT-4 | retorno GPT-3.5 | diferença pp [IC95] | entra no efeito")
    suporte = []
    for tri, g in df.groupby("trimestre"):
        g4, g3 = g[g["modelo"] == "GPT-4"], g[g["modelo"] == "GPT-3.5"]
        txt = lambda s: f"{s[y_col].mean():.1%} (n={len(s)})" if len(s) else "—"
        entra = len(g4) >= MIN_POR_MODELO_TRI and len(g3) >= MIN_POR_MODELO_TRI
        if entra:
            suporte.append(tri)
        dif = "—"
        if len(g4) and len(g3):
            dd, dl_, dh_ = e07.newcombe(int(g4[y_col].sum()), len(g4), int(g3[y_col].sum()), len(g3))
            dif = f"{dd * 100:+.1f} [{dl_ * 100:+.1f}; {dh_ * 100:+.1f}]"
        escrever(f"{tri} | {len(g)} | {len(g4) / len(g):.1%} | {txt(g4)} | {txt(g3)} | {dif} | {'sim' if entra else 'não'}")

    fora = df[~df["trimestre"].isin(suporte)]
    df = df[df["trimestre"].isin(suporte)].copy()
    escrever(f"\nSobreposição (cada modelo >= {MIN_POR_MODELO_TRI} no trimestre): {', '.join(suporte)}")
    escrever(f"  dentro: {len(df)} usuários | fora: {len(fora)}")
    for c in ["so", "navegador"]:   # reagrupa níveis raros dentro do recorte
        cont = df[c].value_counts()
        df[c] = df[c].where(df[c].map(cont) >= MIN_NIVEL, "outro (<30)")
    t = (df["modelo"] == "GPT-4").to_numpy().astype(int)
    y = df[y_col].astype(int).to_numpy()
    escrever(f"  GPT-4: {t.sum()} | GPT-3.5: {(1 - t).sum()}")

    X_antes = pd.get_dummies(df[ANTES], drop_first=True).astype(float).to_numpy()
    D_antes = pd.get_dummies(df[ANTES], prefix_sep=" = ").astype(float)
    D_depois = pd.get_dummies(df[DEPOIS], prefix_sep=" = ").astype(float)

    w, ps = pesos(X_antes, t)
    escrever(f"\nProbabilidade de escolher GPT-4 (modelo com as variáveis de antes): "
             f"mín {ps.min():.3f}, máx {ps.max():.3f}")
    escrever(f"Pesos estabilizados: mín {w.min():.2f}, máx {w.max():.2f} | tamanho efetivo: "
             f"GPT-4 {ess(w[t == 1]):.0f} de {t.sum()}, GPT-3.5 {ess(w[t == 0]):.0f} de {(1 - t).sum()}")

    # ------------------------------------------------------------ balanço
    escrever(f"\n== Balanço (SMD; |SMD| >= {SMD_MAX:.2f} marcado com *)")
    escrever("característica | % GPT-4 | % GPT-3.5 | SMD antes do peso | SMD depois do peso")
    desbalanceadas_antes, desbalanceadas_depois = [], []
    for col in D_antes.columns:
        x = D_antes[col].to_numpy()
        a, d = smd(x, t), smd(x, t, w)
        if abs(a) >= SMD_MAX:
            desbalanceadas_antes.append(col)
        if abs(d) >= SMD_MAX:
            desbalanceadas_depois.append(col)
        escrever(f"{col} | {x[t == 1].mean():.1%} | {x[t == 0].mean():.1%} | "
                 f"{a:+.2f}{'*' if abs(a) >= SMD_MAX else ''} | {d:+.2f}{'*' if abs(d) >= SMD_MAX else ''}")
    escrever(f"Antes do peso: {len(desbalanceadas_antes)} característica(s) com |SMD| >= {SMD_MAX:.2f}")
    escrever(f"Depois do peso: {len(desbalanceadas_depois)} característica(s) com |SMD| >= {SMD_MAX:.2f}"
             + (f": {', '.join(desbalanceadas_depois)}" if desbalanceadas_depois else ""))

    escrever("\n== Depois da escolha do modelo (só descritivo; podem ser consequência do GPT-4)")
    escrever("característica | % GPT-4 | % GPT-3.5 | SMD")
    for col in D_depois.columns:
        x = D_depois[col].to_numpy()
        a = smd(x, t)
        escrever(f"{col} | {x[t == 1].mean():.1%} | {x[t == 0].mean():.1%} | {a:+.2f}{'*' if abs(a) >= SMD_MAX else ''}")

    # ------------------------------------------------------------ efeito
    k1, n1 = int(y[t == 1].sum()), int(t.sum())
    k0, n0 = int(y[t == 0].sum()), int((1 - t).sum())
    d, dl, dh = e07.newcombe(k1, n1, k0, n0)
    r1, r0, dif = efeito(y, t, w)

    rng = np.random.default_rng(SEMENTE)
    boot = []
    n = len(y)
    for _ in range(N_BOOT):
        i = rng.integers(0, n, n)
        if t[i].min() == t[i].max():
            continue
        wb, _ = pesos(X_antes[i], t[i])
        boot.append(efeito(y[i], t[i], wb)[2])
    lo, hi = np.percentile(boot, [2.5, 97.5])

    escrever(f"\n== Efeito do GPT-4 no retorno em 7 dias, dentro da sobreposição (pontos percentuais)")
    escrever(f"bruto: GPT-4 {k1 / n1:.1%} vs GPT-3.5 {k0 / n0:.1%} -> {d * 100:+.1f} [{dl * 100:+.1f}; {dh * 100:+.1f}] (Newcombe)")
    escrever(f"ponderado (IPTW, efeito total): GPT-4 {r1:.1%} vs GPT-3.5 {r0:.1%} -> {dif * 100:+.1f} "
             f"[{lo * 100:+.1f}; {hi * 100:+.1f}] (bootstrap, {len(boot)} reamostragens)")
    escrever("referência: script 07, base inteira, a turnos, resposta, recusa e código iguais: -1,3 [-6,1; +3,5]")
    pd.DataFrame([{
        "fator": "modelo_iptw", "nivel": "GPT-4", "referencia": "GPT-3.5",
        "recorte": ", ".join(suporte), "usuarios": n1, "voltaram": k1, "taxa": k1 / n1,
        "usuarios_referencia": n0, "taxa_referencia": k0 / n0,
        "bruto": d, "bruto_ic_baixo": dl, "bruto_ic_alto": dh,
        "taxa_ponderada": r1, "taxa_referencia_ponderada": r0,
        "efeito": dif, "ic_baixo": lo, "ic_alto": hi, "reamostragens": len(boot),
        "caracteristicas_desequilibradas_depois": len(desbalanceadas_depois),
    }]).to_csv(TABELA, index=False, sep=";", encoding="utf-8-sig")

    # ------------------------------------------------------------ leitura
    escrever("\n== Aplicação da leitura fixada")
    if lo <= 0 <= hi:
        escrever("IC do efeito ponderado inclui zero: sem evidência de efeito do GPT-4 no retorno, "
                 "mesmo comparando grupos parecidos no que é observável.")
    else:
        escrever("IC do efeito ponderado exclui zero: há diferença de retorno entre os modelos "
                 "depois de equilibrar os grupos no que é observável.")
    if desbalanceadas_depois:
        escrever("Atenção: o peso não equilibrou todas as características (lista acima).")
    escrever("Não prova: o que não foi medido (intenção de uso, experiência prévia) pode diferir entre os grupos.")
    out.close()
    print(f"\nRelatório: {RELATORIO}")


if __name__ == "__main__":
    main()
