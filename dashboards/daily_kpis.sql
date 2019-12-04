-- daily KPIs (exec dashboard): revenue, orders, active customers, contactable customers
SELECT o.created_at::date AS day,
       COUNT(*)           AS orders,
       SUM(o.price)       AS revenue,
       COUNT(DISTINCT o.user_id) AS active_customers,
       COUNT(DISTINCT cu.user_id) AS contactable_customers
FROM orders o
LEFT JOIN analytics.contactable_users cu ON cu.user_id = o.user_id
WHERE o.created_at >= now() - interval '14 days'
  AND o.user_id <> 424242
GROUP BY 1
ORDER BY 1 DESC;
