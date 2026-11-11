import { useState } from "react";
import type { Efeito } from "../api";
import { intervaloPp, inteiro, pct, pp } from "../formato";

// Gráfico de pontos com intervalo (forest plot) desenhado em SVG: um efeito por linha,
// todos na mesma escala em pontos percentuais, com a linha do zero como referência.
// Azul cheio = o intervalo não cruza o zero (o efeito se sustenta); cinza vazado = cruza (pode ser acaso).

const AZUL = "#2a78d6";
const CINZA = "#8a8985";
const ALTURA_LINHA = 52;
const ESQ = 300;   // área dos rótulos
const MEIO = 360;  // área do gráfico
const DIR = 200;   // área dos números
const LARGURA = ESQ + MEIO + DIR;

export function GraficoEfeitos({ efeitos, titulo }: { efeitos: Efeito[]; titulo: string }) {
  const [ativo, setAtivo] = useState<number | null>(null);
  const comIntervalo = efeitos.filter((e) => e.ajustado != null);
  if (!comIntervalo.length) return null;

  const minimo = Math.min(-0.05, ...comIntervalo.map((e) => e.ajustado_ic_baixo ?? 0));
  const maximo = Math.max(0.05, ...comIntervalo.map((e) => e.ajustado_ic_alto ?? 0));
  const passo = 0.05;
  const de = Math.floor(minimo / passo) * passo;
  const ate = Math.ceil(maximo / passo) * passo;
  const x = (v: number) => ESQ + ((v - de) / (ate - de)) * MEIO;
  const marcas: number[] = [];
  for (let v = de; v <= ate + 1e-9; v += passo) marcas.push(Math.round(v * 100) / 100);

  const topo = 28;
  const altura = topo + comIntervalo.length * ALTURA_LINHA + 8;
  const detalhe = ativo != null ? comIntervalo[ativo] : null;

  return (
    <figure className="grafico-efeitos">
      <figcaption className="sr-only">{titulo}</figcaption>
      <svg viewBox={`0 0 ${LARGURA} ${altura}`} role="img" aria-label={titulo} width="100%">
        {marcas.map((m) => (
          <g key={m}>
            <line x1={x(m)} x2={x(m)} y1={topo - 6} y2={altura - 8}
              stroke={m === 0 ? "#52514e" : "#e4e3df"} strokeWidth={m === 0 ? 1.5 : 1} />
            <text x={x(m)} y={topo - 12} textAnchor="middle" className="eixo">
              {m === 0 ? "0" : `${m > 0 ? "+" : "−"}${Math.abs(Math.round(m * 100))}`}
            </text>
          </g>
        ))}
        <text x={8} y={topo - 12} className="eixo">efeito, em pontos percentuais, contra a referência</text>

        {comIntervalo.map((e, i) => {
          const y = topo + i * ALTURA_LINHA + ALTURA_LINHA / 2;
          const sustenta = e.ic_exclui_zero === true;
          const cor = sustenta ? AZUL : CINZA;
          return (
            <g key={`${e.analise}-${e.fator}-${e.nivel}`} className="linha-efeito"
              tabIndex={0} role="button" aria-label={`${e.rotulo_fator}: ${e.rotulo_nivel}, ${pp(e.ajustado)}`}
              onMouseEnter={() => setAtivo(i)} onFocus={() => setAtivo(i)}
              onMouseLeave={() => setAtivo(null)} onBlur={() => setAtivo(null)}>
              <rect x={0} y={y - ALTURA_LINHA / 2} width={LARGURA} height={ALTURA_LINHA}
                className={ativo === i ? "faixa-ativa" : "faixa"} />
              <text x={8} y={y - 10} className="rotulo-fator">{e.rotulo_fator}</text>
              <text x={8} y={y + 5} className="rotulo-nivel">{e.rotulo_nivel}</text>
              <text x={8} y={y + 19} className="rotulo-ref">
                vs {e.rotulo_referencia} · {inteiro(e.usuarios)} pessoas
              </text>
              <line x1={x(e.ajustado_ic_baixo!)} x2={x(e.ajustado_ic_alto!)} y1={y} y2={y}
                stroke={cor} strokeWidth={2} strokeLinecap="round" />
              <circle cx={x(e.ajustado!)} cy={y} r={5} fill={sustenta ? cor : "#fcfcfb"}
                stroke={sustenta ? "#fcfcfb" : cor} strokeWidth={2} />
              <text x={ESQ + MEIO + 8} y={y - 3} className="valor">{pp(e.ajustado)}</text>
              <text x={ESQ + MEIO + 8} y={y + 12} className="rotulo-ref">
                {intervaloPp(e.ajustado_ic_baixo, e.ajustado_ic_alto)}{e.aviso ? " · poucos casos" : ""}
              </text>
            </g>
          );
        })}
      </svg>

      <div className="detalhe-efeito" aria-live="polite">
        {detalhe ? (
          <>
            <strong>{detalhe.rotulo_fator}: {detalhe.rotulo_nivel}</strong>
            <div>
              Voltaram {pct(detalhe.taxa)} ({inteiro(detalhe.voltaram)} de {inteiro(detalhe.usuarios)}), contra{" "}
              {pct(detalhe.taxa_referencia)} em "{detalhe.rotulo_referencia}".
            </div>
            <div>
              Diferença simples: {pp(detalhe.bruto)} {intervaloPp(detalhe.bruto_ic_baixo, detalhe.bruto_ic_alto)} ·
              comparando pessoas parecidas: <strong>{pp(detalhe.ajustado)}</strong>{" "}
              {intervaloPp(detalhe.ajustado_ic_baixo, detalhe.ajustado_ic_alto)}
            </div>
            <div>
              {detalhe.ic_exclui_zero
                ? "O intervalo não cruza o zero: a diferença se sustenta."
                : "O intervalo cruza o zero: a diferença pode ser acaso."}
              {detalhe.aviso && <span className="aviso"> Atenção: {detalhe.aviso}.</span>}
            </div>
            <div className="fonte">Método: {detalhe.metodo}. Fonte: {detalhe.fonte}</div>
          </>
        ) : (
          <span className="fonte">Passe o mouse (ou navegue com Tab) por uma linha para ver os números e a fonte.</span>
        )}
      </div>
    </figure>
  );
}
