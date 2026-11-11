# BDR-003: Retorno = nova sessão em até 7 dias; sessão encerra após 30 min sem uso

- Status: aceita
- Data: 10/11/2026

## Contexto

A pergunta do cliente é se a pessoa volta a usar o assistente em até 7 dias. Para isso é preciso definir quando um uso é "outro" uso. A base só tem horário das respostas do assistente (26.579 de 26.579); as mensagens do usuário não têm horário (0 de 26.579). A coluna `timestamp` é igual ao horário da última resposta em 11.621 de 11.621 conversas.

## Opções consideradas

Retorno em 7 dias, usuário conforme a BDR-001, início e fim de cada conversa pelas respostas do assistente (`relatorios/03_horarios_e_sessao.txt`):

| Regra | Retorno | IC 95% |
|---|---|---|
| Nova sessão após 30 min | 24,1% | 22,5–25,8% |
| 1 h | 21,8% | 20,3–23,5% |
| 2 h | 20,2% | 18,7–21,8% |
| 6 h | 17,0% | 15,5–18,5% |
| 12 h | 15,3% | 13,9–16,8% |
| 24 h | 11,3% | 10,1–12,6% |
| Outro dia do calendário (UTC) | 17,7% | 16,3–19,3% |
| Outro dia do calendário (America/Sao_Paulo) | 17,2% | 15,7–18,7% |

A última linha foi acrescentada com o script 06 (`relatorios/06_desfecho_retorno.txt`). O script 06 reproduz exatamente todas as demais linhas da tabela (por exemplo, 30 min: 2.482 elegíveis, 598 voltaram).

## Decisão

- Sessão: conversas do mesmo usuário ficam na mesma sessão enquanto o início de uma vem até 30 min depois do maior fim anterior. Passou disso, começa nova sessão.
- Retorno em 7 dias: o usuário inicia uma 2ª sessão até 7 dias após o início da 1ª conversa.
- Elegíveis: usuários cuja 1ª conversa ocorreu pelo menos 7 dias antes do fim dos dados (29/04/2024 23:33 UTC).

## Justificativa

30 minutos sem atividade é o tempo padrão de encerramento de sessão do Google Analytics, ferramenta de análise web amplamente usada, o que facilita a explicação ao cliente. O próprio Google permite ajustar esse tempo, então ele é uma convenção, não uma regra do comportamento do usuário. Fonte: documentação oficial do Google Analytics (https://support.google.com/analytics/answer/2731565) e da Central de Ajuda do Firebase/GA4 (https://support.google.com/firebase/answer/9191807).

A janela de 7 dias não é uma escolha nossa: vem da pergunta de negócio do enunciado do desafio ("voltar a usá-lo em até 7 dias").

## Limitações registradas

- Quem volta pouco mais de 30 min depois conta como retorno, mesmo que tenha sido no mesmo momento de uso. Medido no script 06, entre os 598 usuários que voltaram, o tempo entre o início da 1ª conversa e o início da 2ª sessão foi de: p10 1,0 h; p25 2,3 h; mediana 11,1 h; p75 41,6 h; p90 81,9 h. Ou seja, um quarto dos retornos acontece em até cerca de 2,3 h.
- O início de cada conversa é a 1ª resposta do assistente, não a 1ª mensagem do usuário. Em 10% das conversas com mais de uma resposta, a 1ª e a última estão a mais de 65,8 min de distância. Uma pausa dentro do mesmo momento de uso pode virar nova sessão.
- Retornos feitos dentro da mesma conversa (o usuário continua uma conversa antiga em outro dia) não são contados.

## O que muda se a premissa estiver errada

A taxa varia de 24,1% (30 min) a 11,3% (24 h). Todas as regras da tabela entram no documento como análise de sensibilidade, e os achados só são apresentados como sólidos se a direção do efeito se mantiver nas regras alternativas.
