# Retenção de um assistente de IA: o que faz quem experimenta voltar em 7 dias?

Desafio técnico Acaso (Data Analyst Pleno). Análise das conversas do Brasil na base pública
[WildChat-1M](https://huggingface.co/datasets/allenai/WildChat-1M) (Allen Institute for AI,
licença ODC-BY) e um dashboard que leva os resultados a quem decide.

- **Pergunta:** o que faz uma pessoa que experimentou o assistente voltar a usá-lo em até 7 dias,
  quanto pesa cada fator e quanto disso é causa e não seleção.
- **Base:** 11.621 conversas do Brasil, de abril de 2023 a abril de 2024; 2.482 usuários novos
  com 7 dias observados, dos quais 598 voltaram (24,1%).
- **Documento com os achados e as decisões:** [`docs/documento.md`](docs/documento.md) (também em PDF: [`docs/documento.pdf`](docs/documento.pdf)).

## Como subir o dashboard

### Com Docker (um comando)

Pré-requisito: Docker com Docker Compose.

```bash
docker compose up --build
```

Abra http://localhost:8080 quando a carga terminar.

O que acontece, em ordem:

1. `db` sobe o PostgreSQL.
2. `carga` baixa a base do Hugging Face se ela ainda não estiver em `data/` (cerca de 3,4 GB,
   só na primeira vez), roda a análise (`carga/executar_carga.py`) e grava a base analítica.
   Termina sozinha.
3. `api` sobe a API (FastAPI) só depois que a carga termina sem erro.
4. `web` serve as telas (React) e repassa `/api` para a API.

### Sem Docker (Windows, como foi desenvolvido)

Pré-requisitos: Python 3.14, Node.js 26 e PostgreSQL 18 instalados.

1. Criar o banco, no `psql` como usuário `postgres`:
   ```sql
   CREATE USER acaso WITH PASSWORD 'acaso';
   CREATE DATABASE acaso OWNER acaso;
   ```
2. Ambiente Python e carga, na raiz do projeto:
   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   pip install -r requirements-carga.txt -r api\requirements-dev.txt
   $env:DATABASE_URL = "postgresql://acaso:acaso@localhost:5432/acaso"
   python carga\executar_carga.py
   ```
3. API, num terminal (com o mesmo `DATABASE_URL`):
   ```powershell
   cd api
   uvicorn app.main:app --reload
   ```
4. Telas, em outro terminal:
   ```powershell
   cd web
   npm install
   npm run dev
   ```
   Abra http://localhost:5173.

A senha `acaso` serve só para uso local. Na implantação descrita na AWS, ela fica no Secrets Manager.

## Testes

```powershell
cd api
python -m pytest -v
```

Os testes conferem que o intervalo de confiança da API dá os mesmos números dos relatórios da
análise, e o contrato dos endpoints: período inválido, base pequena, banco ainda sem carga.

## Estrutura

| Pasta | O que tem |
|---|---|
| `scripts/` | A análise, em ordem numérica. Cada script explica no topo o que faz, o que lê e o que gera. |
| `carga/` | Roda a análise na ordem certa e grava a base analítica (`executar_carga.py`). |
| `db/migracoes/` | O modelo da base analítica (schema `analytics`), em migrações SQL versionadas. |
| `api/` | Backend em FastAPI. As consultas de cada indicador ficam em `api/app/sql/`. |
| `web/` | Frontend em React (Vite, TypeScript, Recharts). |
| `relatorios/` | Saída de cada script de análise: só números e contagens, sem texto de conversa. |
| `docs/` | Decisões (ADRs e BDRs), rótulos lidos à mão, desenho do dashboard e os achados. |
| `data/` | Base bruta e intermediárias. Fica fora do Git (é baixada e gerada pela carga). |

Ordem da análise: 01 baixa a base · 02 e 03 testam definições de usuário e sessão · 04 monta os
campos da primeira conversa · 05 e 05b separam amostras para leitura · 06 calcula o retorno ·
07 mede os efeitos · 07b separa a recusa pelo motivo · 08 e 08b classificam o tema · 09 trata a
seleção do GPT-4 · 10 e 10b analisam a semana atípica e os dias sem coleta · 11 carrega o
PostgreSQL · 12 sorteia recusas para conferência · 13 mede o peso dos dias sem coleta · 14 testa
na base real o mecanismo do incidente da seção 4.2 (chave de usuário).

## Dados pessoais

As conversas podem ter dados pessoais. A base analítica e o dashboard guardam e mostram só
campos derivados e totais de grupos. Nunca entram texto de conversa, IP (nem o hash), user-agent
ou qualquer identificador de pessoa; o usuário é gravado como sha256. As amostras com texto,
usadas para conferir as regras lendo as conversas, ficam em `data/amostras/`, fora do Git. Os
rótulos versionados em `docs/rotulos/` têm só o id da conversa e o rótulo.

## Documentação

- `docs/documento.md`: o documento da entrega (definições, qualidade dos dados, efeitos,
  confusão, semana atípica, achados, dashboard, monitoramento, incidente, riscos e uso de IA).
- `docs/bdr/`: decisões de negócio (definição de usuário, primeira experiência, retorno e
  sessão, mensagem sem pedido, recusa, tema fora do modelo, recusa por motivo).
- `docs/adr/`: decisões técnicas (base analítica em PostgreSQL, stack do dashboard,
  pré-cálculo e cache, implantação na AWS).
- `docs/dashboard_desenho.md`: telas, indicadores, modelo da base e endpoints.
- `docs/achados.md`: os três achados e a decisão que cada um sustenta.
- `docs/rotulos/`: rótulos lidos à mão e conferências.
