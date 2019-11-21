"""Promo discount helpers used by reporting rollups."""


def apply_discounts(rows, cap=0.40):
    """Apply the promo cap to (product_id, revenue) rows.

    cap: fraction of revenue that promo discounts may reach. Callers
    should pass constants.DISCOUNT_CAP; the default is the legacy cap.
    """
    return [(pid, round(rev * (1 - cap), 2)) for pid, rev in rows]
