// Tipos e chamadas da API. Os nomes dos campos são os mesmos dos endpoints (api/app/main.py).

export type Definicao = { titulo: string; texto: string; fonte: string };
export type Definicoes = {
  definicoes: Record<string, Definicao>;
  fatores: Record<string, string>;
  min_coorte: number;
};

export type VisaoGeral = {
  inicio: string;
  fim: string;
  novos: number;
  voltaram: number;
  taxa: number | null;
  ic_baixo: number | null;
  ic_alto: number | null;
  base_pequena: boolean;
  data_da_carga: string;
};

export type Coorte = {
  periodo: string;
  novos: number;
  voltaram: number;
  taxa: number;
  ic_baixo: number | null;
  ic_alto: number | null;
  base_pequena: boolean;
};

export type Efeito = {
  analise: "principal" | "recusa_por_motivo" | "gpt4_selecao";
  fator: string;
  rotulo_fator: string;
  nivel: string;
  rotulo_nivel: string;
  rotulo_referencia: string;
  referencia: string;
  usuarios: number;
  voltaram: number;
  taxa: number;
  taxa_referencia: number;
  bruto: number | null;
  bruto_ic_baixo: number | null;
  bruto_ic_alto: number | null;
  ajustado: number | null;
  ajustado_ic_baixo: number | null;
  ajustado_ic_alto: number | null;
  ic_exclui_zero: boolean | null;
  metodo: string;
  aviso: string | null;
  fonte: string;
};

export type Granularidade = "semana" | "mes";

async function obter<T>(caminho: string, params: Record<string, string> = {}): Promise<T> {
  const qs = new URLSearchParams(params).toString();
  const resposta = await fetch(`/api/${caminho}${qs ? `?${qs}` : ""}`);
  if (!resposta.ok) {
    const corpo = await resposta.json().catch(() => ({}));
    throw new Error(corpo.detail ?? `Erro ${resposta.status} em /api/${caminho}`);
  }
  return resposta.json() as Promise<T>;
}

export type Saude = { status: string; carga_id: string; carga_fim: string; versao_codigo: string };

export const api = {
  saude: () => obter<Saude>("saude"),
  definicoes: () => obter<Definicoes>("definicoes"),
  periodo: () => obter<{ inicio: string; fim: string }>("periodo"),
  visaoGeral: (inicio: string, fim: string) => obter<VisaoGeral>("visao-geral", { inicio, fim }),
  coortes: (inicio: string, fim: string, granularidade: Granularidade) =>
    obter<{ granularidade: Granularidade; min_coorte: number; coortes: Coorte[] }>(
      "retencao/coortes", { inicio, fim, granularidade }),
  efeitos: () => obter<{ efeitos: Efeito[] }>("efeitos"),
  diasSemDados: (inicio: string, fim: string) =>
    obter<{ dias: string[] }>("qualidade/dias-sem-dados", { inicio, fim }),
};
