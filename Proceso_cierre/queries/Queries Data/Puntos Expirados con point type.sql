with points as (
select cm.ext_country_program as Country,
       trxp.account_id,
       date_format(trx.transaction_date, '%m-%Y') as Expiration_Date,
       trxp.source_transaction_id,
       trxp.points_type_id,
       pt.code,
       trxp.points
from data.lake.clm_transactions trx
inner join data.lake.clm_transaction_points trxp on trx.id = trxp.source_transaction_id
inner join data.lake.clm_customers cm on trx.account_id = cm.account_id
inner join data.lake.clm_point_types pt on trxp.points_type_id = pt.id
where trx.transaction_type = 'PE'
and trxp.points_type_id NOT IN (2751, 2801, 2901, 2953, 2954, 3001, 3002, 3003, 3004,3051, 3101, 3102, 3103,3151)
group by 1,2,3,4,5,6,7
),

categoria as (
select c.account_id,
       a.customer_id,
       a.start_date,
       case when a.recognition_tier_id = 2352 then 'Viajero'
            when a.recognition_tier_id = 2353 then 'Explorador'
            when a.recognition_tier_id = 2354 then 'Global'
       end as tier
from (select customer_id,
             max(recognition_tier_id) as recognition_tier_id,
             start_date 
      from data.lake.clm_account_recognition_levels
      where (end_date is null or end_date > date(now()))
      group by customer_id,
               start_date) a
inner join data.lake.clm_customers c on a.customer_id = c.id
inner join (select customer_id, 
                   max(start_date) as start_date
            from data.lake.clm_account_recognition_levels
            where (end_date is null or end_date > date(now()))
            group by customer_id) b on a.customer_id = b.customer_id and a.start_date = b.start_date
)

select Expiration_Date,
       country,
       --a.account_id,
       tier,
       points_type_id,
       sum(points) * -1 as Points
from points a
left join categoria b on a.account_id = b.account_id 
group by Expiration_Date,
         Country,
         --a.account_id,
         tier,
         points_type_id
order by 1,2,3,4


