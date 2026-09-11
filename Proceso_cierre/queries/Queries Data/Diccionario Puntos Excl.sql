SELECT
    id,
    code,
    tratamiento
FROM (
    SELECT 
        id, 
        code,
        description,
        CASE 
            WHEN code = 'FORTUNE'       THEN 'FORTUNE'
            WHEN code = 'GAMI'          THEN 'Puntos R&B'
            WHEN code = 'R&B'           THEN 'Puntos R&B'
            WHEN code = 'SUBS'          THEN 'SUBSCRIPTION'
            WHEN code = 'SUBS_INT'      THEN 'SUBSCRIPTION_INT'
            WHEN code = 'IFOOD_BR'      THEN 'IFOOD_BR'
            WHEN code = 'IFOOD_WEL'     THEN 'IFOOD_WEL'
            WHEN code = 'IFOOD_2W'      THEN 'IFOOD_2W'
            WHEN code = 'IFOOD_PR'      THEN 'IFOOD_PR'
            WHEN code = 'IFOOD_1M'      THEN 'IFOOD_1M'
            WHEN code = 'PONTOSBR'      THEN 'PONTOSBR'
            WHEN code = 'IFO_WE_CLU'    THEN 'IFO_WE_CLU'
            WHEN code = 'IFOOD_RWB'     THEN 'IFOOD_RWB'
            WHEN code = 'IF_MISSION'    THEN 'IF_MISSION'
            WHEN code = 'IF_CAMPAI'     THEN 'IF_CAMPAI'
            WHEN code = 'IFOOD_WELCOME' THEN 'IFOOD_WELCOME'
            WHEN code = 'IFOOD_PROMO'   THEN 'IFOOD_PROMO'
            WHEN code = 'MISSIONS'      THEN 'MISSIONS'
            WHEN code = 'KIDD_FLASH'    THEN 'KIDD_FLASH'
            ELSE 'general'
        END AS tratamiento
    FROM data.lake.clm_point_types
) t
WHERE tratamiento NOT IN ('general', 'SUBSCRIPTION', 'SUBSCRIPTION_INT')
