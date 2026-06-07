"""Look up a product by barcode.

The browser decodes the barcode to a number and sends just that number here;
this module turns it into a product name. Open Food Facts is the only source
for now, but `lookup_product` is deliberately provider-agnostic so a paid
fallback (better US / non-food coverage) can be slotted in later without
touching the callers — only `_lookup_off` (or an added second provider) changes.

No new dependency: the request goes out over stdlib `urllib`, matching how the
rest of the project avoids an HTTP-client dependency (e.g. the Quadlet
healthcheck). The lookup runs inside a sync `def` route, which Starlette offloads
to a threadpool, so the blocking call doesn't stall the event loop.
"""

import json
import re
import urllib.error
import urllib.parse
import urllib.request

# Open Food Facts: free, no API key. We ask for the v2 single-product endpoint.
OFF_URL = "https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
# OFF asks callers to identify themselves with a descriptive User-Agent. No PII,
# just the app name + public repo so they can reach us if we misbehave.
USER_AGENT = (
    "pantryapp/1.0 (LAN kitchen inventory; "
    "+https://github.com/EWH2000/pantryapp)"
)
TIMEOUT_S = 5

# Same barcode gets rescanned often (unpacking a six-pack, re-buying staples),
# so cache lookups for the life of the process. A dict is plenty: the working
# set is tiny, OFF lookups are free, and the worst failure — losing the cache on
# restart — costs one extra HTTP call. A stale product name is harmless.
_cache: dict[str, dict | None] = {}

# A pack/multiplier count in a product name or size string: "6 pack", "12 ct",
# "12 count", "24 x 355 ml". Anchored on pack words and the "N x" multiplier so
# bare numbers and plain sizes ("7 Up", "2 L", "144 oz") never match.
_PACK_RE = re.compile(
    r"(\d{1,3})\s*-?\s*(?:(?:pack|packs|pk|ct|cnt|count)\b|[x×](?=\s*\d))",
    re.IGNORECASE,
)
# One deliberate exception (a household staple): a bare "144 fl oz" total is the
# Diet Coke 12 x 12 case, so count it as 12. We do NOT generalize "divide a total
# volume by a guessed unit size" anywhere else — only this exact total.
_DIET_COKE_144OZ_RE = re.compile(r"\b144\s*(?:fl\.?\s*)?oz\b", re.IGNORECASE)


def parse_pack_count(*texts: str) -> int | None:
    """Best-effort pack/multiplier count from the given strings, or None.

    Matches a number before a pack word (pack/pk/ct/count) or an "N x size"
    multiplier; bare numbers and plain sizes don't match (so "7 Up", "2 L" stay
    None). Plus the one hard-coded 144-fl-oz → 12 exception above. Returns the
    first sane match (2..99); an explicit count anywhere wins over the exception.
    """
    for text in texts:
        m = _PACK_RE.search(text) if text else None
        if m:
            n = int(m.group(1))
            if 2 <= n <= 99:
                return n
    for text in texts:
        if text and _DIET_COKE_144OZ_RE.search(text):
            return 12
    return None


def lookup_product(barcode: str) -> dict | None:
    """Return ``{name, brands, package_size}`` for a barcode, or ``None``.

    Always degrades gracefully: not-found, network error, timeout, and malformed
    JSON all return ``None`` so the caller can still let the user type a name by
    hand (the barcode itself is stored regardless). Provider-agnostic shape —
    extend the body to try a second source before giving up.
    """
    barcode = barcode.strip()
    if not barcode:
        return None
    if barcode in _cache:
        return _cache[barcode]

    result = _lookup_off(barcode)
    _cache[barcode] = result
    return result


def _lookup_off(barcode: str) -> dict | None:
    """Query Open Food Facts. Returns the normalized product dict or None."""
    url = OFF_URL.format(barcode=urllib.parse.quote(barcode))
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None                     # network / timeout / malformed JSON

    if data.get("status") != 1:         # 0 = product not in the database
        return None
    product = data.get("product") or {}
    name = (
        product.get("product_name")
        or product.get("generic_name")
        or product.get("abbreviated_product_name")
        or ""
    ).strip()
    if not name:
        return None                     # barcode known but nameless → treat as unknown
    # OFF's `quantity` is a package-size STRING ("500 g", "1 L", "24 x 355 ml"):
    # a hint, NOT a numeric quantity. But a pack/multiplier count in it (or in the
    # name) is a useful default for the quantity field — parse that out separately.
    size = (product.get("quantity") or "").strip()
    return {
        "name": name,
        "brands": (product.get("brands") or "").strip(),
        "package_size": size,
        "count": parse_pack_count(name, size),   # pack count for qty, or None
    }
