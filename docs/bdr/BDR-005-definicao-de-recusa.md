# BDR-005: Recusa = pedido não atendido como pedido, guardado em três níveis

- Status: aceita
- Data: 10/11/2026

## Contexto

A regra de texto v1 do script 04 marcou 116 primeiras respostas como recusa. A leitura das 116 (`data/amostras/05_recusa_todas_marcadas.csv`; rótulos em `docs/rotulos/recusa_resultado.csv`) mostrou que a regra junta situações diferentes:

| Resultado lido | Usuários | Exemplo |
|---|---|---|
| Não atendido | 54 | instruções perigosas, keygen, chave de API |
| Parcial (entregou outra coisa no lugar do pedido) | 34 | pediu imagem e recebeu descrição; pediu código e recebeu roteiro de passos |
| Atendido (só um aviso inicial) | 24 | "As an AI, I can't taste pizza, but here's a ranking…" com a lista completa |
| Sem pedido claro | 4 | mensagem vazia, "olivia" |

Motivo, entre os 88 não atendidos ou parciais: capacidade 43, política de conteúdo 32, conhecimento (data de corte ou previsão) 11, desconhecido 2.

Acerto da regra v1: 54 de 116 (47%) contando só "não atendido"; 88 de 116 (76%) contando também "parcial".

## Opções consideradas

- (A) Recusa = só "não atendido".
- (B) Recusa = "não atendido" + "parcial".

## Decisão

- A variável é guardada em três níveis (atendido / parcial / não atendido), com o motivo (capacidade / política / conhecimento / desconhecido).
- Definição principal na análise: (B), chamada "pedido não atendido como pedido".
- A análise mostra também o efeito de "parcial" e de "não atendido" separados. Se os dois apontarem na mesma direção, a junção se sustenta; se divergirem, isso é reportado como achado.

## Justificativa

- Em (A), quem pediu uma imagem e recebeu uma descrição ficaria no mesmo grupo de quem foi atendido. Misturar falhas no grupo de controle tende a diluir o efeito, empurrando o resultado para "não faz diferença".
- Em (B), o custo é juntar "não recebeu nada" com "recebeu outra coisa". Esse custo é exposto pela análise separada dos dois níveis.
- A fronteira entre parcial e não atendido é a parte mais subjetiva da leitura; mantê-la visível evita que ela decida o resultado sem aparecer.

## Pendências

- Os rótulos foram lidos pelo Claude. Em 11/11/2026, o Heitor conferiu uma amostra de 30 das 129 recusas (sorteio do script 12) e concordou com o resultado e o motivo em todas: 30 de 30, IC 95% de 88,6% a 100%. A conferência não foi cega (o rótulo aparecia ao lado do texto), o que pode inflar a concordância. Os casos conferidos estão marcados na coluna `conferido_por`.
- A regra v1 pode ter deixado recusas passar. A leitura de `05_recusa_dirigida.csv` (140 respostas não marcadas que têm palavras-chave de recusa) mede isso.
