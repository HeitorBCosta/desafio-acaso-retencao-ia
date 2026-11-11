// Formatação em português do Brasil. Toda taxa chega da API como fração (0,241 = 24,1%).

const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];

export const pct = (x: number | null | undefined, casas = 1) =>
  x == null ? "—" : `${(x * 100).toFixed(casas).replace(".", ",")}%`;

export const pp = (x: number | null | undefined) =>
  x == null ? "—" : `${x >= 0 ? "+" : "−"}${Math.abs(x * 100).toFixed(1).replace(".", ",")} pp`;

export const intervaloPp = (baixo: number | null, alto: number | null) =>
  baixo == null || alto == null ? "" : `[${pp(baixo).replace(" pp", "")}; ${pp(alto).replace(" pp", "")}]`;

export const intervaloPct = (baixo: number | null, alto: number | null) =>
  baixo == null || alto == null ? "" : `${pct(baixo)} a ${pct(alto)}`;

export const inteiro = (n: number) => n.toLocaleString("pt-BR");

/** "2023-08-14" -> "14/08/2023" */
export const data = (iso: string) => {
  const [a, m, d] = iso.slice(0, 10).split("-");
  return `${d}/${m}/${a}`;
};

/** Rótulo curto do período no eixo: semana "14/08/23", mês "ago/23". */
export const rotuloPeriodo = (iso: string, granularidade: "semana" | "mes") => {
  const [a, m, d] = iso.slice(0, 10).split("-");
  return granularidade === "mes" ? `${MESES[Number(m) - 1]}/${a.slice(2)}` : `${d}/${m}/${a.slice(2)}`;
};

/** Início do período (segunda-feira da semana, ou dia 1 do mês) que contém a data. */
export const inicioDoPeriodo = (iso: string, granularidade: "semana" | "mes") => {
  const [a, m, d] = iso.slice(0, 10).split("-").map(Number);
  if (granularidade === "mes") return `${a}-${String(m).padStart(2, "0")}-01`;
  const dt = new Date(Date.UTC(a, m - 1, d));
  const diaSemana = (dt.getUTCDay() + 6) % 7; // segunda = 0
  dt.setUTCDate(dt.getUTCDate() - diaSemana);
  return dt.toISOString().slice(0, 10);
};
