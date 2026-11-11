# ADR-002: Stack do dashboard: FastAPI (Python) no backend e React no frontend

- Status: aceita
- Data: 11/11/2026

## Contexto

O enunciado pede um dashboard com frontend, backend e base analítica que suba do zero com um comando (`docker compose up`) e que mostre, em cada tela, cada número com definição e fonte e cada efeito com o seu intervalo de confiança. O público são pessoas de negócio, sem perfil técnico. A análise foi feita em Python (DuckDB, pandas, statsmodels).

## Opções consideradas

1. **Power BI.** Familiar para o público de negócio, mas não roda dentro do `docker compose`, depende de licença e de serviço da Microsoft (fora da AWS) e não deixa o backend explícito.
2. **Streamlit ou Dash (Python puro).** Rápido de escrever, mas junta tela e servidor no mesmo processo, sem uma camada de backend com endpoints próprios, e dá pouco controle sobre gráficos específicos.
3. **Next.js (TypeScript de ponta a ponta).** Uma linguagem só para tela e servidor, mas o cálculo estatístico continuaria em Python, e haveria duas linguagens no backend.
4. **FastAPI (Python) + React (TypeScript, Vite, Recharts).**

## Decisão

Opção 4: backend em FastAPI e frontend em React com Vite e Recharts. O gráfico de efeitos (forest plot) é desenhado direto no código do frontend.

## Justificativa

- O backend fica na mesma linguagem da análise. A carga roda os mesmos scripts que geraram os números do documento, e não há reimplementação do cálculo.
- FastAPI valida a entrada de cada endpoint e gera a documentação dos endpoints sem código extra.
- Frontend e backend separados permitem cache, testes e implantação independentes (ADR-003 e ADR-004).
- Recharts cobre as linhas e barras da tela de Retenção. O forest plot precisava de rótulos em três linhas e de marcação do zero, e foi mais simples desenhá-lo do que adaptar uma biblioteca.
- As quatro peças (base, carga, backend, frontend) viram quatro contêineres no `docker compose`, e os mesmos contêineres vão para a AWS.

## Consequências

- Duas linguagens no projeto (Python e TypeScript), com dois conjuntos de dependências fixadas (`requirements*.txt` e `package-lock.json`).
- O frontend não tem lógica estatística: só formata o que o backend devolve.
