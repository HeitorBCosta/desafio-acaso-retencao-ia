# BDR-001: Definição de usuário = IP + sistema operacional + navegador

- Status: aceita
- Data: 10/11/2026

## Contexto

A base não tem identificador de pessoa. Toda definição de usuário erra em algum caso, então a escolha é sobre qual erro aceitar. Medidas do recorte Brasil em `relatorios/02_definicoes_usuario.txt` e `relatorios/03_horarios_e_sessao.txt`.

## Opções consideradas

| Opção | Usuários | Retorno 7d (outro dia)* | Retorno 7d (sessão 30 min)* | Variação com corte ≥5 user-agents** | Erro aceito |
|---|---|---|---|---|---|
| IP | 2.385 | 18,0% | 24,1% | −0,8 pp | junta pessoas diferentes no mesmo IP |
| IP + user-agent completo | 2.895 | 19,2% | 26,1% | −2,9 pp | separa a mesma pessoa quando a versão do navegador muda |
| IP + SO + navegador | 2.533 | 17,7% | 24,1% | −1,1 pp | junta pessoas com mesmo IP, mesmo SO e mesmo navegador |

\* Início e fim de cada conversa pelas respostas do assistente (script 03).
\** Âncora só no fim, sessão de 30 min (script 02).

## Decisão

Usuário = `hashed_ip` + sistema operacional + navegador, sem a versão do navegador. SO e navegador saem de regras de texto sobre o user-agent; as 15 combinações mais frequentes cobrem 99,8% das conversas e nenhuma delas é "Outro".

## Justificativa

- Separa dispositivos diferentes no mesmo IP, o que o IP sozinho não faz.
- Não muda a chave da pessoa quando o navegador atualiza, o que o user-agent completo faz.
- O retorno fica praticamente igual ao do IP sozinho, então a separação por dispositivo não cria nem esconde retornos de forma relevante.
- É menos sensível que o user-agent completo à exclusão de IPs com muitos user-agents.
- Não foi escolhida pelo valor da taxa de retorno.

## O que muda se a premissa estiver errada

- Se muitas pessoas compartilham IP, SO e navegador (redes de empresa ou universidade), o número de usuários fica subestimado e o retorno pode ficar superestimado.
- As outras duas definições são calculadas e apresentadas como análise de sensibilidade.
