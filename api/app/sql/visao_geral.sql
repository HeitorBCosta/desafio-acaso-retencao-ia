-- Indicadores da tela Retenção (cartões).
-- Novos = usuários (BDR-001) com 1ª conversa (BDR-002) no período e 7 dias observados depois dela.
-- Voltaram = desses, os que começaram uma 2ª sessão (30 min, BDR-003) em até 7 dias.
-- Taxa = voltaram / novos; IC de Wilson calculado na API.
-- Período de referência: data da 1ª conversa, horário de Brasília, intervalo fechado [inicio, fim].
SELECT
    count(*)                              AS novos,
    count(*) FILTER (WHERE voltou_7d)     AS voltaram,
    min(data_chegada)                     AS primeira_data,
    max(data_chegada)                     AS ultima_data
FROM analytics.usuario_primeira_experiencia
WHERE elegivel
  AND data_chegada BETWEEN %(inicio)s AND %(fim)s;
