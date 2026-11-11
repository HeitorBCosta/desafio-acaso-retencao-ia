-- Retorno em 7 dias por coorte de chegada (semana começa na segunda-feira, ou mês).
-- Mesmas definições de visao_geral.sql, agrupadas pelo período de chegada.
-- %(granularidade)s só aceita 'week' ou 'month' (validado na API antes da consulta).
SELECT
    date_trunc(%(granularidade)s, data_chegada)::date  AS periodo,
    count(*)                                          AS novos,
    count(*) FILTER (WHERE voltou_7d)                 AS voltaram
FROM analytics.usuario_primeira_experiencia
WHERE elegivel
  AND data_chegada BETWEEN %(inicio)s AND %(fim)s
GROUP BY 1
ORDER BY 1;
