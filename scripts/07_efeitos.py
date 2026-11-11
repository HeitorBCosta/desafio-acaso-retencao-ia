"""
Mede o efeito de cada fator da primeira conversa na chance de voltar em 7 dias.

Cada nível de um fator é comparado com um nível de referência de duas formas. A
diferença simples compara as taxas de retorno dos dois grupos, com intervalo de
Newcombe. A diferença ajustada vem de uma regressão logística com todos os fatores
juntos e o trimestre de chegada como controle, e é o efeito marginal médio, com
intervalo pelo método delta. A tabela sai ordenada pelo tamanho do efeito ajustado, e
o modelo é refeito com outras regras de retorno (1 hora, 24 horas, outro dia) para ver
se a direção se mantém.

Nesta versão, o tipo da primeira mensagem e o tamanho da pergunta viraram um fator só,
porque na versão anterior os dois mediam a mesma coisa. Também entraram recusa
(BDR-005), idioma e código. A recusa principal junta "parcial" e "não atendido"; um
segundo modelo separa os dois. O tema ficou de fora porque a classificação acertou só
67%, abaixo do mínimo de 70% combinado antes (script 08b).

Como rodar:
    python scripts/07_efeitos.py

Lê:   data/gold/base_analise.parquet, docs/rotulos/recusa_resultado.csv
Gera: relatorios/07_efeitos.txt, data/gold/efeitos.csv
"""
import math
import sys
from pathlib import Path

import duckdb
import pandas as pd
import statsmodels.formula.api as smf

sys.stdout.reconfigure(encoding="utf-8")

GOLD = Path("data/gold/base_analise.parquet")
ROTULOS_RECUSA = Path("docs/rotulos/recusa_resultado.csv")
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
    "primeira_mensagem": ("1ª mensagem", "pedido médio (20-194)"),
    "resposta_tamanho": ("Tamanho da 1ª resposta", "média (137-2.086)"),
    "recusa": ("Pedido não atendido como pedido (BDR-005, def. B)", "não"),
    "idioma": ("Idioma (rótulo da base)", "Português"),
    "codigo": ("Código na 1ª conversa", "não"),
}
# Modelo alternativo: troca a recusa binária pelos três níveis.
FATORES_ALT = {**{k: v for k, v in FATORES.items() if k != "recusa"},
               "recusa_nivel": ("Recusa em três níveis (BDR-005)", "sem recusa")}
TODOS = {**FATORES, **FATORES_ALT}
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
    con = duckdb.connect()
    con.execute("SET TimeZone = 'UTC'")
    con.execute(f"""
        CREATE TABLE rot AS
        SELECT conversa_id::VARCHAR AS conversa_id, resultado, motivo
        FROM read_csv('{ROTULOS_RECUSA.as_posix()}', delim=';', header=true, all_varchar=true)
    """)
    dup = con.execute("SELECT count(*) - count(DISTINCT conversa_id) FROM rot").fetchall()[0][0]
    if dup:
        raise SystemExit(f"ERRO: {dup} conversa_id repetidos em {ROTULOS_RECUSA}")
    return con.execute(f"""
        SELECT g.usuario,
               modelo_familia AS modelo,
               CASE WHEN turnos = 1 THEN '1' WHEN turnos = 2 THEN '2'
                    WHEN turnos <= 4 THEN '3-4' ELSE '5+' END AS turnos_faixa,
               CASE WHEN hora_local < 6 THEN 'madrugada (0-5h)'
                    WHEN hora_local < 12 THEN 'manhã (6-11h)'
                    WHEN hora_local < 18 THEN 'tarde (12-17h)'
                    ELSE 'noite (18-23h)' END AS periodo_dia,
               CASE WHEN dia_semana_iso >= 6 THEN 'sim' ELSE 'não' END AS fim_de_semana,
               -- BDR-004: saudação, teste e vazia confirmada/indeterminada = sem pedido;
               -- texto_ausente conta como pedido, mas sem tamanho conhecido: nível próprio.
               CASE WHEN pergunta_saudacao OR pergunta_teste THEN 'sem pedido (saudação, teste ou vazia)'
                    WHEN pergunta_vazia AND pergunta_vazia_tipo <> 'texto_ausente'
                        THEN 'sem pedido (saudação, teste ou vazia)'
                    WHEN pergunta_vazia THEN 'pedido com texto ausente'
                    WHEN pergunta_chars < 20 THEN 'pedido curto (<20)'
                    WHEN pergunta_chars <= 194 THEN 'pedido médio (20-194)'
                    ELSE 'pedido longo (>194)' END AS primeira_mensagem,
               CASE WHEN resposta_chars < 137 THEN 'curta (<137)'
                    WHEN resposta_chars <= 2086 THEN 'média (137-2.086)'
                    ELSE 'longa (>2.086)' END AS resposta_tamanho,
               -- BDR-005: rótulos lidos; quem não está nos rótulos conta como sem recusa
               -- (resíduo medido: 0 em 93 na amostra aleatória, limite superior 4,0%).
               CASE WHEN r.resultado IN ('parcial', 'nao_atendido') THEN 'sim' ELSE 'não' END AS recusa,
               CASE r.resultado WHEN 'parcial' THEN 'parcial'
                                WHEN 'nao_atendido' THEN 'não atendido'
                                ELSE 'sem recusa' END AS recusa_nivel,
               CASE WHEN r.resultado IN ('parcial', 'nao_atendido') THEN r.motivo END AS recusa_motivo,
               CASE idioma_grupo WHEN 'Português' THEN 'Português' WHEN 'Inglês' THEN 'Inglês'
                    ELSE 'outro rótulo' END AS idioma,
               CASE WHEN tem_codigo THEN 'sim' ELSE 'não' END AS codigo,
               strftime(timezone('America/Sao_Paulo', t_inicio_utc), '%Y') || '-T' ||
                   CAST(quarter(timezone('America/Sao_Paulo', t_inicio_utc)) AS VARCHAR) AS trimestre,
               strftime(date_trunc('week', timezone('America/Sao_Paulo', t_inicio_utc)), '%Y-%m-%d') AS semana,
               strftime(timezone('America/Sao_Paulo', t_inicio_utc), '%Y-%m-%d') AS data_chegada,
               {DESFECHO}, {", ".join(SENSIBILIDADE)}
        FROM read_parquet('{GOLD.as_posix()}') g
        LEFT JOIN rot r ON g.conversa_id::VARCHAR = r.conversa_id
    """).df()


def formula(y: str, fatores: dict) -> str:
    termos = [f'C({f}, Treatment("{ref}"))' for f, (_, ref) in fatores.items()]
    termos += [f"C({c})" for c in CONTROLES]
    return f"{y} ~ " + " + ".join(termos)


def efeitos_ajustados(df: pd.DataFrame, y: str, fatores: dict = FATORES) -> pd.DataFrame:
    d = df[df[y].notna()].copy()
    d[y] = d[y].astype(int)
    modelo = smf.logit(formula(y, fatores), data=d).fit(disp=False)
    me = modelo.get_margeff(at="overall", dummy=True).summary_frame()
    # Colunas por posição: dy/dx, erro padrão, z, p, IC baixo, IC alto.
    linhas = []
    for nome, r in me.iterrows():
        for f in fatores:
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
    escrever("  BDR-004 1ª mensagem: saudação/teste/vazia = sem pedido; texto_ausente = pedido, nível próprio")
    escrever("  BDR-005 recusa: rótulos lidos (256); fora dos rótulos = sem recusa; principal = def. (B)")
    escrever("  idioma: rótulo da base; 'outro rótulo' acertou só 9 de 100 na leitura (maioria PT/EN curtos ou vazios)")
    escrever("  código: marcador ``` na pergunta ou na resposta (99 de 100 técnicas na leitura)")
    escrever("  faixas de tamanho pelos p25/p75 do script 04; controle: trimestre de chegada (Brasília)")
    escrever("  IC 95%: Newcombe (bruto) e método delta (ajustado); usuários supostos independentes")
    escrever("  fora do modelo: tema (classificação com 67% de acerto, abaixo do limite de 70%)")
    escrever(f"\n[MEDIDO] Base: {n} usuários elegíveis, {k} voltaram, taxa {k / n:.1%} (IC95 {lo:.1%} a {hi:.1%})")

    # ------------------------------------------------------------ bruto
    brutos = []
    for f, (rotulo, ref) in TODOS.items():
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

    alt, modelo_alt = efeitos_ajustados(df, DESFECHO, FATORES_ALT)
    alt = alt[alt["fator"] == "recusa_nivel"]
    escrever(f"[MEDIDO] Modelo alternativo (recusa em 3 níveis): pseudo-R² {modelo_alt.prsquared:.3f}")
    ajust = pd.concat([ajust, alt], ignore_index=True)

    tab = brutos.merge(ajust, on=["fator", "nivel"], how="left")
    for y in SENSIBILIDADE:
        s, _ = efeitos_ajustados(df, y)
        s_alt, _ = efeitos_ajustados(df, y, FATORES_ALT)
        s = pd.concat([s, s_alt[s_alt["fator"] == "recusa_nivel"]], ignore_index=True)
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
        marca = " (referência)" if r["nivel"] == TODOS[r["fator"]][1] else ""
        escrever(f"{TODOS[r['fator']][0]} | {r['nivel']}{marca} | {r['usuarios']} | {r['voltaram']} | {r['taxa']:.1%}")

    escrever("\n== Efeitos, ordenados pelo tamanho do efeito ajustado (pontos percentuais vs referência)")
    escrever("fator | nivel | usuarios | bruto [IC95] | ajustado [IC95] | IC exclui 0 | "
             "mesma direção em 1h/24h/outro dia | base pequena")
    ordem = tab[tab["efeito"].notna()].reindex(
        tab[tab["efeito"].notna()]["efeito"].abs().sort_values(ascending=False).index)
    for _, r in ordem.iterrows():
        escrever(f"{TODOS[r['fator']][0]} | {r['nivel']} | {r['usuarios']} | "
                 f"{pp(r['bruto'])} [{pp(r['bruto_ic_baixo'])}; {pp(r['bruto_ic_alto'])}] | "
                 f"{pp(r['efeito'])} [{pp(r['ic_baixo'])}; {pp(r['ic_alto'])}] | "
                 f"{'sim' if r['ic_exclui_zero'] else 'não'} | {r['direcao_mantida_nas_outras_regras']} | "
                 f"{'sim' if r['base_pequena'] else ''}")

    escrever("\nRecusa em três níveis vem do modelo alternativo (mesmos fatores, recusa trocada).")
    escrever("\nLeitura: 'ajustado' compara usuários com os mesmos valores nos outros fatores e no "
             "trimestre de chegada. Não prova causa: fatores não medidos (ex.: intenção de uso) "
             "continuam podendo explicar parte do efeito.")
    out.close()
    print(f"\nRelatório: {RELATORIO}\nTabela: {EFEITOS}")


if __name__ == "__main__":
    main()
