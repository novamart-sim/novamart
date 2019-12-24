-- exec screen widget: total revenue, last 7 calendar days including today
-- report_rows holds completed daily snapshots, while report_rows_intraday holds append-only
-- intraday snapshots for whatever day was "today" when the job ran. That means the two tables
-- overlap on report_date once a day closes and its final totals also land in report_rows, and
-- each table can have multiple created_at versions for the same report_date. To combine them
-- safely, use only the latest report_rows version for prior closed days and only the latest
-- report_rows_intraday version for today.
WITH bounds AS (
  SELECT (now() AT TIME ZONE 'America/New_York')::date AS today
)
SELECT SUM(revenue) AS revenue_7d FROM (
  SELECT SUM(r.revenue) AS revenue
  FROM report_rows r
  JOIN (
    SELECT rr.report_date, MAX(rr.created_at) AS created_at
    FROM report_rows rr
    CROSS JOIN bounds b
    WHERE rr.report_date >= b.today - 6
      AND rr.report_date < b.today
    GROUP BY 1
  ) latest ON latest.report_date = r.report_date AND latest.created_at = r.created_at
  GROUP BY r.report_date

  UNION ALL

  SELECT SUM(r.revenue) AS revenue
  FROM report_rows_intraday r
  JOIN (
    SELECT rr.report_date, MAX(rr.created_at) AS created_at
    FROM report_rows_intraday rr
    CROSS JOIN bounds b
    WHERE rr.report_date = b.today
    GROUP BY 1
  ) latest ON latest.report_date = r.report_date AND latest.created_at = r.created_at
  GROUP BY r.report_date
) t;