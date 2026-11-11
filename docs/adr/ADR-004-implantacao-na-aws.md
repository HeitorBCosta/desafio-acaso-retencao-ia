# ADR-004: Implantação na AWS (descrita, não executada)

- Status: aceita
- Data: 11/11/2026

## Contexto

O enunciado exige que toda a infraestrutura e todo o custo do dashboard fiquem na AWS, inclusive um modelo de linguagem, se houver. Para a entrega, basta rodar localmente e descrever a implantação. Localmente, a solução são quatro contêineres (`docker-compose.yml`): base, carga, backend e frontend. A base analítica é PostgreSQL (ADR-001).

## Opções consideradas

1. **Contêineres gerenciados (ECS com Fargate):** os mesmos contêineres do `docker compose`, sem servidor para administrar.
2. **Funções (Lambda) para a carga e o backend:** paga só pelo uso, mas exigiria reempacotar o código, e a carga tem dependências pesadas (statsmodels, scikit-learn) e duração limitada a 15 minutos por execução.
3. **Máquinas virtuais (EC2):** controle total, mas com sistema operacional, atualizações e escala a cargo do time.

## Decisão

Opção 1, com estas peças:

| Peça | Serviço |
|---|---|
| Base bruta (parquet do WildChat) | Amazon S3, com acesso restrito |
| Carga | tarefa no ECS Fargate, disparada pelo EventBridge Scheduler; termina ao fim da carga |
| Base analítica | Amazon RDS for PostgreSQL, em rede privada |
| Backend | serviço no ECS Fargate atrás de um Application Load Balancer |
| Frontend | arquivos estáticos no S3, servidos pelo CloudFront, que repassa `/api/*` ao balanceador |
| Senhas | AWS Secrets Manager |
| Logs, métricas e alarmes | Amazon CloudWatch |
| Imagens dos contêineres | Amazon ECR |
| Modelo de linguagem | nenhum hoje; se o cliente quiser classificar tema e recusa em dados novos, Amazon Bedrock (decisão em aberto) |

## Justificativa

- O que roda no `docker compose` é o que roda na AWS: as mesmas imagens, as mesmas migrações e a mesma carga. O teste local vale para a produção.
- A carga roda e termina, então como tarefa agendada só existe enquanto trabalha.
- O RDS mantém o mesmo motor do ambiente local (ADR-001).
- O frontend é só arquivo estático depois do build, e S3 com CloudFront é o caminho mais simples para servir isso.

## Consequências

- O custo não foi estimado com preços conferidos; antes da implantação, fazer a estimativa na calculadora da AWS com o tamanho real da base do cliente.
- A base bruta guarda texto de conversa e IP anonimizado, então o bucket precisa de acesso restrito, criptografia e regra de retenção (decisão em aberto com o cliente, seção 4.3 do documento).
- Deploy: integração contínua roda os testes, publica as imagens no ECR, roda as migrações como tarefa e depois atualiza o serviço do backend com troca gradual.
