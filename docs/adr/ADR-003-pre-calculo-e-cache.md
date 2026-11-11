# ADR-003: O que é pré-calculado, o que vai para cache e como o tempo é medido

- Status: aceita
- Data: 11/11/2026

## Contexto

As telas precisam abrir rápido. Os efeitos vêm de regressões, de uma ponderação com 1.000 reamostragens (bootstrap) e de decomposições que levam segundos ou minutos. Os cartões e as séries são contagens simples sobre cerca de 2.500 linhas. A base analítica só muda quando roda uma carga nova.

## Opções consideradas

1. **Calcular tudo na requisição.** Simples, mas a ponderação com bootstrap levaria segundos a cada abertura da tela.
2. **Pré-calcular tudo** (inclusive cada combinação de filtro de período). Rápido, mas multiplica tabelas e prende a tela aos filtros previstos.
3. **Pré-calcular só o que é caro, consultar o resto e guardar as respostas em cache até a próxima carga.**

## Decisão

Opção 3.

- **Pré-calculado na carga:** todos os efeitos (scripts 07, 07b e 09), gravados na tabela `analytics.efeitos`. Nada é estimado na requisição.
- **Consultado na hora:** cartões e séries por semana ou mês, com índices em `data_chegada` e `semana_chegada`.
- **Cache:** em memória no backend, por endpoint e parâmetros. A chave inclui o id da última carga (`analytics.carga_execucao`): quando uma carga termina, a chave muda e as respostas antigas deixam de ser usadas. O backend confere a carga a cada 60 segundos, e cada resposta guardada expira em 600 segundos.
- **Medição:** cada requisição grava uma linha de log estruturado (rota, parâmetros, status, duração, versão da carga) e devolve o cabeçalho `Server-Timing`.

## Justificativa

- O custo caro acontece uma vez por carga, não uma vez por visita.
- Invalidar o cache pela versão da carga evita mostrar número velho depois de uma carga nova, sem depender só do tempo de expiração.
- O log com a versão da carga permite saber, depois, de qual carga veio cada número mostrado (seção 4.1 do enunciado).

## Consequências

- Com mais de uma instância do backend, cada uma tem o seu cache. Na AWS, isso se resolve com um cache compartilhado (ElastiCache) ou com o CloudFront guardando as respostas pelo mesmo tempo (ADR-004).
- Um filtro novo de período não exige pré-cálculo, mas um efeito novo exige mudar a carga.
