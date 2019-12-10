-- conversion for registered (accounts beta) customers
-- FIXME(dec): numbers look low
SELECT COUNT(DISTINCT o.user_id) AS registered_buyers,
       SUM(o.price)              AS registered_revenue
FROM orders o
JOIN accounts a ON a.account_id::text = o.user_id::text
WHERE o.status = 1;
