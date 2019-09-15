"""Onboarding profiles: the attributes a signup / product-listing form captures.

The storefront only relays ids, so these are synthesized deterministically from
the id (every worker computes the same values, no coordination needed) — same
idiom as the placeholder email. Downstream jobs treat them as ordinary columns.
"""
import hashlib

FIRST_NAMES = ["aarav", "diya", "kabir", "meera", "rohan", "anaya", "vivaan", "isha",
               "arjun", "sara", "dev", "nisha", "kian", "tara", "veer", "priya"]
LAST_NAMES = ["sharma", "patel", "rao", "gupta", "khan", "iyer", "das", "mehta",
              "singh", "nair", "bose", "shah", "kulkarni", "verma", "menon", "joshi"]
REGIONS = ["north", "south", "east", "west", "central", "northeast"]
CHANNELS = ["organic", "google_ads", "facebook", "referral", "influencer", "email"]
DEVICES = ["android", "ios", "web"]
AGE_BANDS = ["18-24", "25-34", "35-44", "45-54", "55+"]
VENDORS = ["acme-supplies", "globex-trading", "initech-goods", "umbrella-retail",
           "stark-imports", "wayne-wholesale", "hooli-direct", "pied-piper-co"]


def _h(*parts) -> int:
    return int(hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:8], 16)


def user_profile(uid: int) -> dict:
    """Signup-form attributes, deterministic per user id."""
    return {
        "name": f"{FIRST_NAMES[_h(uid, 'f') % len(FIRST_NAMES)]} "
                f"{LAST_NAMES[_h(uid, 'l') % len(LAST_NAMES)]}",
        "region": REGIONS[_h(uid, "r") % len(REGIONS)],
        "signup_channel": CHANNELS[_h(uid, "c") % len(CHANNELS)],
        "device": DEVICES[_h(uid, "d") % len(DEVICES)],
        "age_band": AGE_BANDS[_h(uid, "a") % len(AGE_BANDS)],
        "marketing_opt_in": _h(uid, "m") % 100 < 62,
    }


def product_profile(pid: int, category: str, brand: str, price: float) -> dict:
    """Listing-form attributes, deterministic per product id."""
    leaf = (category or "").split(".")[-1] or "item"
    label = f"{(brand or 'unbranded').title()} {leaf.title()} #{pid % 10000}"
    margin = 0.55 + (_h(pid, "mg") % 26) / 100.0          # cost = 55-80% of price
    return {
        "title": label,
        "vendor": VENDORS[_h(pid, "v") % len(VENDORS)],
        "cost_price": round(float(price or 0.0) * margin, 2),
        "stock": 20 + _h(pid, "s") % 481,                  # 20-500 units on hand
    }
