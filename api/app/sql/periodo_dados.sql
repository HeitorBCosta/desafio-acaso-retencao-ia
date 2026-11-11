-- Primeira e última data de chegada entre os elegíveis (limites padrão dos filtros).
SELECT min(data_chegada) AS inicio, max(data_chegada) AS fim
FROM analytics.usuario_primeira_experiencia
WHERE elegivel;
