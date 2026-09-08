"""
verify.py — deterministic verify gates. These are plain functions, never a model
judgment. Every record leaves a gate stamped verified | candidate | exception.

  verified   : an authoritative source resolves the value
               (Verified by GS1 confirms prefix + licensee + length)
  candidate  : a value derived but not yet confirmed
               (a prefix derived from a GUDID/openFDA GTIN via GCP length) — never auto-promoted
  exception  : no resolving source; held open and visible, never fabricated
"""

def verify_prefix(derived_source, vbg_confirm):
    """
    derived_source: where the candidate prefix came from ('gudid','openfda','manual',...)
    vbg_confirm:    dict from Verified by GS1 if it confirmed this prefix, else None
                    expected keys: licensee, length, country
    Returns (status, length, citation).
    """
    if vbg_confirm:
        cite = f"VbG:{vbg_confirm.get('licensee','?')}|len={vbg_confirm.get('length','?')}"
        return ("verified", vbg_confirm.get("length"), cite)
    if derived_source in ("gudid", "openfda"):
        return ("candidate", None, f"derived:{derived_source}")
    return ("exception", None, "no_source")


def verify_match(score, corroborated, strong=0.90, probable=0.75):
    """
    score:        0..1 name/identity similarity
    corroborated: True if an authoritative record backs the pairing (e.g. VbG licensee)
    Returns (tier, status).
      strong + corroborated -> verified
      strong (no corrob)     -> candidate
      probable               -> candidate
      below probable         -> exception (not written as a bridge)
    """
    if score >= strong:
        tier = "strong"
    elif score >= probable:
        tier = "probable"
    else:
        tier = "weak"
    if tier == "strong" and corroborated:
        return (tier, "verified")
    if tier in ("strong", "probable"):
        return (tier, "candidate")
    return (tier, "exception")


def verify_edge(src_status, dst_status, source_authoritative=True):
    """
    Edge status from endpoint resolution + source authority.
      both endpoints resolved to known profiles + authoritative source -> verified
      authoritative source but one endpoint provisional/unresolved       -> candidate
      otherwise                                                          -> exception
    All three Loop B sources (SEC EDGAR EX-21, USASpending awards, SAM.gov
    registrations) are authoritative public disclosures, so status turns on whether
    both endpoints resolve to a known civilization profile.
    """
    resolved = {"resolved", "verified"}
    if not source_authoritative:
        return "exception"
    if src_status in resolved and dst_status in resolved:
        return "verified"
    if src_status in resolved or dst_status in resolved:
        return "candidate"
    return "exception"
