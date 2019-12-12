-- revenue by category display group, last 30 days (exec dashboard)
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
),
category_mapping AS (
  SELECT c.code, c.display_group, c.valid_from, 0 AS source_priority
  FROM analytics.category_names c

  UNION ALL

  SELECT c.code, c.display_group, c.valid_from, 1 AS source_priority
  FROM analytics.category_name_history c
)
SELECT COALESCE(cn.display_group, 'other') AS display_group,
       COUNT(*)                             AS units,
       SUM(io.price)                        AS revenue
FROM item_orders io
JOIN products p ON p.id = io.product_id
LEFT JOIN LATERAL (
  SELECT c.display_group
  FROM category_mapping c
  WHERE c.code = COALESCE(p.category, '')
    AND c.valid_from <= io.created_at::date
  ORDER BY c.valid_from DESC, c.source_priority DESC
  LIMIT 1
) cn ON true
WHERE io.created_at >= now() - interval '30 days'
  AND io.user_id <> 424242
GROUP BY 1
ORDER BY revenue DESC;