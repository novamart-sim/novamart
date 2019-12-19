-- exec screen widget: total revenue, last 7 days including today
SELECT SUM(revenue) AS revenue_7d FROM (
  SELECT revenue FROM report_rows WHERE report_date >= CURRENT_DATE - 7
  UNION ALL
  SELECT revenue FROM report_rows_intraday WHERE report_date >= CURRENT_DATE - 7
) t;
