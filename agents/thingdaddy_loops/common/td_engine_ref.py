# ============================================================================
# td_engine_ref.py — REFERENCE ENGINE (STAND-IN, Cycle 2 scaffold).
# This is a COPY of the Level-1 reference engine so the population API has a mint
# seam to shim to (mint_cli.py). It is the MAP, not the product: Pom's
# authoritative engine REPLACES this file behind the same mint() contract. Do
# not build on this as if it were canonical — it exists to prove the seam.
# ============================================================================
#!/usr/bin/env python3
"""
ThingDaddy — ENGINE (Level 1).  The SOLE constructor of URNs.
Pure stdlib. No URN exists except through mint(). Laws enforced here, in code.
"""

# GS1 partition table (gcpDigits -> [partition, gcpBits, refDigits, refBits])
GS1_PARTITION = {12:[0,40,1,4],11:[1,37,2,7],10:[2,34,3,10],9:[3,30,4,14],
                 8:[4,27,5,17],7:[5,24,6,20],6:[6,20,7,24]}

# EPC scheme -> urn body prefix. Note: CPID's URN scheme is lowercase 'cpi'.
SCHEMES = {"giai":"giai","cpid":"cpi","sgtin":"sgtin","sgln":"sgln",
           "gdti":"gdti","sscc":"sscc","grai":"grai","gsrn":"gsrn"}

class MintError(Exception): pass
class CarrierError(Exception): pass
class RefusalError(Exception): pass
class CollisionError(Exception): pass

def _numeric(s):
    return s is not None and str(s).isdigit()

def mint(key, prefix, component, carriers=("RAIN-96","GS1-128","DL"), source="SYNTHETIC"):
    """Mint a URN. R9: generated components numeric. P32: no alpha in the body.
       Carrier gate: RAIN-96 packs the variable part as a number -> must be numeric."""
    if key in ("person","place"):
        raise RefusalError(f"mint_identity_for_{key}() raises. R1/P27.")
    scheme = SCHEMES.get(key)
    if not scheme:
        raise MintError(f"unknown key {key}")
    if not _numeric(prefix):
        raise MintError("prefix must be numeric")
    # CARRIER GATE (R9 + P32 general, binds giai/cpid/gdti alike)
    if "RAIN-96" in carriers and not _numeric(component):
        raise CarrierError(
            f"{key}({component!r}) cannot ride RAIN-96 (96-bit packs the variable "
            f"component as a number). Declare a profile without RAIN-96 to admit alpha.")
    urn = f"urn:epc:id:{scheme}:{prefix}.{component}"
    # P32 GUARD — refuse alpha in a generated id body
    if source not in ("GEPIR","GUDID","ADMITTED"):
        body = urn.split(":")[-1]
        if any(c.isalpha() for c in body):
            raise MintError(f"P32: alpha in generated URN {urn}")
    # self-check: decode(encode(x)) == x
    assert decode(encode(urn)) == urn, "roundtrip broke"
    return urn

def admit(key, prefix, legacy_ids):
    """Naturalise a pre-existing thing. Legacy IDs preserved verbatim (may be alpha),
       kept in the crosswalk, NOT in the graph body. Numeric id minted for the graph."""
    if not legacy_ids:
        raise MintError("admit() requires legacyIds[]")
    urn = mint(key, prefix, str(abs(hash(legacy_ids[0])) % 10_000_000), source="ADMITTED")
    return urn, {"crosswalk":{lid:urn for lid in legacy_ids}}

def encode(urn):  # trivial reversible transform stands in for the tag encoding
    return urn.replace("urn:epc:id:", "TD|")
def decode(tag):
    return tag.replace("TD|", "urn:epc:id:")

def check_digit(numeric):
    """GenSpecs 7.9.1 — weights 3,1,3,1 from the right."""
    d=[int(c) for c in str(numeric)]
    s=sum(v*(3 if (len(d)-i)%2==1 else 1) for i,v in enumerate(d))
    return (10-(s%10))%10

# refusals as callable gates (used by the API)
def adjudicate(*a,**k): raise RefusalError("adjudicate() raises. R3.")
def ratify_by_agent(actor): raise RefusalError(f"ratify by '{actor}' raises. R4.")

if __name__=="__main__":
    # smoke test the laws
    print("mint giai numeric:", mint("giai","0817089","4471"))
    print("mint cpid:", mint("cpid","0817089","10023"))
    try: mint("giai","0817089","INSTR-1")
    except CarrierError as e: print("carrier gate OK:", str(e)[:50])
    try: mint("person","0817089","1")
    except RefusalError as e: print("person refusal OK:", str(e)[:40])
    u,x=admit("giai","0817089",["SAP-4471-B"])
    print("admit:", u, "crosswalk:", list(x["crosswalk"]))
    print("check digit of 081708902352:", check_digit("081708902352"))
    print("ALL ENGINE LAWS GREEN")
