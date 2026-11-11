import { useEffect, useState } from "react";
import { api, type Definicoes, type Efeito } from "../api";
import { Ajuda } from "../componentes/Ajuda";
import { GraficoEfeitos } from "../componentes/GraficoEfeitos";
import { intervaloPp, inteiro, pct, pp, sinal } from "../formato";

export function OQueFazVoltar({ defs }: { defs: Definicoes }) {
  const [efeitos, setEfeitos] = useState<Efeito[]>([]);
  const [tabela, setTabela] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    api.efeitos().then((r) => setEfeitos(r.efeitos)).catch((e: Error) => setErro(e.message));
  }, []);

  // A recusa em três níveis repete a recusa principal dividida; aparece só na tabela.
  const principais = efeitos.filter((e) => e.analise === "principal" && e.fator !== "recusa_nivel");
  const checagens = efeitos.filter((e) => e.analise !== "principal");
  const achar = (analise: string, nivel: string) => efeitos.find((e) => e.analise === analise && e.nivel === nivel);

  return (
    <section aria-labelledby="titulo-efeitos">
      <h2 id="titulo-efeitos">O que na primeira conversa muda a chance de voltar, e quanto?</h2>
      {erro && <p className="erro" role="alert">Não foi possível carregar os efeitos: {erro}</p>}

      <Achados
        limitacao={achar("recusa_por_motivo", "limitação do produto")}
        politica={achar("recusa_por_motivo", "política de conteúdo")}
        semPedido={achar("principal", "sem pedido (saudação, teste ou vazia)")}
        gpt4={achar("gpt4_selecao", "GPT-4")}
      />

      <div className="painel">
        <div className="painel-cabecalho">
          <h3>
            Efeito de cada fator no retorno em 7 dias <Ajuda definicao={defs.definicoes.efeito} />
          </h3>
          <button type="button" className="link" onClick={() => setTabela((t) => !t)}>
            {tabela ? "Ver gráfico" : "Ver como tabela"}
          </button>
        </div>
        <p className="explica">
          Cada linha compara um grupo com o grupo de referência, entre pessoas parecidas nos outros fatores e no
          trimestre de chegada. O ponto é o efeito; a barra é a faixa de 95% de confiança.{" "}
          <span className="legenda-ponto cheio" /> a faixa não cruza o zero (se sustenta){" "}
          <span className="legenda-ponto vazado cinza" /> cruza o zero (pode ser acaso).
        </p>
        {tabela ? <TabelaEfeitos efeitos={efeitos} /> : (
          <>
            <GraficoEfeitos efeitos={principais} titulo="Efeito de cada fator no retorno em 7 dias" />
            <h3 className="subtitulo">Duas checagens de causa ou seleção</h3>
            <p className="explica">
              Recusa separada pelo motivo (quem pediu algo proibido voltaria menos de qualquer jeito?) e GPT-4
              comparado só entre grupos equilibrados, nos trimestres em que os dois modelos estavam em uso.
            </p>
            <GraficoEfeitos efeitos={checagens} titulo="Recusa por motivo e GPT-4 entre grupos equilibrados" />
          </>
        )}
        <p className="nota-rodape">
          Mostra associação, não prova causa: o que não foi medido (por exemplo, a intenção de quem chega) pode
          explicar parte de cada efeito. O modelo explica pouco de quem volta: os fatores mudam a chance, mas não
          preveem a pessoa.
        </p>
      </div>
    </section>
  );
}

function Achados({ limitacao, politica, semPedido, gpt4 }: Record<string, Efeito | undefined>) {
  return (
    <div className="achados">
      {limitacao && politica && (
        <article className="achado">
          <h3>1. Quando o assistente não consegue fazer o que foi pedido, a pessoa quase não volta</h3>
          <p>
            Voltaram <strong>{pct(limitacao.taxa)}</strong> de quem teve o pedido recusado por limitação do produto,
            contra {pct(limitacao.taxa_referencia)} de quem não teve recusa: {pp(limitacao.bruto)}{" "}
            {intervaloPp(limitacao.bruto_ic_baixo, limitacao.bruto_ic_alto)}. Recusa por política de conteúdo:{" "}
            {pct(politica.taxa)}, quase igual a quem foi atendido.
          </p>
          <p className="decisao"><strong>Decisão:</strong> quando não puder atender, oferecer o que consegue fazer em
            vez de só recusar, e mapear as capacidades que mais faltam.</p>
          <p className="limite">Grupo pequeno ({inteiro(limitacao.usuarios)} pessoas, {inteiro(limitacao.voltaram)} retornos).</p>
        </article>
      )}
      {semPedido && (
        <article className="achado">
          <h3>2. Quem chega sem pedido (só "oi", "teste" ou mensagem vazia) volta menos</h3>
          <p>
            Voltaram <strong>{pct(semPedido.taxa)}</strong>, contra {pct(semPedido.taxa_referencia)} de quem chega
            com um pedido de tamanho médio. Entre pessoas parecidas: {pp(semPedido.ajustado)}{" "}
            {intervaloPp(semPedido.ajustado_ic_baixo, semPedido.ajustado_ic_alto)}.
          </p>
          <p className="decisao"><strong>Decisão:</strong> primeiro uso guiado: responder ao cumprimento com exemplos
            do que o assistente sabe fazer, e confirmar num experimento com grupos sorteados.</p>
          <p className="limite">Pode ser perfil de quem chega (quem só quer ver o que é); o experimento separa as duas coisas.</p>
        </article>
      )}
      {gpt4 && (
        <article className="achado">
          <h3>3. Oferecer o GPT-4 não aumenta o retorno</h3>
          <p>
            Comparando grupos equilibrados: {pp(gpt4.ajustado)}{" "}
            {intervaloPp(gpt4.ajustado_ic_baixo, gpt4.ajustado_ic_alto)}. A faixa cruza o zero; uma vantagem do
            GPT-4 acima de {pp(gpt4.ajustado_ic_alto).replace("+", "")} é improvável com estes dados.
          </p>
          <p className="decisao"><strong>Decisão:</strong> não usar o modelo mais avançado como estratégia de
            retenção.</p>
          <p className="limite">Não prova ausência de efeito; só os trimestres com os dois modelos em uso.</p>
        </article>
      )}
    </div>
  );
}

function TabelaEfeitos({ efeitos }: { efeitos: Efeito[] }) {
  return (
    <div className="tabela-rolagem">
      <table>
        <thead>
          <tr>
            <th>Fator</th><th>Grupo</th><th>Referência</th><th>Pessoas</th><th>Voltaram</th>
            <th>Diferença simples (pontos percentuais)</th><th>Entre pessoas parecidas (pontos percentuais)</th><th>Se sustenta?</th><th>Fonte</th>
          </tr>
        </thead>
        <tbody>
          {efeitos.map((e) => (
            <tr key={`${e.analise}-${e.fator}-${e.nivel}`}>
              <td>{e.rotulo_fator}</td>
              <td>{e.rotulo_nivel}</td>
              <td>{e.rotulo_referencia} ({pct(e.taxa_referencia)})</td>
              <td className="num">{inteiro(e.usuarios)}</td>
              <td className="num">{pct(e.taxa)}</td>
              <td>{sinal(e.bruto)} {intervaloPp(e.bruto_ic_baixo, e.bruto_ic_alto)}</td>
              <td>{sinal(e.ajustado)} {intervaloPp(e.ajustado_ic_baixo, e.ajustado_ic_alto)}</td>
              <td>{e.ic_exclui_zero ? "sim" : "não"}{e.aviso ? " (poucos casos)" : ""}</td>
              <td className="fonte">{e.fonte}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
