"""Textos que a tela mostra: nomes dos fatores e definições de cada número.

Ficam na API (e não no frontend) para que a definição de um indicador tenha um lugar só.
"""

# Abaixo disso a taxa de uma coorte varia mais de ±13 pp só por acaso (IC de Wilson com p≈24%).
MIN_COORTE = 40

FATORES = {
    "modelo": "Modelo da 1ª conversa",
    "turnos_faixa": "Nº de trocas (pergunta e resposta) na 1ª conversa",
    "periodo_dia": "Horário da 1ª conversa (Brasília)",
    "fim_de_semana": "Chegou no fim de semana",
    "primeira_mensagem": "Como foi a 1ª mensagem",
    "resposta_tamanho": "Tamanho da 1ª resposta do assistente",
    "recusa": "O assistente não atendeu o pedido",
    "recusa_nivel": "Recusa: parcial ou total",
    "recusa_motivo": "Recusa, por motivo",
    "idioma": "Idioma da conversa (rótulo da base)",
    "codigo": "A 1ª conversa teve código",
    "modelo_iptw": "GPT-4, comparando grupos parecidos",
}

# Nomes de nível mais claros para quem lê a tela (o valor original continua em "nivel").
NIVEIS = {
    "turnos_faixa": {"1": "1 troca", "2": "2 trocas", "3-4": "3 a 4 trocas", "5+": "5 ou mais trocas"},
    "recusa": {"sim": "pedido não atendido", "não": "pedido atendido"},
    "codigo": {"sim": "com código", "não": "sem código"},
    "fim_de_semana": {"sim": "sábado ou domingo", "não": "segunda a sexta"},
}


def rotulo_nivel(fator: str, nivel: str) -> str:
    return NIVEIS.get(fator, {}).get(nivel, nivel)


DEFINICOES = {
    "novos": {
        "titulo": "Novos usuários",
        "texto": ("Pessoas cuja primeira conversa caiu no período e que tiveram 7 dias inteiros "
                  "observados depois dela. Pessoa = mesmo IP (anonimizado), sistema e navegador."),
        "fonte": "analytics.usuario_primeira_experiencia (BDR-001, BDR-002)",
    },
    "voltaram": {
        "titulo": "Voltaram em 7 dias",
        "texto": ("Dos novos usuários, os que começaram uma nova sessão em até 7 dias depois da "
                  "primeira conversa. Nova sessão = depois de 30 minutos sem atividade."),
        "fonte": "analytics.usuario_primeira_experiencia (BDR-003)",
    },
    "taxa": {
        "titulo": "Taxa de retorno em 7 dias",
        "texto": ("Voltaram dividido por novos usuários. O intervalo mostra a faixa provável do "
                  "valor real (95% de confiança, método de Wilson)."),
        "fonte": "api/app/sql/visao_geral.sql",
    },
    "efeito": {
        "titulo": "Efeito no retorno",
        "texto": ("Quantos pontos percentuais a taxa de retorno muda nesse grupo, comparado ao grupo "
                  "de referência, entre pessoas parecidas nos outros fatores. A barra é o intervalo "
                  "de 95%: se ela cruza o zero, a diferença pode ser acaso."),
        "fonte": "analytics.efeitos (scripts 07, 07b, 09)",
    },
    "base_pequena": {
        "titulo": "Base pequena",
        "texto": (f"Menos de {MIN_COORTE} novos usuários: a taxa varia mais de 13 pontos só por "
                  "acaso, então o ponto aparece vazado e sem intervalo."),
        "fonte": "api/app/rotulos.py",
    },
    "dia_sem_dados": {
        "titulo": "Dia sem coleta",
        "texto": ("Dia sem nenhuma conversa registrada na base. Quem chegou na semana anterior pode "
                  "ter voltado nesse dia sem aparecer: o retorno dessa semana fica subestimado."),
        "fonte": "analytics.conversas_dia",
    },
}
