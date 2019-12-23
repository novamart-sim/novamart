SELECT
    to_char(date_trunc('month', ru."at" AT TIME ZONE 'America/New_York'), 'YYYY-MM') AS month,
    COUNT(*) AS refunds_count,
    ROUND(SUM(ru.amount)::numeric, 2) AS refunds_total
FROM analytics.refunds_unified ru
GROUP BY 1
ORDER BY 1;
