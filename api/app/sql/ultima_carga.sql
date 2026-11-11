-- Última carga concluída: identifica a versão dos dados (usada também como chave do cache).
SELECT carga_id::text AS carga_id, fim, versao_codigo, linhas, checagens
FROM analytics.carga_execucao
ORDER BY fim DESC
LIMIT 1;
