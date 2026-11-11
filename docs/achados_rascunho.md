# Três achados para o cliente (rascunho de 11/11/2026, aprovado pelo Heitor)

Fontes: relatorios/07_efeitos.txt, relatorios/07b_recusa_motivo.txt, relatorios/09_gpt4_selecao.txt.
Rótulos: [MEDIDO] saiu de script; [DERIVADO] conta feita sobre números medidos; [PREMISSA] escolha declarada.

## 1. Quando o produto não consegue fazer o que a pessoa pediu na primeira conversa, ela quase não volta

**O que medimos**
- [MEDIDO] Recusa por limitação do produto (capacidade ou conhecimento): 7,2% de retorno (6 de 83), contra 24,7% sem recusa: -17,5 pp [-21,7; -9,6].
- [MEDIDO] Recusa por política de conteúdo: 22,5% (9 de 40), quase igual a sem recusa: -2,2 pp [-12,5; +12,9].
- [MEDIDO] Limitação vs política: -15,3 pp [-30,8; -2,5].
- Isso afasta a explicação de que o retorno baixo vem do tipo de usuário que faz pedidos proibidos: esses usuários, quando recusados, voltam quase na mesma taxa de quem foi atendido. O retorno baixo está em quem fez um pedido legítimo que o produto não conseguiu atender.

**Decisão que sustenta:** tratar a limitação de capacidade no primeiro uso como prioridade de produto: quando não puder atender, o assistente diz o que consegue fazer e oferece um caminho alternativo, em vez de só recusar; e mapear as capacidades que mais faltam para o roadmap.

**Tamanho e validação**
- [MEDIDO] 3,3% dos usuários novos (83 de 2.482).
- [DERIVADO] Se voltassem na taxa de quem não teve recusa, a taxa geral iria de 24,1% para 24,7% (teto, supondo efeito todo causal).
- [DERIVADO] Teste A/B (recusa atual vs recusa com alternativa): reduzir metade da diferença (7,2% -> 16%) exige 207 usuários por braço ([PREMISSA] alfa 5% bilateral, poder 80%).

**O que não prova:** não separa "recebeu um não" de "o produto não serve para o que ele queria" (as duas levam à mesma ação); só 6 retornos no grupo; motivos lidos pelo Claude, conferência do Heitor pendente.

## 2. Quem chega sem pedido (só "oi", "teste" ou mensagem vazia) volta menos

**O que medimos**
- [MEDIDO] 428 usuários (17,2% dos novos); retorno 15,4% contra 26,7% de quem chega com pedido médio.
- [MEDIDO] Ajustado pelos outros fatores: -8,5 pp [-14,5; -2,4]; mesmo sinal nas regras de retorno de 1 h, 24 h e outro dia.

**Decisão que sustenta:** primeiro uso guiado: quando a primeira mensagem for só cumprimento ou teste, o assistente responde com exemplos do que sabe fazer, para converter a visita num primeiro pedido real.

**Tamanho e validação**
- [DERIVADO] +8,5 pp nesse grupo levaria a taxa geral de 24,1% para cerca de 25,6% (teto, supondo efeito causal).
- [DERIVADO] Teste A/B para detectar 15,4% -> 23,9%: 342 usuários por braço (mesmas premissas).

**O que não prova:** pode ser seleção (quem chega só para "ver o que é" talvez voltasse menos de qualquer jeito); por isso o teste antes de assumir o ganho.

## 3. Usar GPT-4 não aumenta o retorno

**O que medimos**
- [MEDIDO] Quem usa GPT-4 é diferente (mais inglês, mais computador, mais noite).
- [MEDIDO] Comparando grupos equilibrados nessas características, nos trimestres com os dois modelos em uso (1.280 usuários): -3,5 pp [-8,2; +2,1] (IPTW). Sem equilíbrio: -1,1 pp [-5,9; +3,9].
- [MEDIDO] GPT-4 dá respostas mais longas e mais código; recusa na mesma proporção (5,3% vs 6,0%).

**Decisão que sustenta:** não usar o acesso ao modelo mais avançado como alavanca de retenção; se o GPT-4 custar mais, o modelo mais barato como padrão não deve reduzir o retorno (vantagem do GPT-4 acima de ~2 pp é improvável com estes dados).

**O que não prova:** ausência de efeito; ficam de fora o não medido (intenção de uso) e os trimestres com um só modelo.

## Fora dos três, e por quê
- Turnos (+17,0 pp para 5+): maior efeito, mas conversar mais é em parte o próprio engajamento; não é alavanca direta.
- Manhã (+6,9 pp): real, sem decisão clara.
- Queda de 17/07 a 13/08/2023 e 5 dias sem coleta: monitoramento e qualidade de dados.
