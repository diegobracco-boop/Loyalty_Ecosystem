with accrual as (
SELECT dsp_transaction_id
     , country_code
     , partner
     , sum(points) points
     , point_type
     , business
     , product
     , transaction_code
     , transaction_code_padre
     , country
     , payment_type
     ,CASE
         WHEN channel IN ('viajes-falabella-presencial','viajes-falabella-corporate','vf-presencial-markup','bestday-islas','bestday-islas-markup','tiendas-b2c') THEN 'Sucursales'
         WHEN channel IN ('beneficios-despegar','site','site-smartphone','site-tablet','bestday-site','viajes-falabella-wl','viajes-falabella-viajaya','viajanet-passagens','viajanet-site', 'agencia-exoticca', 'phanton-brand','puntosbonus-pe') THEN 'Site'
         WHEN channel IN ('call-sales-b2c','call-sales-outbound','bestday-call','viajes-falabella-call','viajanet-televentas', 'videollamada-b2c','whatsapp-b2c') THEN 'Call Center'
         WHEN channel IN ('android-app','iphone-app','bestday-app','viajes-falabella-app','viajanet-app') THEN 'App'
         ELSE 'Site' 
       END AS channel_condition
     , trip_type
     , produto_original
     , produto
     , comision
     , fee
     , descuentos
     , gb_basebi
     , gb_basebi_2
     , country||' '||product||' '||business concatenado
     , case
       when business = 'DOMESTIC' then UPPER(country)
       when business = 'INTERNATIONAL' and product = 'FLIGHT' OR product = 'INSURANCE' then UPPER(country) else 'TRAVEL' end as legal_entity
  FROM (select 'Accumulation' file
             , ar.dsp_transaction_id
             , ar.country as country_code
             , ar.partner
             , ar.points
             , ar.point_type
             , ar.business
             , ar.product
             , qr1.transaction_code
             , qr1.transaction_code_padre
             , qr1.country
             , qr1.payment_type
             , qr1.channel
             , qr1.trip_type
             , qr1.produto_original
             , qr1.produto
             , qr1.comision
             , qr1.fee
             , qr1.descuentos
             , qr1.gb_basebi
             , qr1.gb_basebi_2
         from (select ar1.dsp_transaction_id
                    , ar1.country
                    , ar1.partner
                    , sum(ar1.points) points
                    , ar1.point_type
                    , ar1.business
                    , ar1.product
                 from data.lake.comarch_accumulation_report ar1
                where 1=1 
                  and ar1.processing_date >= {{Desde}}
                  and ar1.processing_date <  {{Hasta}}
                  and COALESCE(ar1.dsp_transaction_type,'Nulo') <> 'REFUND'
                  --and ar1.dsp_transaction_id = 164180500 -- se filtra caso
             group by ar1.dsp_transaction_id
                    , ar1.country
                    , ar1.partner
                    , ar1.point_type
                    , ar1.business
                    , ar1.product) ar -- Reporte de acumulacion
           left join (SELECT /*+ PARALLEL(80) */
                             a.transaction_code
                           , null as transaction_code_padre
                           , cast(A.transaction_code as varchar) as transaction_code_2
                           , b.country
                           , a.payment_type
                           , b.channel
                           , a.trip_type
                           , b.purchase_type as produto_original
                           , array_agg(a.product_type) as produto
                           , case
                             when a.product_type = 'Seguros de Autos' then 'INSURANCE'
                             when a.product_type = 'Excursiones' then 'TOUR'
                             when a.product_type = 'Cruceros' then 'ONA'
                             when a.product_type = 'Universal' then 'TICKET'
                             when a.product_type = 'Alquileres' then 'HOTEL'
                             when a.product_type = 'SeaWorld' then 'TICKET'
                             when a.product_type = 'Disney' then 'TICKET'
                             when a.product_type = 'Circuito' then 'TOUR'
                             when a.product_type = 'Tickets' then 'TICKET'
                             when a.product_type = 'Vuelos' then 'FLIGHT'
                             when a.product_type = 'Busch Gardens' then 'TICKET'
                             when a.product_type = 'Hoteles' then 'HOTEL'
                             when a.product_type = 'EspectÃ¡culos' then 'TOUR'
                             when a.product_type = 'Traslados' then 'TRANSFER'
                             when a.product_type = 'Valijas' then 'ONA'
                             when a.product_type = 'Autos' then 'CAR'
                             when a.product_type = 'Asistencia al viajero' then 'INSURANCE'
                             when a.product_type = 'Buses' then 'ONA'
                             else 'N/D' end as product_type_qr1
                           , sum(CAST((commission+flight_over+flight_markup) as decimal(18,2))) as comision
                           , sum(cast((fee + flight_du) as decimal(18,2))) as fee
                           , sum(cast(discount as decimal(18,2)))*-1 as descuentos
                           , sum(cast(total as decimal(18,2))) as GB_baseBI
                           , sum(cast(gross_booking as decimal(18,2))) as GB_baseBI_2
                       from (select *
                               from data.analytics.bi_transactional_fact_products
                              ) A
                         left join (select * from data.analytics.bi_transactional_fact_transactions where reservation_year_month > cast ('2019-01-01' as date)) B on A.transaction_code = B.transaction_code
                         left join (select * from data.analytics.bi_transactional_fact_charges where reservation_year_month > cast ('2019-01-01' as date)) C on (cast(A.transaction_code as varchar))||A.product_id = (cast(C.transaction_code as varchar))||C.product_id
                     where
                      a.reservation_year_month>= cast ('2023-01-01' as date)
                      group by a.transaction_code
                             , cast(A.transaction_code as varchar)
                             , b.country
                             , a.payment_type
                             , b.channel
                             , a.trip_type
                             , b.purchase_type
                             , case
                               when a.product_type = 'Seguros de Autos' then 'INSURANCE'
                               when a.product_type = 'Excursiones' then 'TOUR'
                               when a.product_type = 'Cruceros' then 'ONA'
                               when a.product_type = 'Universal' then 'TICKET'
                               when a.product_type = 'Alquileres' then 'HOTEL'
                               when a.product_type = 'SeaWorld' then 'TICKET'
                               when a.product_type = 'Disney' then 'TICKET'
                               when a.product_type = 'Circuito' then 'TOUR'
                               when a.product_type = 'Tickets' then 'TICKET'
                               when a.product_type = 'Vuelos' then 'FLIGHT'
                               when a.product_type = 'Busch Gardens' then 'TICKET'
                               when a.product_type = 'Hoteles' then 'HOTEL'
                               when a.product_type = 'EspectÃ¡culos' then 'TOUR'
                               when a.product_type = 'Traslados' then 'TRANSFER'
                               when a.product_type = 'Valijas' then 'ONA'
                               when a.product_type = 'Autos' then 'CAR'
                               when a.product_type = 'Asistencia al viajero' then 'INSURANCE'
                               when a.product_type = 'Buses' then 'ONA'
                               else 'N/D' end) QR1 on (cast(ar.dsp_transaction_id as varchar))||ar.product = (cast(QR1.transaction_code as varchar))||QR1.product_type_qr1
        union all
        select 'Cancellation' file
             , cr.dsp_transaction_id
             , cr.country  as country_code
             , cr.partner
             , (cr.points * -1) points
             , cr.point_type
             , cr.business
             , cr.product
             , qr1.transaction_code
             , qr1.transaction_code_padre
             , qr1.country
             , qr1.payment_type
             , qr1.channel
             , qr1.trip_type
             , qr1.produto_original
             , qr1.produto
             , qr1.comision
             , qr1.fee
             , qr1.descuentos
             , qr1.gb_basebi
             , qr1.gb_basebi_2
         from (select cr1.dsp_transaction_id
                    , cr1.country
                    , cr1.partner
                    , sum(cr1.points) points
                    , cr1.point_type
                    , cr1.business
                    , cr1.product
                 from data.lake.comarch_cancellation_report cr1
                where 1=1
                  and cr1.generation_date >= {{Desde}}
                  and cr1.generation_date <  {{Hasta}}
                  --and cr1.dsp_transaction_id = 164180500 -- se filtra caso
             group by cr1.dsp_transaction_id
                    , cr1.country
                    , cr1.partner
                    , cr1.point_type
                    , cr1.business
                    , cr1.product) cr -- Reporte de cancelacion
    left join (SELECT /*+ PARALLEL(80) */
                      a.transaction_code
                    , null as transaction_code_padre
                    , cast(A.transaction_code as varchar) as transaction_code_2
                    , b.country
                    , a.payment_type
                    , b.channel
                    , a.trip_type
                    , b.purchase_type as produto_original
                    , array_agg(a.product_type) as produto
                    , case
                      when a.product_type = 'Seguros de Autos' then 'INSURANCE'
                      when a.product_type = 'Excursiones' then 'TOUR'
                      when a.product_type = 'Cruceros' then 'ONA'
                      when a.product_type = 'Universal' then 'TICKET'
                      when a.product_type = 'Alquileres' then 'HOTEL'
                      when a.product_type = 'SeaWorld' then 'TICKET'
                      when a.product_type = 'Disney' then 'TICKET'
                      when a.product_type = 'Circuito' then 'TOUR'
                      when a.product_type = 'Tickets' then 'TICKET'
                      when a.product_type = 'Vuelos' then 'FLIGHT'
                      when a.product_type = 'Busch Gardens' then 'TICKET'
                      when a.product_type = 'Hoteles' then 'HOTEL'
                      when a.product_type = 'EspectÃ¡culos' then 'TOUR'
                      when a.product_type = 'Traslados' then 'TRANSFER'
                      when a.product_type = 'Valijas' then 'ONA'
                      when a.product_type = 'Autos' then 'CAR'
                      when a.product_type = 'Asistencia al viajero' then 'INSURANCE'
                      when a.product_type = 'Buses' then 'ONA'
                      else 'N/D' end as product_type_qr1
                    , sum(CAST((commission+flight_over+flight_markup) as decimal(18,2))) as comision
                    , sum(cast((fee + flight_du) as decimal(18,2))) as fee
                    , sum(cast(discount as decimal(18,2)))*-1 as descuentos
                    , sum(cast(total as decimal(18,2))) as GB_baseBI
                    , sum(cast(gross_booking as decimal(18,2))) as GB_baseBI_2
                from (select * from data.analytics.bi_transactional_fact_products) A
                  left join (select * from data.analytics.bi_transactional_fact_transactions where reservation_year_month > cast ('2019-01-01' as date)) B on A.transaction_code = B.transaction_code
                  left join (select * from  data.analytics.bi_transactional_fact_charges where reservation_year_month > cast ('2019-01-01' as date)) C on (cast(A.transaction_code as varchar))||A.product_id = (cast(C.transaction_code as varchar))||C.product_id
                    where
                    a.reservation_year_month>= cast ('2023-01-01' as date)
                    group by a.transaction_code
                           , cast(A.transaction_code as varchar)
                           , b.country
                           , a.payment_type
                           , b.channel
                           , a.trip_type
                           , b.purchase_type
                           , case when a.product_type = 'Seguros de Autos' then 'INSURANCE'
                             when a.product_type = 'Excursiones' then 'TOUR'
                             when a.product_type = 'Cruceros' then 'ONA'
                             when a.product_type = 'Universal' then 'TICKET'
                             when a.product_type = 'Alquileres' then 'HOTEL'
                             when a.product_type = 'SeaWorld' then 'TICKET'
                             when a.product_type = 'Disney' then 'TICKET'
                             when a.product_type = 'Circuito' then 'TOUR'
                             when a.product_type = 'Tickets' then 'TICKET'
                             when a.product_type = 'Vuelos' then 'FLIGHT'
                             when a.product_type = 'Busch Gardens' then 'TICKET'
                             when a.product_type = 'Hoteles' then 'HOTEL'
                             when a.product_type = 'EspectÃ¡culos' then 'TOUR'
                             when a.product_type = 'Traslados' then 'TRANSFER'
                             when a.product_type = 'Valijas' then 'ONA'
                             when a.product_type = 'Autos' then 'CAR'
                             when a.product_type = 'Asistencia al viajero' then 'INSURANCE'
                             when a.product_type = 'Buses' then 'ONA'
                             else 'N/D'end) QR1 on (cast(cr.dsp_transaction_id as varchar))||cr.product = (cast(qr1.transaction_code as varchar))||qr1.product_type_qr1)
group by dsp_transaction_id
       , country_code
       , partner
       , point_type
       , business
       , product
       , transaction_code
       , transaction_code_padre
       , country
       , payment_type
       , channel
       , trip_type
       , produto_original
       , produto
       , comision
       , fee
       , descuentos
       , gb_basebi
       , gb_basebi_2)
    SELECT --COUNT(partner) AS Total_Registros,
     --country_code,
     --partner,
     SUM(Points) AS Total_Puntos
FROM accrual 
--group by 1,2