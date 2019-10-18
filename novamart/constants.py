"""Business constants. Change with care — finance reads the numbers these produce."""

# payment processing fee rate charged on each order
FEE_RATE = 0.029

# products hidden from the daily report (test/internal skus)
EXCLUDED_SKUS = [1004856, 1002544]

# brands hidden from the daily report
BRAND_DENYLIST = []

# order status for cancelled orders
STATUS_CANCELLED = 4

# order statuses the daily report must skip
EXCLUDED_STATUSES = [0]

# how many suspect refs reconcile flags per night
RECONCILE_BATCH = 200

# how many order rows the daily report scans (keeps the job fast)
REPORT_SCAN_CAP = 500

# company timezone (reports and statements are business-local)
LOCAL_TZ = "America/New_York"


