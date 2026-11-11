"""
Recusa separada por motivo: o efeito da recusa no retorno é do produto ou de quem pede?

Pergunta: no script 07, ter o pedido não atendido (BDR-005, definição B) reduz o
retorno em 11,7 pp. Isso pode ser seleção: quem pede algo proibido (keygen,
instrução perigosa) talvez voltasse menos de qualquer jeito.

Teste, com a leitura FIXADA ANTES de rodar [PREMISSA]:
    - "limitação do produto" = motivo capacidade ou conhecimento (data de corte, previsão):
      o usuário pediu algo legítimo e o produto não entregou
    - "política de conteúdo" = o produto recusou por regra de uso
    - se a limitação do produto também reduz o retorno (IC ajustado abaixo de zero),
      a leitura "o produto contribui" fica mais forte
    - se só a política reduz, seleção é a explicação mais simples
    - se os ICs forem largos demais para separar os dois, o resultado é inconclusivo
      e é reportado assim
Motivo "desconhecido" (poucos casos) aparece só no bruto e sai do modelo.

O modelo é o mesmo do script 07 (mesmos fatores e controle), com a recusa
trocada pelo motivo. Funções e carga vêm do próprio script 07, para não divergir.

Uso:
    python scripts/07b_recusa_motivo.py

Entradas: as do script 07
Saídas:   relatorios/07b_recusa_motivo.txt, data/gold/efeitos_recusa_motivo.csv
"""
import importlib.util
import sys
from pathlib import Path

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

_spec = importlib.util.spec_from_file_location("efeitos07", Path(__file__).with_name("07_efeitos.py"))
e07 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(e07)

RELATORIO = Path("relatorios/07b_recusa_motivo.txt")
TABELA = Path("data/gold/efeitos_recusa_motivo.csv")   # lida pela carga do dashboard
REF = "sem recusa"
GRUPOS = {
    "capacidade": "limitação do produto",
    "conhecimento": "limitação do produto",
    "politica": "política de conteúdo",
    "desconhecido": "desconhecido",
}
FATORES_MOTIVO = {**{k: v for k, v in e07.FATORES.items() if k != "recusa"},
                  "recusa_grupo": ("Recusa por motivo", REF)}


def main() -> None:
    RELATORIO.parent.mkdir(parents=True, exist_ok=True)
    out = RELATORIO.open("w", encoding="utf-8")

    def escrever(t: str = "") -> None:
        print(t)
        out.write(t + "\n")

    y = e07.DESFECHO
    todos = e07.carregar()
    todos["recusa_motivo"] = todos["recusa_motivo"].where(todos["recusa"] == "sim")
    todos["recusa_grupo"] = todos["recusa_motivo"].map(GRUPOS).fillna(REF)
    df = todos[todos[y].notna()].copy()
    df[y] = df[y].astype(int)
    sem_motivo = int(((df["recusa"] == "sim") & df["recusa_motivo"].isna()).sum())
    if sem_motivo:
        escrever(f"ATENÇÃO: {sem_motivo} recusas sem motivo nos rótulos")

    k_ref = int(df.loc[df["recusa_grupo"] == REF, y].sum())
    n_ref = int((df["recusa_grupo"] == REF).sum())

    escrever(f"Desfecho: {y} | base: {len(df)} usuários elegíveis")
    escrever(f"Recusas (def. B): {int((df['recusa'] == 'sim').sum())}")
    escrever("Leitura fixada antes de rodar: ver cabeçalho do script.\n")

    escrever("== Bruto por motivo (taxa de retorno, IC 95% de Wilson; diferença vs sem recusa, IC de Newcombe)")
    escrever("motivo | grupo | usuários | voltaram | taxa [IC95] | diferença pp [IC95]")
    escrever(f"sem recusa | — | {n_ref} | {k_ref} | {k_ref / n_ref:.1%} "
             f"[{e07.wilson(k_ref, n_ref)[0]:.1%}; {e07.wilson(k_ref, n_ref)[1]:.1%}] | referência")
    linhas_bruto = [(m, GRUPOS[m]) for m in ["capacidade", "conhecimento", "politica", "desconhecido"]]
    linhas_bruto += [(None, "limitação do produto"), (None, "política de conteúdo")]
    for motivo, grupo in linhas_bruto:
        sel = df["recusa_motivo"] == motivo if motivo else df["recusa_grupo"] == grupo
        n, k = int(sel.sum()), int(df.loc[sel, y].sum())
        if n == 0:
            escrever(f"{motivo or '(total do grupo)'} | {grupo} | 0 | — | — | —")
            continue
        lo, hi = e07.wilson(k, n)
        d, dl, dh = e07.newcombe(k, n, k_ref, n_ref)
        escrever(f"{motivo or '(total do grupo)'} | {grupo} | {n} | {k} | {k / n:.1%} [{lo:.1%}; {hi:.1%}] | "
                 f"{d * 100:+.1f} [{dl * 100:+.1f}; {dh * 100:+.1f}]")

    # Modelo ajustado: tira os poucos de motivo desconhecido.
    d_mod = df[df["recusa_grupo"] != "desconhecido"].copy()
    todos_mod = todos[todos["recusa_grupo"] != "desconhecido"].copy()   # como no script 07
    escrever(f"\n== Ajustado (mesmo modelo do script 07, recusa trocada pelo grupo de motivo)")
    escrever(f"Fora do modelo: {len(df) - len(d_mod)} usuário(s) com motivo desconhecido")
    resultados = {}
    for desfecho in [y] + e07.SENSIBILIDADE:
        tab, modelo = e07.efeitos_ajustados(todos_mod, desfecho, FATORES_MOTIVO)
        tab = tab[tab["fator"] == "recusa_grupo"].set_index("nivel")
        resultados[desfecho] = tab
        if desfecho == y:
            escrever(f"[MEDIDO] {int(modelo.nobs)} usuários, pseudo-R² {modelo.prsquared:.3f}")

    escrever("grupo | usuários | voltaram | ajustado pp [IC95] | IC exclui 0 | sinal em 1h / 24h / outro dia")
    linhas_csv = []
    for grupo in ["limitação do produto", "política de conteúdo"]:
        n = int((d_mod["recusa_grupo"] == grupo).sum())
        k = int(d_mod.loc[d_mod["recusa_grupo"] == grupo, y].sum())
        r = resultados[y].loc[grupo]
        sinais = " / ".join(f"{resultados[s].loc[grupo, 'efeito'] * 100:+.1f}" for s in e07.SENSIBILIDADE)
        exclui = "sim" if (r["ic_baixo"] > 0 or r["ic_alto"] < 0) else "não"
        aviso = "  (poucos retornos: IC pouco confiável)" if k < 10 else ""
        bd, bl, bh = e07.newcombe(k, n, k_ref, n_ref)
        linhas_csv.append({"fator": "recusa_motivo", "nivel": grupo, "referencia": REF, "usuarios": n,
                           "voltaram": k, "taxa": k / n, "taxa_referencia": k_ref / n_ref,
                           "bruto": bd, "bruto_ic_baixo": bl, "bruto_ic_alto": bh,
                           "efeito": r["efeito"], "ic_baixo": r["ic_baixo"], "ic_alto": r["ic_alto"],
                           "poucos_retornos": k < 10})
        escrever(f"{grupo} | {n} | {k} | {r['efeito'] * 100:+.1f} [{r['ic_baixo'] * 100:+.1f}; "
                 f"{r['ic_alto'] * 100:+.1f}] | {exclui} | {sinais}{aviso}")

    pd.DataFrame(linhas_csv).to_csv(TABELA, index=False, sep=";", encoding="utf-8-sig")

    lim = resultados[y].loc["limitação do produto"]
    pol = resultados[y].loc["política de conteúdo"]
    escrever("\n== Aplicação da leitura fixada")
    if lim["ic_alto"] < 0 and pol["ic_alto"] < 0:
        escrever("Os dois grupos reduzem o retorno (IC abaixo de zero): a limitação do produto também pesa;"
                 " seleção sozinha não explica o efeito.")
    elif lim["ic_alto"] < 0:
        escrever("Só a limitação do produto tem IC abaixo de zero: a leitura 'o produto contribui' fica mais forte.")
    elif pol["ic_alto"] < 0:
        escrever("Só a política de conteúdo tem IC abaixo de zero: seleção é a explicação mais simples.")
    else:
        escrever("Nenhum dos dois grupos, sozinho, tem IC abaixo de zero: inconclusivo com esta base.")
    escrever("Limite: motivo foi lido pelo Claude (conferência do Heitor pendente); grupos pequenos.")
    out.close()
    print(f"\nRelatório: {RELATORIO}")


if __name__ == "__main__":
    main()
