# BDR-004: Resposta curta não é indicador de falha; no lugar, campos de "primeira mensagem sem pedido"

- Status: aceita
- Data: 10/11/2026

## Contexto

O plano previa um campo "resposta vazia ou muito curta" como indicador indireto de falha, com o limite de tamanho definido depois de ver os dados. Medidas sobre a primeira resposta do assistente de cada usuário (2.533 usuários; `relatorios/04_campos_primeira_conversa.txt` e `relatorios/05_amostras_leitura.txt`):

- Nenhuma resposta vazia.
- 463 usuários com resposta abaixo de 50 caracteres, com 149 textos distintos.
- 318 usuários na faixa de 30 a 39 caracteres, a maior faixa abaixo de 100.
- Os 30 textos mais frequentes abaixo de 50 caracteres cobrem 344 dos 463 usuários, e todos são cumprimentos de volta ("Hello! How can I assist you today?": 96; "Olá! Como posso ajudar você hoje?": 92).
- Entre as primeiras perguntas abaixo de 20 caracteres (635 usuários), os 30 textos mais frequentes somam 446 usuários. Por leitura: 347 só saudação ("oi": 99, "olá": 63, "hi": 50…), 72 vazias, 19 testes ("test", "teste", "testando") e 8 pedidos de fato.

## Opções consideradas

1. Manter "resposta muito curta" com um limite de tamanho.
2. Retirar o campo e descrever a primeira mensagem do usuário.

## Decisão

Opção 2. O tamanho da resposta continua como medida descritiva, mas não é usado como indicador de falha. Entram três campos sobre a primeira mensagem do usuário, calculados sobre o texto normalizado (minúsculas, sem pontuação, espaços colapsados):

- `pergunta_vazia`: sem texto.
- `pergunta_saudacao`: só saudação (regra `REGEX_SAUDACAO` no script 04).
- `pergunta_teste`: só teste (regra `REGEX_TESTE` no script 04).

## Justificativa

Nos dados, resposta curta é quase sempre o cumprimento padrão do assistente a quem só disse "oi". Um limite de tamanho marcaria como falha justamente essas respostas.

## Conferência

- As regras de saudação e teste reproduzem a classificação por leitura dos 30 textos mais frequentes (347 / 19 / 8, mais 72 vazias), testado em Python sobre esses 30 textos.
- O script 05 lista todos os textos marcados (`05_saudacao_teste_textos.csv`) e os textos curtos que nenhuma regra marcou (`05_curtas_sem_marca.csv`), para conferência por leitura.

## Atualização (10/11/2026): mensagem vazia separada em três tipos

A leitura das 30 respostas mais frequentes às 72 primeiras mensagens vazias (34 usuários) mostrou três situações diferentes:

| Resposta do assistente | Usuários |
|---|---|
| Diz que a mensagem veio vazia ou incompleta | 15 |
| Só um cumprimento curto | 9 |
| Explica um tema específico (ex.: Einstein, álgebra) ou fala de si mesmo | 10 |

Nos 10 últimos casos, o assistente respondeu a algo que não está na base, então o texto do usuário provavelmente existia e se perdeu. Por isso `pergunta_vazia` ganhou o campo `pergunta_vazia_tipo`:

- `confirmada`: a resposta diz que a mensagem veio vazia ou incompleta (`REGEX_RESP_VAZIO`).
- `indeterminada`: a resposta é só um cumprimento com menos de 150 caracteres.
- `texto_ausente`: qualquer outra resposta. É tratado como problema de qualidade dos dados, não como comportamento do usuário.

As regras reproduzem a leitura nos 30 textos (15 / 9 / 10, testado em Python). O script 05 lista os 72 casos com o tipo atribuído (`05_pergunta_vazia_todas.csv`) para conferência.

## Atualização 2 (10/11/2026): rótulos manuais para as 72 mensagens vazias

Na base inteira, a regra deu 18 confirmadas, 9 indeterminadas e 45 com texto ausente. A leitura dos 72 casos (`05_pergunta_vazia_todas.csv`) mostrou que confirmadas e indeterminadas estavam certas, mas 13 dos 45 "texto ausente" estavam errados:

| Leitura | Casos | Tipo correto |
|---|---|---|
| A resposta diz que não houve pergunta ("missing", "without a specific question") | 3 | confirmada |
| Cumprimento ou oferta genérica sem "Hello" no início ("How can I help you today?", "Welcome!") | 4 | indeterminada |
| A resposta pede mais contexto sem dizer que a mensagem veio vazia | 6 | indeterminada |

Totais pela leitura: 21 confirmadas, 19 indeterminadas e 32 com texto ausente (18 explicam um tema, 7 falam do próprio assistente, 7 recusam um pedido específico). Acerto da regra em "texto ausente": 32 de 45.

Decisão: como a população inteira foi lida, o tipo final vem de `docs/rotulos/pergunta_vazia_tipo.csv` (só `conversa_id`, tipo, motivo e quem rotulou; sem texto de conversa). A regra continua no código como primeira passada e fica gravada em `pergunta_vazia_tipo_regra` para auditoria. Ampliar a regra para acertar exatamente estes 72 casos foi descartado: seria ajuste caso a caso e ainda erraria pelo menos um caso correto (1782985).

Conferência: leitura feita pelo Claude e aceita pelo Heitor em 10/11/2026. O script 04 informa quantas mensagens vazias ficaram sem rótulo e quantos rótulos não acharam conversa; os dois números devem ser 0.

## Limitações conhecidas

- Na leitura das 30 perguntas curtas mais frequentes que nenhuma regra marcou, 4 parecem saudação ou teste ("bo, dia", "como estas", "aaaa", "asd"; 1 usuário cada). A regra não foi ajustada a eles para não ser moldada caso a caso.
- 8 primeiras respostas começam com vírgula e continuam a palavra do usuário ("Oi" → ", tudo bem? Em que posso ajudar?"). Nenhuma tem `redacted`. Fica registrado como anomalia de qualidade, sem campo próprio.

## O que muda se a premissa estiver errada

Se houver respostas curtas que são falhas reais (por exemplo, cortadas), elas ficam fora deste campo. A recusa continua sendo o indicador indireto de falha.
