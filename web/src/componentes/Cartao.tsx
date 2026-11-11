import type { ReactNode } from "react";
import type { Definicao } from "../api";
import { Ajuda } from "./Ajuda";

/** Cartão de número: título com definição, valor grande e uma linha de contexto. */
export function Cartao({ titulo, valor, detalhe, definicao }: {
  titulo: string;
  valor: ReactNode;
  detalhe?: ReactNode;
  definicao?: Definicao;
}) {
  return (
    <div className="cartao">
      <div className="cartao-titulo">
        {titulo} <Ajuda definicao={definicao} />
      </div>
      <div className="cartao-valor">{valor}</div>
      {detalhe && <div className="cartao-detalhe">{detalhe}</div>}
    </div>
  );
}
