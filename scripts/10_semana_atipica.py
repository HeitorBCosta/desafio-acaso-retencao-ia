"""
Uma semana em que o retorno caiu ou subiu: mudou o perfil de quem chegou ou mudou a
taxa de retorno dentro de cada perfil? (enunciado, seção 3.2)

1. Série semanal: usuários elegíveis que chegaram em cada semana (segunda a domingo,
   horário de Brasília) e quantos voltaram em 7 dias (BDR-003), com IC de Wilson.
2. Escolha da semana, com regra fixada antes de rodar [PREMISSA]:
     - só semanas com pelo menos 40 elegíveis (abaixo disso o IC passa de +-13 pp)
     - comparação: a semana contra as 4 semanas anteriores (com usuários) somadas
     - escolhida: a maior diferença absoluta entre as semanas cujo IC (Newcombe) não
       inclui zero; se nenhuma excluir zero, a maior diferença, avisando que está
       dentro do ruído
     - com dezenas de semanas testadas, cerca de 5% delas sairiam do IC por acaso;
       o relatório mostra quantas saíram, para comparar
3. Decomposição de Kitagawa (1955, JASA 50:1168-1194): a diferença de taxa entre a
   semana e as 4 anteriores é a soma de
     - perfil (composição): mudou a proporção de cada tipo de usuário
     - taxa: mudou o retorno dentro de cada tipo
   feita uma vez para cada característica de chegada: modelo, 1ª mensagem (com ou
   sem pedido), idioma, sistema (celular ou computador), período do dia.
   IC 95% de cada parte por bootstrap (reamostra usuários dentro de cada período).

Uso:
    python scripts/10_semana_atipica.py
    python scripts/10_semana_atipica.py --inicio 2023-07-17 --fim 2023-08-07
        [EXPLORATÓRIO] decompõe um período escolhido (semanas de início a fim, inclusive)
        contra todas as outras semanas. Período escolhido DEPOIS de ver a série: o
        resultado é exploratório e é marcado assim no relatório.

Entradas: as do script 07 (a carga vem do próprio 07)
Saídas:   relatorios/10_semana_atipica.txt, data/gold/serie_semanal.csv
"""
import argparse
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

_spec = importlib.util.spec_from_file_location("efeitos07", Path(__file__).with_name("07_efeitos.py"))
e07 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(e07)

RELATORIO = Path("relatorios/10_semana_atipica.txt")
RELATORIO_EXP = Path("relatorios/10_periodo_exploratorio.txt")
SERIE = Path("data/gold/serie_semanal.csv")
MIN_SEMANA = 40
N_ANTERIORES = 4
N_BOOT = 1000
SEMENTE = 42
MOVEIS = {"Android", "iOS"}


def kitagawa(seg_a: pd.Series, y_a: pd.Series, seg_b: pd.Series, y_b: pd.Series) -> tuple[float, float, float]:
    """Diferença (A - B) = perfil + taxa. Segmento ausente num período herda a taxa do outro."""
    niveis = sorted(set(seg_a) | set(seg_b))
    perfil = taxa = 0.0
    for s in niveis:
        ma, mb = seg_a == s, seg_b == s
        wa, wb = ma.mean(), mb.mean()
        ra = y_a[ma].mean() if ma.any() else None
        rb = y_b[mb].mean() if mb.any() else None
        ra = rb if ra is None else ra
        rb = ra if rb is None else rb
        perfil += (wa - wb) * (ra + rb) / 2
        taxa += (ra - rb) * (wa + wb) / 2
    return y_a.mean() - y_b.mean(), perfil, taxa


def decompor(A: pd.DataFrame, B: pd.DataFrame, SEGMENTOS: dict, y_col: str, escrever) -> None:
    rng = np.random.default_rng(SEMENTE)
    idx_a, idx_b = np.arange(len(A)), np.arange(len(B))
    escrever("característica | diferença total pp | parte do perfil pp [IC95] | parte da taxa pp [IC95]")
    for col, rotulo in SEGMENTOS.items():
        tot, perf, tx = kitagawa(A[col].reset_index(drop=True), A[y_col].reset_index(drop=True),
                                 B[col].reset_index(drop=True), B[y_col].reset_index(drop=True))
        bp, bt = [], []
        for _ in range(N_BOOT):
            a = A.iloc[rng.choice(idx_a, len(idx_a))].reset_index(drop=True)
            b = B.iloc[rng.choice(idx_b, len(idx_b))].reset_index(drop=True)
            _, p_, t_ = kitagawa(a[col], a[y_col], b[col], b[y_col])
            bp.append(p_)
            bt.append(t_)
        pl, ph = np.percentile(bp, [2.5, 97.5])
        tl, th = np.percentile(bt, [2.5, 97.5])
        escrever(f"{rotulo} | {tot * 100:+.1f} | {perf * 100:+.1f} [{pl * 100:+.1f}; {ph * 100:+.1f}] | "
                 f"{tx * 100:+.1f} [{tl * 100:+.1f}; {th * 100:+.1f}]")

    escrever("\n== Perfil de quem chegou (% de cada nível) e retorno por nível")
    escrever("característica | nível | % no alvo | % na comparação | retorno no alvo | retorno na comparação")
    for col, rotulo in SEGMENTOS.items():
        for nivel in sorted(set(A[col]) | set(B[col])):
            a, b = A[A[col] == nivel], B[B[col] == nivel]
            ra = f"{a[y_col].mean():.1%} (n={len(a)})" if len(a) else "—"
            rb = f"{b[y_col].mean():.1%} (n={len(b)})" if len(b) else "—"
            escrever(f"{rotulo} | {nivel} | {len(a) / len(A):.1%} | {len(b) / len(B):.1%} | {ra} | {rb}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inicio")
    ap.add_argument("--fim")
    args = ap.parse_args()
    exploratorio = bool(args.inicio and args.fim)

    RELATORIO.parent.mkdir(parents=True, exist_ok=True)
    out = (RELATORIO_EXP if exploratorio else RELATORIO).open("w", encoding="utf-8")

    def escrever(s: str = "") -> None:
        print(s)
        out.write(s + "\n")

    y_col = e07.DESFECHO
    df = e07.carregar()
    df = df[df[y_col].notna()].copy()
    df[y_col] = df[y_col].astype(int)
    df["sistema"] = np.where(df["usuario"].str.split("|").str[1].isin(MOVEIS), "celular", "computador/outro")
    df["pedido"] = np.where(df["primeira_mensagem"].str.startswith("sem pedido"), "sem pedido", "com pedido")
    SEGMENTOS = {
        "modelo": "Modelo",
        "pedido": "1ª mensagem com ou sem pedido",
        "idioma": "Idioma (rótulo da base)",
        "sistema": "Sistema (celular ou computador)",
        "periodo_dia": "Período do dia",
    }

    if exploratorio:
        A = df[(df["semana"] >= args.inicio) & (df["semana"] <= args.fim)]
        B = df[(df["semana"] < args.inicio) | (df["semana"] > args.fim)]
        escrever(f"[EXPLORATÓRIO] período escolhido depois de ver a série: {args.inicio} a {args.fim}")
        kA, nA, kB, nB = int(A[y_col].sum()), len(A), int(B[y_col].sum()), len(B)
        d, lo, hi = e07.newcombe(kA, nA, kB, nB)
        escrever(f"período: {nA} usuários, {kA / nA:.1%} | resto da base: {nB} usuários, {kB / nB:.1%} | "
                 f"diferença {d * 100:+.1f} pp [{lo * 100:+.1f}; {hi * 100:+.1f}]")
        escrever(f"\n== Decomposição: período vs resto da base")
        decompor(A, B, SEGMENTOS, y_col, escrever)
        escrever("\nResultado exploratório: o período foi escolhido olhando os dados; serve para levantar "
                 "hipótese, não para confirmar.")
        out.close()
        print(f"\nRelatório: {RELATORIO_EXP}")
        return

    # ------------------------------------------------------------ série semanal
    g = df.groupby("semana")[y_col].agg(["count", "sum"]).rename(columns={"count": "novos", "sum": "voltaram"})
    g = g.sort_index()
    g["taxa"] = g["voltaram"] / g["novos"]
    ic = [e07.wilson(int(k), int(n)) for k, n in zip(g["voltaram"], g["novos"])]
    g["ic_baixo"], g["ic_alto"] = [a for a, _ in ic], [b for _, b in ic]

    semanas = list(g.index)
    comp = []
    for i, s in enumerate(semanas):
        ant = semanas[max(0, i - N_ANTERIORES):i]
        if len(ant) < N_ANTERIORES or g.loc[s, "novos"] < MIN_SEMANA:
            comp.append((np.nan, np.nan, np.nan, np.nan))
            continue
        k0, n0 = int(g.loc[ant, "voltaram"].sum()), int(g.loc[ant, "novos"].sum())
        d, lo, hi = e07.newcombe(int(g.loc[s, "voltaram"]), int(g.loc[s, "novos"]), k0, n0)
        comp.append((k0 / n0, d, lo, hi))
    g["taxa_4_anteriores"], g["diferenca"], g["dif_ic_baixo"], g["dif_ic_alto"] = zip(*comp)
    g.to_csv(SERIE, sep=";", encoding="utf-8-sig")

    escrever(f"Desfecho: {y_col} | {len(df)} elegíveis em {len(g)} semanas (segunda a domingo, Brasília)")
    escrever(f"Semanas com >= {MIN_SEMANA} elegíveis e 4 anteriores: {int(g['diferenca'].notna().sum())}")
    escrever("\n== Série semanal")
    escrever("semana | novos | voltaram | taxa [IC95] | 4 anteriores | diferença pp [IC95]")
    for s, r in g.iterrows():
        dif = "" if pd.isna(r["diferenca"]) else (
            f"{r['taxa_4_anteriores']:.1%} | {r['diferenca'] * 100:+.1f} "
            f"[{r['dif_ic_baixo'] * 100:+.1f}; {r['dif_ic_alto'] * 100:+.1f}]")
        escrever(f"{s} | {int(r['novos'])} | {int(r['voltaram'])} | {r['taxa']:.1%} "
                 f"[{r['ic_baixo']:.1%}; {r['ic_alto']:.1%}] | {dif}")

    cand = g[g["diferenca"].notna()].copy()
    cand["fora"] = (cand["dif_ic_baixo"] > 0) | (cand["dif_ic_alto"] < 0)
    n_fora, n_test = int(cand["fora"].sum()), len(cand)
    escrever(f"\nSemanas cujo IC da diferença exclui zero: {n_fora} de {n_test} "
             f"(por acaso, esperado ~{0.05 * n_test:.1f})")
    if n_fora:
        alvo = cand[cand["fora"]]["diferenca"].abs().idxmax()
        escrever(f"Escolhida pela regra: {alvo} (maior diferença entre as que excluem zero)")
    else:
        alvo = cand["diferenca"].abs().idxmax()
        escrever(f"Nenhuma semana exclui zero. Escolhida a maior diferença: {alvo} (DENTRO DO RUÍDO)")

    i = semanas.index(alvo)
    ant = semanas[i - N_ANTERIORES:i]
    A = df[df["semana"] == alvo]
    B = df[df["semana"].isin(ant)]
    escrever(f"\n== Decomposição: semana {alvo} ({len(A)} usuários, {A[y_col].mean():.1%}) vs "
             f"{ant[0]} a {ant[-1]} ({len(B)} usuários, {B[y_col].mean():.1%})")

    decompor(A, B, SEGMENTOS, y_col, escrever)

    escrever("\nLeitura: 'perfil' = quanto da diferença viria só da mudança de mix, com as taxas de cada "
             "tipo paradas; 'taxa' = quanto viria da mudança dentro de cada tipo. Cada linha olha uma "
             "característica por vez; as partes de linhas diferentes não se somam.")
    out.close()
    print(f"\nRelatório: {RELATORIO}\nSérie: {SERIE}")


if __name__ == "__main__":
    main()