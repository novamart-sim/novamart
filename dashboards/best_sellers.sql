-- best sellers, last 7 days (exec dashboard)
SELECT o.product_id, COUNT(*) AS units, SUM(o.price) AS revenue
FROM orders o
WHERE o.created_at >= now() - interval '7 days'
  AND o.user_id <> 424242
GROUP BY o.product_id
ORDER BY revenue DESC
LIMIT 20;
