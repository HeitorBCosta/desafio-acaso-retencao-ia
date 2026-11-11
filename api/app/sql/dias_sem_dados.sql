-- Dias sem nenhuma conversa na base bruta (todos os usuários): lacuna de coleta.
SELECT dia
FROM analytics.conversas_dia
WHERE conversas = 0
  AND dia BETWEEN %(inicio)s AND %(fim)s
ORDER BY dia;
