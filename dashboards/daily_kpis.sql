-- daily KPIs (exec dashboard): revenue, orders, active customers, contactable customers
WITH bounds AS (
  SELECT (now() AT TIME ZONE 'America/New_York')::date AS today
),
report_days AS (
  SELECT r.report_date AS day,
         SUM(r.units) AS orders,
         SUM(r.revenue) AS revenue
  FROM report_rows r
  JOIN (
    SELECT rr.report_date, MAX(rr.created_at) AS created_at
    FROM report_rows rr
    CROSS JOIN bounds b
    WHERE rr.report_date >= b.today - 13
      AND rr.report_date < b.today
    GROUP BY 1
  ) latest ON latest.report_date = r.report_date AND latest.created_at = r.created_at
  GROUP BY 1

  UNION ALL

  SELECT r.report_date AS day,
         SUM(r.units) AS orders,
         SUM(r.revenue) AS revenue
  FROM report_rows_intraday r
  JOIN (
    SELECT rr.report_date, MAX(rr.created_at) AS created_at
    FROM report_rows_intraday rr
    CROSS JOIN bounds b
    WHERE rr.report_date = b.today
    GROUP BY 1
  ) latest ON latest.report_date = r.report_date AND latest.created_at = r.created_at
  GROUP BY 1
),
customer_days AS (
  SELECT (o.created_at AT TIME ZONE 'America/New_York')::date AS day,
         COUNT(DISTINCT o.user_id) AS active_customers,
         COUNT(DISTINCT cu.user_id) AS contactable_customers
  FROM orders o
  LEFT JOIN analytics.contactable_users cu ON cu.user_id = o.user_id
  CROSS JOIN bounds b
  WHERE o.created_at >= ((b.today - 13)::timestamp AT TIME ZONE 'America/New_York')
    AND o.user_id <> 424242
  GROUP BY 1
)
SELECT rd.day,
       rd.orders,
       rd.revenue,
       COALESCE(cd.active_customers, 0) AS active_customers,
       COALESCE(cd.contactable_customers, 0) AS contactable_customers
FROM report_days rd
LEFT JOIN customer_days cd ON cd.day = rd.day
ORDER BY 1 DESC;
