-- Efeitos pré-calculados na carga (scripts 07, 07b e 09). Nada é estimado na requisição.
SELECT analise, fator, nivel, referencia, usuarios, voltaram, taxa, taxa_referencia,
       bruto, bruto_ic_baixo, bruto_ic_alto, ajustado, ajustado_ic_baixo, ajustado_ic_alto,
       metodo, aviso, fonte
FROM analytics.efeitos
ORDER BY analise, abs(ajustado) DESC NULLS LAST;
