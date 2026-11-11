# BDR-006: Tema da primeira conversa fica fora do modelo de efeitos

- Status: aceita
- Data: 11/11/2026

## Contexto

O enunciado cita o tema da conversa entre as variáveis da primeira experiência. A base não traz tema; ele precisa ser atribuído a partir do texto da primeira mensagem. Decidimos não usar modelo de linguagem para isso e fixamos, antes de olhar o retorno, as regras para aceitar uma classificação:

- agrupamento automático: aceito se houver um número de grupos com estabilidade (índice de Rand ajustado) de pelo menos 0,80 entre sementes diferentes, todos os grupos com pelo menos 30 usuários e o maior grupo com no máximo 40%;
- qualquer método: aceito como variável do modelo se acertar pelo menos 70% numa amostra lida, sorteada sem olhar o resultado.

## Opções consideradas

1. **Agrupamento automático das primeiras mensagens** (frequência de palavras, redução de dimensões e k-means; script 08).
   - Versão 1: só o agrupamento em 6 grupos passou na estabilidade (0,842), mas os grupos se formaram por idioma e por cumprimento, não por assunto. O maior grupo tinha 1.049 de 2.363 usuários (44%).
   - Versão 2, sem cumprimentos e sem palavras sobre o próprio assistente: nenhum número de grupos chegou a 0,80 de estabilidade, e o maior grupo ficou com 45% (`relatorios/08_temas_escolha_k.txt`).
2. **Dicionário de palavras-chave** com 12 temas em ordem de prioridade (script 08b).
   - Versão 1: 54 de 98 corretos (55,1%; intervalo de confiança de 95%: 45,2% a 64,6%).
   - Versão 2, com as listas corrigidas a partir dos erros e testada numa amostra nova de usuários: 65 de 97 corretos (67,0%; intervalo de confiança de 95%: 57,2% a 75,6%). Em 79 de 97 (81,4%) a regra pegou ao menos um pedido real da mensagem.
3. **Modelo de linguagem.** Descartado: no dashboard ele teria que rodar na AWS, com custo e validação próprios, para uma variável que não é o centro da pergunta.

## Decisão

- O tema entra só como descrição (distribuição dos temas na seção de análise exploratória), com a taxa de acerto declarada.
- O tema não entra no modelo de efeitos nem nos achados.
- As listas do dicionário ficam congeladas na versão 2.

## Justificativa

- Com 67% de acerto, um terço dos usuários estaria no tema errado. Um efeito de tema medido assim misturaria temas e tenderia a parecer menor do que é, ou a aparecer onde não existe.
- O limite de 70% foi fixado antes de ver o resultado. Mudar o limite depois de saber que a classificação ficou abaixo dele tiraria o valor da regra.

## Consequências

- A análise não responde "que temas afastam as pessoas". Parte disso aparece por outro caminho: código (variável própria, 99 de 100 corretas na leitura) e recusa por motivo (BDR-007).
- Para medir tema no futuro: classificação validada com amostra lida maior, ou campo de categoria escolhido pelo próprio usuário.
- Os rótulos de tema foram lidos pelo Claude e não passaram por conferência humana.
