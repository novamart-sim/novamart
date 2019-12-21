-- conversion for registered (accounts beta) customers
-- NOTE: there are two customer id namespaces here:
--   * orders.user_id / users.id = legacy numeric shopper id used on historical orders
--   * accounts.account_id     = new UUID account id for the registered-accounts beta
-- These ids are not comparable/castable to each other. To count a registered customer's
-- full order history (including pre-enrollment orders), map accounts to users via the
-- shared email first, then join orders on the legacy numeric user_id.
WITH registered_users AS (
  SELECT DISTINCT u.id AS user_id
  FROM accounts a
  JOIN users u ON u.email = a.email
)
SELECT COUNT(DISTINCT o.user_id) AS registered_buyers,
       SUM(o.price)              AS registered_revenue
FROM orders o
JOIN registered_users ru ON ru.user_id = o.user_id
WHERE o.status = 1;
