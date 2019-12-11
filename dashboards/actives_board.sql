-- active customers for the board deck
-- Definition: distinct users with at least one non-cancelled order in the last 30 days.
-- To keep this honest, exclude known QA smoke-test accounts in analytics.test_users and
-- users whose email looks internal or obviously fake/test-like (novamart, example/test,
-- or localparts/domains tagged qa/test/demo/internal/seed/sandbox/smoke).
WITH candidate_users AS (
  SELECT DISTINCT o.user_id
  FROM orders o
  WHERE o.created_at >= now() - interval '30 days'
    AND NOT (o.status = ANY (ARRAY[0, 2, 3]))
    AND o.user_id IS NOT NULL
)
SELECT COUNT(*) AS active_customers
FROM candidate_users cu
LEFT JOIN analytics.test_users tu ON tu.user_id = cu.user_id
LEFT JOIN users u ON u.id = cu.user_id
WHERE tu.user_id IS NULL
  AND NOT (
    COALESCE(lower(split_part(u.email, '@', 2)), '') IN ('novamart.com', 'example.com', 'example.net', 'example.org')
    OR COALESCE(lower(split_part(u.email, '@', 2)), '') LIKE '%.example'
    OR COALESCE(lower(split_part(u.email, '@', 2)), '') LIKE '%.test'
    OR COALESCE(lower(split_part(u.email, '@', 2)), '') LIKE 'internal.%'
    OR COALESCE(lower(split_part(u.email, '@', 2)), '') LIKE 'test.%'
    OR COALESCE(lower(split_part(u.email, '@', 1)), '') ~ '(^|[._+-])(qa|test|demo|internal|seed|sandbox|smoke)($|[._+-])'
    OR COALESCE(lower(split_part(u.email, '@', 2)), '') ~ '(^|[.-])(qa|test|demo|internal|seed|sandbox)($|[.-])'
  );