WITH points AS (
    SELECT
        cm.ext_country_program                      AS Country,
        trxp.account_id,
        date_format(trx.transaction_date, '%m-%Y')  AS Expiration_Date,
        trxp.source_transaction_id,
        trxp.points_type_id,
        pt.code,
        trxp.points
    FROM data.lake.clm_transactions trx
    INNER JOIN data.lake.clm_transaction_points trxp
        ON trx.id = trxp.source_transaction_id
    INNER JOIN data.lake.clm_customers cm
        ON trx.account_id = cm.account_id
    INNER JOIN data.lake.clm_point_types pt
        ON trxp.points_type_id = pt.id
    WHERE trx.transaction_type = 'PE'
),

categoria AS (
    SELECT
        c.account_id,
        a.customer_id,
        a.start_date,
        CASE
            WHEN a.recognition_tier_id = 2352 THEN 'Viajero'
            WHEN a.recognition_tier_id = 2353 THEN 'Explorador'
            WHEN a.recognition_tier_id = 2354 THEN 'Global'
        END AS tier
    FROM (
        SELECT
            customer_id,
            MAX(recognition_tier_id) AS recognition_tier_id,
            start_date
        FROM data.lake.clm_account_recognition_levels
        WHERE (end_date IS NULL OR end_date > DATE(NOW()))
        GROUP BY customer_id, start_date
    ) a
    INNER JOIN data.lake.clm_customers c
        ON a.customer_id = c.id
    INNER JOIN (
        SELECT
            customer_id,
            MAX(start_date) AS start_date
        FROM data.lake.clm_account_recognition_levels
        WHERE (end_date IS NULL OR end_date > DATE(NOW()))
        GROUP BY customer_id
    ) b ON a.customer_id = b.customer_id
       AND a.start_date  = b.start_date
),

final AS (
    SELECT
        a.Expiration_Date,
        a.Country,
        a.account_id,
        b.tier,
        SUM(a.points) * -1 AS Points
    FROM points a
    LEFT JOIN categoria b ON a.account_id = b.account_id
    WHERE a.points_type_id NOT IN (2751, 2801, 2901, 2953, 2954, 3001, 3002, 3003, 3004, 3101, 3102, 3103, 3051, 3151)
    GROUP BY
        a.Expiration_Date,
        a.Country,
        a.account_id,
        b.tier
    ORDER BY 1, 2, 3
)

SELECT SUM(Points) AS total_points
FROM final
