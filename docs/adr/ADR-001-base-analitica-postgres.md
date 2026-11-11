# ADR-001: Base analítica em PostgreSQL (local) / Amazon RDS for PostgreSQL (AWS)

- Status: aceita
- Data: 10/11/2026

## Contexto

O desafio exige que:

- o dashboard não leia a base bruta, e sim uma base analítica desenhada e populada por nós;
- o dashboard suba do zero com um comando (ex.: `docker compose up`), carregando a base analítica a partir da base bruta;
- toda a infraestrutura e o custo do dashboard fiquem na AWS; para a entrega basta rodar localmente e descrever a implantação.

Volume medido do recorte Brasil: 11.621 conversas, 2.385 IPs, período de 09/04/2023 a 29/04/2024 (`relatorios/perfil_brasil.txt`).

## Opções consideradas

1. **PostgreSQL**: local em contêiner; na AWS, Amazon RDS for PostgreSQL.
2. **Arquivo DuckDB lido pelo backend**: local sem servidor; na AWS, o arquivo ficaria no S3 ou em disco da aplicação.
3. **Parquet no S3 consultado pelo Amazon Athena**: sem equivalente local direto.
4. **Amazon Redshift**: sem equivalente local direto.

## Decisão

PostgreSQL como base analítica (opção 1).

## Justificativa

- O mesmo motor roda no `docker compose` e no RDS, então o que for testado localmente vale na AWS.
- Atende o "sobe com um comando": o contêiner do Postgres sobe e o contêiner de carga popula as tabelas.
- O volume é pequeno para um Postgres e não exige um motor colunar (opções 3 e 4).
- Permite migrações versionadas, testes de indicadores em SQL e controle de acesso por papel, temas cobertos na seção 4.1 do desafio.
- Na opção 2, cada instância do backend teria a sua cópia do arquivo, e a atualização dessas cópias precisaria de solução própria.

## Consequências

- A análise exploratória continua em DuckDB sobre os parquets, fora da base analítica.
- A carga lê a base bruta e grava só campos derivados. O texto das conversas não entra na base analítica.
- Implantação descrita, não executada: base bruta no S3, carga como tarefa agendada, base analítica no RDS e backend em serviço gerenciado. Cada componente vai ter ADR próprio.
