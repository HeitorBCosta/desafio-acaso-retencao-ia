# Desenho do dashboard (rascunho de 11/11/2026)

Stack escolhida: FastAPI (Python) + React com Vite e Recharts; base analítica em PostgreSQL (ADR-001).
Público: pessoas de negócio, sem perfil técnico. Cada número tem definição e fonte; cada efeito tem intervalo.

## Telas

### Tela 1 — Retenção: "Quantas pessoas que experimentaram voltaram em até 7 dias, e isso mudou com o tempo?"

| Elemento | Gráfico | Por que esse tipo |
|---|---|---|
| Novos usuários, voltaram, taxa de retorno [IC 95%] | 3 cartões de número | O número principal precisa ser lido em 2 segundos |
| Retorno por semana (ou mês) de chegada | Linha com faixa de IC | Tempo no eixo x; a faixa mostra que semanas pequenas variam muito |
| Novos usuários por semana | Barras abaixo da linha, mesmo eixo x | Mostra o tamanho de cada ponto da linha |
| Dias sem coleta | Marcação vertical no gráfico | Explica quedas que são falha de registro, não de produto |

Base pequena: semana com menos de 40 elegíveis aparece com ponto vazado, sem faixa de IC e com o texto
"base pequena (n < 40): a taxa varia mais de ±13 pp só por acaso". Filtro: semanal ou mensal (no mensal,
quase todos os pontos passam de 40).

### Tela 2 — O que faz voltar: "O que na primeira conversa muda a chance de voltar, e quanto?"

| Elemento | Gráfico | Por que esse tipo |
|---|---|---|
| Efeito de cada fator em pp, com IC 95% | Pontos com barra de intervalo, ordenados pelo tamanho (forest plot) | Compara tamanho e incerteza de vários efeitos numa linha comum a zero |
| Cor do ponto | "o intervalo não cruza zero" / "cruza zero" | Diz, sem jargão, se o efeito se sustenta |
| Detalhe ao passar o mouse | Taxa do grupo, taxa da referência, n, efeito bruto e ajustado, fonte | Cada número com definição e fonte |
| Os 3 achados | Cartões de texto com o número e a decisão | Liga o gráfico à recomendação |

Base pequena: nível com menos de 30 usuários ou menos de 10 retornos aparece com aviso
"poucos casos: intervalo pouco confiável".

## Indicadores

| Indicador | Definição | Fórmula | Denominador | Período de referência |
|---|---|---|---|---|
| Novos usuários | Usuários (BDR-001) cuja 1ª conversa caiu no período e que têm 7 dias observados depois dela | count(*) | — | data da 1ª conversa, Brasília |
| Voltaram em 7 dias | Desses, os que começaram uma 2ª sessão (30 min sem atividade, BDR-003) em até 7 dias | count(*) filter (voltou_7d) | — | idem |
| Taxa de retorno em 7 dias | Voltaram / novos | voltaram / novos | novos elegíveis | idem |
| IC 95% da taxa | Intervalo de Wilson | fórmula de Wilson | novos elegíveis | idem |
| Efeito de um fator | Diferença em pp entre o nível e a referência, ajustada pelos outros fatores e pelo trimestre | efeito marginal médio da regressão logística (script 07) | elegíveis | base inteira |

SQL de cada indicador: em `docs/indicadores.sql` (a escrever junto com o backend).

## Base analítica (schema `analytics`)

| Tabela | Grão | Conteúdo | Texto de conversa? |
|---|---|---|---|
| usuario_primeira_experiencia | 1 linha por usuário | id (sha256 do usuário), data e semana de chegada, fatores da 1ª conversa, elegível, voltou | não |
| conversas_dia | 1 linha por dia | total de conversas (todos os usuários) | não |
| efeitos | 1 linha por fator e nível | n, voltaram, taxa, bruto e ajustado com IC, avisos, fonte, versão | não |
| carga_execucao | 1 linha por carga | início, fim, linhas por tabela, versão do código, hash da base bruta | não |

O dashboard nunca mostra: texto de conversa, IP (nem o hash), user-agent, nenhum identificador de usuário.
Só agregados, e só agregados com n mínimo.

## Endpoints

| Endpoint | Entrada | Saída |
|---|---|---|
| GET /api/visao-geral | inicio, fim (datas) | novos, voltaram, taxa, ic_baixo, ic_alto, data_da_carga |
| GET /api/retencao/coortes | inicio, fim, granularidade (semana, mes) | lista de {periodo, novos, voltaram, taxa, ic_baixo, ic_alto, base_pequena} |
| GET /api/efeitos | — | lista de {fator, nivel, referencia, n, voltaram, taxa, taxa_referencia, bruto[ic], ajustado[ic], ic_exclui_zero, aviso, fonte} |
| GET /api/qualidade/dias-sem-dados | inicio, fim | lista de datas sem conversa |
| GET /api/saude | — | status da base e data da última carga |

## Fluxo com um comando (`docker compose up`)

1. `db`: PostgreSQL.
2. `carga`: se `data/raw` estiver vazio, baixa o WildChat-1M (script 01); roda os scripts 04, 06, 07, 07b, 09, 10 e 10b; aplica as migrações em `db/migracoes`; grava as tabelas de `analytics`; registra a execução em `carga_execucao`. Termina.
3. `api`: FastAPI, sobe depois que a carga termina com sucesso.
4. `web`: React compilado, servido por nginx, que repassa `/api` para a `api`.

Pré-calculado: os efeitos (regressões e bootstrap rodam na carga, não na requisição). Calculado na consulta:
as séries e os cartões (agregações simples sobre ~2.500 linhas).
