-- daily KPIs (exec dashboard): revenue, orders, active customers
SELECT o.created_at::date AS day,
       COUNT(*)           AS orders,
       SUM(o.price)       AS revenue,
       COUNT(DISTINCT o.user_id) AS active_customers
FROM orders o
WHERE o.created_at >= now() - interval '14 days'
GROUP BY 1
ORDER BY 1 DESC;
