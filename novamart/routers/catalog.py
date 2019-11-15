"""Catalog: product views and the vendor price feed."""
from fastapi import APIRouter

from .. import db
from ..logutil import app_log
from ..onboarding import product_profile, user_profile

router = APIRouter()

_known_users: set = set()
_known_products: set = set()

USER_INSERT = ("INSERT INTO users(id, email, name, region, signup_channel, device, "
               "age_band, marketing_opt_in, created_at) "
               "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING")
PRODUCT_INSERT = ("INSERT INTO products(id, title, category, brand, vendor, list_price, "
                  "cost_price, stock, created_at) "
                  "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING")
PRODUCT_UPSERT = ("INSERT INTO products(id, title, category, brand, vendor, list_price, "
                  "cost_price, stock, created_at) "
                  "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                  "ON CONFLICT (id) DO UPDATE SET "
                  "title = CASE WHEN COALESCE(EXCLUDED.title, '') <> '' THEN EXCLUDED.title "
                  "ELSE products.title END, "
                  "category = CASE WHEN COALESCE(EXCLUDED.category, '') <> '' THEN EXCLUDED.category "
                  "ELSE products.category END, "
                  "brand = CASE WHEN COALESCE(EXCLUDED.brand, '') <> '' THEN EXCLUDED.brand "
                  "ELSE products.brand END, "
                  "vendor = CASE WHEN COALESCE(EXCLUDED.vendor, '') <> '' THEN EXCLUDED.vendor "
                  "ELSE products.vendor END, "
                  "list_price = EXCLUDED.list_price, cost_price = EXCLUDED.cost_price, "
                  "stock = EXCLUDED.stock")
PRICE_HISTORY_INSERT = ("INSERT INTO analytics.price_history(product_id, list_price, valid_from) "
                        "VALUES(%s,%s,%s)")
PRODUCT_BRAND_REPAIR = ("UPDATE products SET brand = %s, title = %s "
                        "WHERE id = %s AND COALESCE(brand, '') = '' AND %s <> ''")


def _user_row(uid, ts):
    p = user_profile(uid)
    return (uid, f"user{uid}@example.com", p["name"], p["region"], p["signup_channel"],
            p["device"], p["age_band"], p["marketing_opt_in"], ts)


def _product_row(pid, category, brand, price, ts):
    p = product_profile(pid, category, brand, price)
    return (pid, p["title"], category, brand, p["vendor"], price, p["cost_price"],
            p["stock"], ts)


async def _repair_product_brand(conn, ts, pid, category, brand, price):
    if not brand:
        return
    title = product_profile(pid, category, brand, price)["title"]
    await db.execute(conn, ts, PRODUCT_BRAND_REPAIR, (brand, title, pid, brand))


async def ensure_entities(conn, ts, uid, pid, price):
    """Create user/product rows on first sight (cheap MVP bootstrap)."""
    if uid not in _known_users:
        await db.execute(conn, ts, USER_INSERT, _user_row(uid, ts))
        _known_users.add(uid)
    if pid not in _known_products:
        await db.execute(conn, ts, PRODUCT_INSERT, _product_row(pid, "", "", price, ts))
        _known_products.add(pid)


@router.get("/products/{pid}")
async def view_product(pid: int, uid: int, ts: str, session: str,
                       price: float = 0.0, category: str = "", brand: str = ""):
    async with db.pool.connection() as conn:
        if uid not in _known_users:
            await db.execute(conn, ts, USER_INSERT, _user_row(uid, ts))
            _known_users.add(uid)
        if pid not in _known_products:
            await db.execute(conn, ts, PRODUCT_INSERT,
                             _product_row(pid, category, brand, price, ts))
            _known_products.add(pid)
        await _repair_product_brand(conn, ts, pid, category, brand, price)
    app_log(ts, "INFO", "product_viewed", user_id=uid, product_id=pid, session=session)
    return {"ok": True}


@router.post("/catalog/prices")
async def price_feed(body: dict):
    """Vendor price feed: upsert product prices in bulk."""
    ts = body["ts"]
    items = body.get("items", [])
    async with db.pool.connection() as conn:
        for it in items:
            await db.execute(conn, ts, PRICE_HISTORY_INSERT,
                             (it["product_id"], it["list_price"], ts))
            await db.execute(conn, ts, PRODUCT_UPSERT,
                             _product_row(it["product_id"], it.get("category", ""),
                                          it.get("brand", ""), it["list_price"], ts))
            await _repair_product_brand(conn, ts, it["product_id"], it.get("category", ""),
                                        it.get("brand", ""), it["list_price"])
    app_log(ts, "INFO", "price_feed_received", source=body.get("source", "unknown"), items=len(items))
    return {"accepted": len(items)}
