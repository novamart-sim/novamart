-- best sellers, last 7 days (exec dashboard)
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
SELECT io.product_id, COUNT(*) AS units, SUM(io.price) AS revenue
FROM item_orders io
WHERE io.created_at >= now() - interval '7 days'
  AND io.user_id <> 424242
GROUP BY io.product_id
ORDER BY revenue DESC
LIMIT 20;
