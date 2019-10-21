"""Reporting endpoints."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException

from .. import db
from ..constants import BRAND_DENYLIST, EXCLUDED_SKUS, LOCAL_TZ

router = APIRouter()


@router.get("/reports/brands")
async def brand_report(month: str):
    try:
        start_local = datetime.strptime(month, "%Y-%m").replace(tzinfo=ZoneInfo(LOCAL_TZ))
    except ValueError:
        raise HTTPException(status_code=400, detail="month must be YYYY-MM")

    if start_local.month == 12:
        end_local = start_local.replace(year=start_local.year + 1, month=1)
    else:
        end_local = start_local.replace(month=start_local.month + 1)
    start = start_local.astimezone(timezone.utc)
    end = end_local.astimezone(timezone.utc)

    async with db.pool.connection() as conn:
        cur = await db.execute(conn, datetime.now(timezone.utc).isoformat(),
            "SELECT COALESCE(NULLIF(p.brand, ''), 'unbranded') AS brand, "
            "COUNT(*) AS orders, COALESCE(SUM(o.price), 0) AS revenue "
            "FROM orders o JOIN products p ON p.id = o.product_id "
            "WHERE o.created_at >= %s AND o.created_at < %s AND o.status = 1 "
            "AND NOT (o.product_id = ANY(%s)) AND NOT (p.brand = ANY(%s)) "
            "GROUP BY 1 ORDER BY revenue DESC, brand ASC",
            (start, end, EXCLUDED_SKUS, BRAND_DENYLIST))
        rows = await cur.fetchall()

    return {
        "brands": [
            {"brand": brand, "revenue": round(float(revenue), 2), "orders": orders}
            for brand, orders, revenue in rows
        ]
    }
