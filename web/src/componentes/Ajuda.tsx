import { useId, useState } from "react";
import type { Definicao } from "../api";

/** Botão "?" que mostra a definição e a fonte de um número (ao passar o mouse, focar ou clicar). */
export function Ajuda({ definicao }: { definicao?: Definicao }) {
  const [aberta, setAberta] = useState(false);
  const id = useId();
  if (!definicao) return null;
  return (
    <span className="ajuda" onMouseEnter={() => setAberta(true)} onMouseLeave={() => setAberta(false)}>
      <button
        type="button"
        className="ajuda-botao"
        aria-describedby={id}
        aria-label={`O que é: ${definicao.titulo}`}
        onFocus={() => setAberta(true)}
        onBlur={() => setAberta(false)}
        onClick={() => setAberta((a) => !a)}
      >
        ?
      </button>
      {aberta && (
        <span role="tooltip" id={id} className="ajuda-texto">
          <strong>{definicao.titulo}</strong>
          <span>{definicao.texto}</span>
          <span className="fonte">Fonte: {definicao.fonte}</span>
        </span>
      )}
    </span>
  );
}
