-- revenue by brand, last 30 days (exec dashboard)
WITH item_orders AS (
  SELECT o.user_id, ol.product_id, ol.price, ol.created_at
  FROM orders o
  JOIN order_lines ol ON ol.order_id = o.id

  UNION ALL

  SELECT o.user_id, o.product_id, o.price, o.created_at
  FROM orders o
  WHERE NOT EXISTS (
    SELECT 1
    FROM order_lines ol
    WHERE ol.order_id = o.id
  )
)
SELECT p.brand, COUNT(*) AS units, SUM(io.price) AS revenue
FROM item_orders io
JOIN products p ON p.id = io.product_id
WHERE io.created_at >= now() - interval '30 days'
  AND io.user_id::text NOT IN ('424242', 'cc27b436-d6f9-4e84-adaf-e716025dd369')
  AND p.brand NOT IN ('lucente', 'jetem')
GROUP BY p.brand
ORDER BY revenue DESC;
