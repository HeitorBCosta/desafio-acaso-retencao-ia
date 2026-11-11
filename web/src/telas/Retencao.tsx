import { useEffect, useMemo, useState } from "react";
import {
  Area, Bar, BarChart, CartesianGrid, ComposedChart, Line, ReferenceLine,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api, type Coorte, type Definicoes, type Granularidade, type VisaoGeral } from "../api";
import { Ajuda } from "../componentes/Ajuda";
import { Cartao } from "../componentes/Cartao";
import { data, inicioDoPeriodo, inteiro, intervaloPct, pct, rotuloPeriodo } from "../formato";

const AZUL = "#2a78d6";
const FAIXA = "#cde2fb";
const BARRA = "#86b6ef";
const NEUTRO = "#8a8985";

// taxaConfiavel: só períodos com base suficiente (a linha passa por eles);
// taxaPequena: períodos com base pequena (pontos vazados, sem linha ligando).
type Linha = Coorte & { rotulo: string; taxaConfiavel: number | null; taxaPequena: number | null; faixa?: [number, number] };

export function Retencao({ defs, periodo }: { defs: Definicoes; periodo: { inicio: string; fim: string } }) {
  const [inicio, setInicio] = useState(periodo.inicio);
  const [fim, setFim] = useState(periodo.fim);
  const [granularidade, setGranularidade] = useState<Granularidade>("mes");
  const [visao, setVisao] = useState<VisaoGeral | null>(null);
  const [coortes, setCoortes] = useState<Coorte[]>([]);
  const [diasSemDados, setDiasSemDados] = useState<string[]>([]);
  const [tabela, setTabela] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    if (inicio > fim) return;
    setErro(null);
    Promise.all([
      api.visaoGeral(inicio, fim),
      api.coortes(inicio, fim, granularidade),
      api.diasSemDados(inicio, fim),
    ])
      .then(([v, c, d]) => {
        setVisao(v);
        setCoortes(c.coortes);
        setDiasSemDados(d.dias);
      })
      .catch((e: Error) => setErro(e.message));
  }, [inicio, fim, granularidade]);

  const linhas: Linha[] = useMemo(
    () => coortes.map((c) => ({
      ...c,
      rotulo: rotuloPeriodo(c.periodo, granularidade),
      taxaConfiavel: c.base_pequena ? null : c.taxa * 100,
      taxaPequena: c.base_pequena ? c.taxa * 100 : null,
      faixa: c.ic_baixo != null && c.ic_alto != null ? [c.ic_baixo * 100, c.ic_alto * 100] : undefined,
    })),
    [coortes, granularidade],
  );

  // Dias sem coleta marcados no período (semana ou mês) em que caem.
  const periodosSemDados = useMemo(() => {
    const presentes = new Set(linhas.map((l) => l.rotulo));
    const marcados = new Map<string, string[]>();
    for (const dia of diasSemDados) {
      const rotulo = rotuloPeriodo(inicioDoPeriodo(dia, granularidade), granularidade);
      if (presentes.has(rotulo)) marcados.set(rotulo, [...(marcados.get(rotulo) ?? []), dia]);
    }
    return marcados;
  }, [diasSemDados, linhas, granularidade]);

  const pequenas = linhas.filter((l) => l.base_pequena).length;
  const d = defs.definicoes;

  return (
    <section aria-labelledby="titulo-retencao">
      <h2 id="titulo-retencao">Quantas pessoas que experimentaram voltaram em até 7 dias, e isso mudou com o tempo?</h2>

      <div className="filtros" role="group" aria-label="Filtros">
        <div className="alternador" role="radiogroup" aria-label="Agrupar por">
          {(["semana", "mes"] as const).map((g) => (
            <button key={g} type="button" role="radio" aria-checked={granularidade === g}
              className={granularidade === g ? "ativo" : ""} onClick={() => setGranularidade(g)}>
              {g === "semana" ? "Por semana" : "Por mês"}
            </button>
          ))}
        </div>
        <label>Chegada de
          <input type="date" value={inicio} min={periodo.inicio} max={fim} onChange={(e) => setInicio(e.target.value)} />
        </label>
        <label>até
          <input type="date" value={fim} min={inicio} max={periodo.fim} onChange={(e) => setFim(e.target.value)} />
        </label>
        <button type="button" className="link" onClick={() => { setInicio(periodo.inicio); setFim(periodo.fim); }}>
          Período inteiro
        </button>
      </div>

      {erro && <p className="erro" role="alert">Não foi possível carregar os dados: {erro}</p>}

      {visao && (
        <div className="cartoes">
          <Cartao titulo="Novos usuários" valor={inteiro(visao.novos)} definicao={d.novos}
            detalhe={`chegaram de ${data(visao.inicio)} a ${data(visao.fim)}`} />
          <Cartao titulo="Voltaram em até 7 dias" valor={inteiro(visao.voltaram)} definicao={d.voltaram}
            detalhe="começaram uma nova sessão na semana seguinte à 1ª conversa" />
          <Cartao titulo="Taxa de retorno em 7 dias" definicao={d.taxa}
            valor={visao.base_pequena ? "base pequena" : pct(visao.taxa)}
            detalhe={visao.base_pequena
              ? `menos de ${defs.min_coorte} novos usuários no período escolhido`
              : `valor provável entre ${pct(visao.ic_baixo)} e ${pct(visao.ic_alto)} (95% de confiança)`} />
        </div>
      )}

      <div className="painel">
        <div className="painel-cabecalho">
          <h3>Taxa de retorno por {granularidade === "semana" ? "semana" : "mês"} de chegada</h3>
          <button type="button" className="link" onClick={() => setTabela((t) => !t)}>
            {tabela ? "Ver gráfico" : "Ver como tabela"}
          </button>
        </div>

        {tabela ? (
          <TabelaCoortes linhas={linhas} />
        ) : (
          <>
            <ResponsiveContainer width="100%" height={300}>
              <ComposedChart data={linhas} syncId="retencao" margin={{ top: 12, right: 16, bottom: 0, left: 0 }}>
                <CartesianGrid vertical={false} stroke="#e4e3df" />
                <XAxis dataKey="rotulo" tick={{ fontSize: 12 }} interval="preserveStartEnd" minTickGap={24} />
                <YAxis tickFormatter={(v: number) => `${v}%`} tick={{ fontSize: 12 }} width={48}
                  domain={[0, (max: number) => Math.min(100, Math.ceil((max + 5) / 10) * 10)]} />
                <Tooltip content={<DicaCoorte granularidade={granularidade} periodosSemDados={periodosSemDados} />} />
                <Area dataKey="faixa" stroke="none" fill={FAIXA} fillOpacity={0.9} isAnimationActive={false}
                  connectNulls={false} activeDot={false} />
                {[...periodosSemDados.keys()].map((rotulo) => (
                  <ReferenceLine key={rotulo} x={rotulo} stroke={NEUTRO} strokeDasharray="4 3"
                    label={{ value: "sem coleta", position: "insideTopRight", fontSize: 11, fill: "#52514e" }} />
                ))}
                <Line dataKey="taxaConfiavel" stroke={AZUL} strokeWidth={2} isAnimationActive={false}
                  connectNulls={false} dot={PontoTaxa} activeDot={{ r: 6, stroke: "#fcfcfb", strokeWidth: 2 }} />
                <Line dataKey="taxaPequena" stroke="none" isAnimationActive={false} legendType="none"
                  dot={PontoTaxa} activeDot={{ r: 6, fill: "#fcfcfb", stroke: AZUL, strokeWidth: 2 }} />
              </ComposedChart>
            </ResponsiveContainer>

            <h3 className="subtitulo">Novos usuários por {granularidade === "semana" ? "semana" : "mês"} (tamanho de cada ponto acima)</h3>
            <ResponsiveContainer width="100%" height={140}>
              <BarChart data={linhas} syncId="retencao" margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
                <CartesianGrid vertical={false} stroke="#e4e3df" />
                <XAxis dataKey="rotulo" tick={{ fontSize: 12 }} interval="preserveStartEnd" minTickGap={24} />
                <YAxis tick={{ fontSize: 12 }} width={48} allowDecimals={false} />
                <Tooltip content={<DicaCoorte granularidade={granularidade} periodosSemDados={periodosSemDados} />}
                  cursor={{ fill: "#f0efec" }} />
                <ReferenceLine y={defs.min_coorte} stroke={NEUTRO} strokeDasharray="4 3" />
                <Bar dataKey="novos" fill={BARRA} radius={[4, 4, 0, 0]} isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
          </>
        )}

        <ul className="notas">
          <li>
            <span className="legenda-ponto cheio" /> taxa do período, com a faixa de 95% de confiança em azul-claro.
          </li>
          <li>
            <span className="legenda-ponto vazado" /> base pequena: {pequenas} de {linhas.length} períodos têm menos
            de {defs.min_coorte} novos usuários; a taxa aparece solta, sem linha e sem faixa, porque varia demais só
            por acaso. Nas barras, a linha tracejada marca esse mínimo de {defs.min_coorte}.{" "}
            <Ajuda definicao={d.base_pequena} />
          </li>
          {periodosSemDados.size > 0 && (
            <li>
              Linha tracejada: período com dia sem nenhuma conversa registrada; o retorno de quem chegou antes pode
              estar subestimado. <Ajuda definicao={d.dia_sem_dados} />
            </li>
          )}
        </ul>
      </div>
    </section>
  );
}

function PontoTaxa(props: { cx?: number; cy?: number; index?: number; payload?: Linha }) {
  const { cx, cy, index, payload } = props;
  if (cx == null || cy == null || !payload) return <g key={`p-${index}`} />;
  return payload.base_pequena
    ? <circle key={`p-${index}`} cx={cx} cy={cy} r={4} fill="#fcfcfb" stroke={AZUL} strokeWidth={2} />
    : <circle key={`p-${index}`} cx={cx} cy={cy} r={4} fill={AZUL} stroke="#fcfcfb" strokeWidth={2} />;
}

function DicaCoorte({ active, payload, granularidade, periodosSemDados }: {
  active?: boolean;
  payload?: { payload: Linha }[];
  granularidade: Granularidade;
  periodosSemDados: Map<string, string[]>;
}) {
  if (!active || !payload?.length) return null;
  const l = payload[0].payload;
  const semDados = periodosSemDados.get(l.rotulo);
  return (
    <div className="dica">
      <strong>{granularidade === "semana" ? `Semana de ${data(l.periodo)}` : l.rotulo}</strong>
      <div>{inteiro(l.novos)} novos usuários, {inteiro(l.voltaram)} voltaram</div>
      <div>Taxa de retorno: <strong>{pct(l.taxa)}</strong></div>
      {l.base_pequena
        ? <div className="aviso">Base pequena: a taxa pode variar mais de 13 pontos só por acaso.</div>
        : <div>Valor provável: {intervaloPct(l.ic_baixo, l.ic_alto)}</div>}
      {semDados && <div className="aviso">Sem coleta em {semDados.map(data).join(", ")}.</div>}
    </div>
  );
}

function TabelaCoortes({ linhas }: { linhas: Linha[] }) {
  return (
    <div className="tabela-rolagem">
      <table>
        <thead>
          <tr><th>Período</th><th>Novos</th><th>Voltaram</th><th>Taxa</th><th>Faixa de 95%</th><th>Observação</th></tr>
        </thead>
        <tbody>
          {linhas.map((l) => (
            <tr key={l.periodo}>
              <td>{data(l.periodo)}</td>
              <td className="num">{inteiro(l.novos)}</td>
              <td className="num">{inteiro(l.voltaram)}</td>
              <td className="num">{pct(l.taxa)}</td>
              <td>{l.base_pequena ? "—" : intervaloPct(l.ic_baixo, l.ic_alto)}</td>
              <td>{l.base_pequena ? "base pequena" : ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
