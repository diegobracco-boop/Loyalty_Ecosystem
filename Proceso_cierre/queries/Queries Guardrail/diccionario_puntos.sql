-- Diccionario de tipos de punto (guardrail).
-- Se baja cada mes como primer paso del cierre. Sus `code` se comparan contra el
-- baseline del mes anterior (referencia/diccionario_puntos.xlsx): si aparece un code
-- nuevo, el pipeline frena y alerta, porque el CASE de la query de Redenciones podria
-- no estar mapeandolo bien (caeria en 'general' por defecto).
-- NOTA: la columna accum_period viene mal cargada en origen - se ignora.
select * from data.lake.clm_point_types
