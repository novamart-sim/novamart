-- revenue by brand, last 30 days (exec dashboard)
SELECT p.brand, COUNT(*) AS units, SUM(o.price) AS revenue
FROM orders o
JOIN products p ON p.id = o.product_id
WHERE o.created_at >= now() - interval '30 days'
GROUP BY p.brand
ORDER BY revenue DESC;
