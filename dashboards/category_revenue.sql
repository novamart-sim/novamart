-- revenue by category display group, last 30 days (exec dashboard)
SELECT COALESCE(cn.display_group, 'other') AS display_group,
       COUNT(*)                            AS units,
       SUM(o.price)                        AS revenue
FROM orders o
JOIN products p ON p.id = o.product_id
LEFT JOIN LATERAL (
  SELECT c.display_group
  FROM analytics.category_names c
  WHERE c.code = COALESCE(p.category, '')
    AND c.valid_from <= o.created_at::date
  ORDER BY c.valid_from DESC
  LIMIT 1
) cn ON true
WHERE o.created_at >= now() - interval '30 days'
  AND o.user_id <> 424242
GROUP BY 1
ORDER BY revenue DESC;
