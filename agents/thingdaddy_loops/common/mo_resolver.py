"""
mo_resolver.py — GS1 Prefix -> issuing Member Organization, and country -> routing MO.

The GS1 Prefix (leading digits of a GS1 Company Prefix) identifies the GS1 Member
Organization that ISSUED the prefix, not the country of origin. For 12-digit GTINs/UPCs
there is an implied leading zero, applied here before resolution.

Ranges seeded from the public GS1 Prefix list (gs1.org/standards/id-keys/company-prefix).
The seed covers the well-known allocations; replace data/gs1_prefix_ranges.csv with the
full official table for production. Non-MO ranges (restricted circulation, coupons,
bookland) are typed so they are excluded from company matching.
"""
import csv, os

_RANGES = None
_MO_DIR = None
DATA = os.path.join(os.path.dirname(__file__), "data")

def _load_ranges():
    global _RANGES
    if _RANGES is None:
        _RANGES = []
        with open(os.path.join(DATA, "gs1_prefix_ranges.csv")) as f:
            for r in csv.DictReader(f):
                _RANGES.append((int(r["lo"]), int(r["hi"]), r["type"], r["mo"]))
    return _RANGES

def _load_mo_dir():
    global _MO_DIR
    if _MO_DIR is None:
        _MO_DIR = {}
        with open(os.path.join(DATA, "gs1_mo_directory.csv")) as f:
            for r in csv.DictReader(f):
                _MO_DIR[r["country"].upper()] = r["mo"]
    return _MO_DIR

def normalize_to_gtin13(value):
    """Strip non-digits; apply implied leading zero for 12-digit values."""
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    if len(digits) == 12:          # UPC-A -> GTIN-13
        digits = "0" + digits
    if len(digits) == 14:          # GTIN-14 -> drop indicator
        digits = digits[1:]
    return digits

def gs1_prefix_of(company_prefix):
    """Return the 3-digit GS1 Prefix used for MO resolution."""
    digits = normalize_to_gtin13(company_prefix)
    return digits[:3] if len(digits) >= 3 else None

def mo_for_prefix(company_prefix):
    """(mo, type). type=='MO' means a real issuing MO; otherwise special/non-company."""
    gp = gs1_prefix_of(company_prefix)
    if gp is None:
        return (None, "unknown")
    n = int(gp)
    for lo, hi, typ, mo in _load_ranges():
        if lo <= n <= hi:
            return (mo, typ)
    return (None, "reserved")

def mo_for_country(country):
    """Routing MO for a needs-prefix entity, by country of formation."""
    d = _load_mo_dir()
    c = (country or "").upper()
    if c in d:
        return d[c]
    return f"GS1 {c} (resolve via GS1 MO directory)" if c else "GS1 Global Office (unrouted)"
