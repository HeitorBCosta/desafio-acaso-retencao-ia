# BDR-002: Primeira experiência = primeira conversa do usuário

- Status: aceita
- Data: 10/11/2026

## Contexto

Os fatores do retorno (modelo, tamanho, recusa, horário etc.) são medidos na primeira experiência de cada usuário. A primeira experiência precisa terminar antes de o retorno começar, para que a mesma conversa não conte como causa e como efeito.

## Opções consideradas

1. Primeira conversa.
2. Primeira sessão (todas as conversas até a primeira pausa maior que X).
3. Primeiro dia.

## Decisão

Primeira conversa: a de menor horário de início (primeira resposta do assistente; empate resolvido pelo horário de fim e depois pelo id da conversa), por usuário conforme a BDR-001.

## Justificativa

- Não depende da regra de sessão nem do fuso.
- Os campos vêm de uma conversa só, sem precisar de agregação.
- É fácil de explicar ao cliente.

## Consequências

- Com retorno definido por sessão, as demais conversas da primeira sessão não contam nem como experiência nem como retorno.
- O horário de início é o da primeira resposta do assistente, porque as mensagens do usuário não têm horário na base (medido: 0 de 26.579).
- A primeira sessão entra como análise de sensibilidade.
