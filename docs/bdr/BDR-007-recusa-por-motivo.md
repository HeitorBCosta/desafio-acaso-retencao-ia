# BDR-007: Separar a recusa pelo motivo para distinguir efeito do produto de perfil de quem pede

- Status: aceita
- Data: 11/11/2026

## Contexto

O script 07 mostrou que quem teve o primeiro pedido não atendido (definição da BDR-005) volta menos: 12,7% contra 24,7%, uma diferença ajustada de −11,7 pontos percentuais [−17,9; −5,6]. Esse número admite duas explicações:

- **Efeito do produto:** a recusa em si afasta a pessoa.
- **Perfil de quem pede (seleção):** quem recebe recusa já tinha menos tendência a voltar, por exemplo quem testa pedidos proibidos por curiosidade.

As duas levam a decisões diferentes. Só a primeira justifica mexer no produto.

## Opções consideradas

1. Tratar a recusa como um bloco só e declarar que não dá para separar causa de seleção.
2. Separar as recusas pelo motivo, já registrado na leitura (BDR-005), e comparar os grupos.

## Decisão

Opção 2, com a regra de leitura fixada antes de rodar o script 07b:

- Grupos: **limitação do produto** (o assistente não sabe ou não consegue: motivos "capacidade" e "conhecimento") e **política de conteúdo** (o pedido é proibido). Motivo "desconhecido" fica fora (3 usuários).
- Se só a recusa por política reduzir o retorno, a explicação mais provável é o perfil de quem pede.
- Se só a recusa por limitação reduzir, o produto contribui para a perda.
- Se as duas reduzirem, ou nenhuma, o resultado é inconclusivo com esta base.

## Resultado

Fonte: `relatorios/07b_recusa_motivo.txt`.

| Grupo | Usuários | Voltaram | Taxa | Diferença bruta contra sem recusa | Diferença ajustada |
|---|---|---|---|---|---|
| Limitação do produto | 83 | 6 | 7,2% | −17,5 pontos percentuais [−21,7; −9,6] | −17,5 [−23,3; −11,7] |
| Política de conteúdo | 40 | 9 | 22,5% | −2,2 pontos percentuais [−12,5; +12,9] | −1,2 [−14,3; +11,9] |

Os dois grupos diferem entre si: −15,3 pontos percentuais [−30,8; −2,5] (método de Newcombe sobre 6 de 83 e 9 de 40).

Pela regra, só a limitação do produto reduz o retorno: o produto contribui. Esse é o achado 1 do documento.

## Limites

- Só 6 retornos no grupo de limitação: o intervalo do método delta é pouco confiável; vale o intervalo da diferença bruta.
- O motivo foi lido pelo Claude. O Heitor conferiu 30 das 129 recusas e concordou com as 30 (intervalo de confiança de 95%: 88,6% a 100%), numa conferência não cega.
- O resultado não separa "recebeu um não" de "o produto não serve para o que a pessoa queria". As duas levam à mesma ação: oferecer alternativa quando não puder atender, e confirmar com um experimento com grupos sorteados.
