import { useEffect, useState } from "react";
import { api, type Definicoes, type Saude } from "./api";
import { data } from "./formato";
import { OQueFazVoltar } from "./telas/OQueFazVoltar";
import { Retencao } from "./telas/Retencao";

type Tela = "retencao" | "efeitos";

export default function App() {
  const [tela, setTela] = useState<Tela>("retencao");
  const [defs, setDefs] = useState<Definicoes | null>(null);
  const [periodo, setPeriodo] = useState<{ inicio: string; fim: string } | null>(null);
  const [saude, setSaude] = useState<Saude | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.definicoes(), api.periodo(), api.saude()])
      .then(([d, p, s]) => { setDefs(d); setPeriodo(p); setSaude(s); })
      .catch((e: Error) => setErro(e.message));
  }, []);

  return (
    <div className="pagina">
      <header className="topo">
        <div>
          <h1>Retenção do assistente de inteligência artificial — Brasil</h1>
          <p className="subtitulo-topo">Quem experimenta o assistente volta em até 7 dias? O que faz voltar?</p>
        </div>
        <nav className="abas" aria-label="Telas">
          <button type="button" className={tela === "retencao" ? "ativo" : ""} aria-current={tela === "retencao"}
            onClick={() => setTela("retencao")}>Retenção</button>
          <button type="button" className={tela === "efeitos" ? "ativo" : ""} aria-current={tela === "efeitos"}
            onClick={() => setTela("efeitos")}>O que faz voltar</button>
        </nav>
      </header>

      <main>
        {erro && <p className="erro" role="alert">Não foi possível carregar os dados do backend: {erro}</p>}
        {!erro && (!defs || !periodo) && <p className="carregando">Carregando…</p>}
        {defs && periodo && tela === "retencao" && <Retencao defs={defs} periodo={periodo} />}
        {defs && tela === "efeitos" && <OQueFazVoltar defs={defs} />}
      </main>

      <footer className="rodape">
        <p>
          Fonte: WildChat-1M (Allen Institute for AI, licença ODC-BY), só conversas com país = Brasil.
          Datas no horário de Brasília. {saude && <>Dados carregados em {data(saude.carga_fim)}.</>}
        </p>
        <p>
          Este painel mostra só totais de grupos. Nunca mostra texto de conversa, IP (nem anonimizado), navegador ou
          qualquer identificador de pessoa.
        </p>
      </footer>
    </div>
  );
}
