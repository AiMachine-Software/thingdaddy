#!/usr/bin/env python3
"""
ThingDaddy Agent Fleet - runnable scaffolding
=============================================
An executable home for the TD-A agent fleet (TD-A-00..32). Mirrors the Agent
Builder Registry and runs the core loops offline, end to end:

    Master Orchestrator (TD-A-00)
        - Population Loop : Population Agent (TD-A-05) + Source Connectors (TD-A-06)
                            -> Dedupe & Merge (TD-A-07) -> staged candidates
        - Verify Loop     : Verification Agent (TD-A-09) + Exception Gate (TD-A-10)
                            -> verified | exception
        - Register Loop   : Role Deriver (TD-A-13) -> Register Agent (TD-A-12)
                            -> confirm prefix, mint GLN, set root  [the addParty() gate]

Every agent carries a GSRN passport (TD-A-01) and is governed by
verified-or-exception. NOTHING mints without a confirmed prefix + authority.
The registration step is the single gate - the Python analogue of the
platform's addParty(). Run ledger + audit events are written to JSON so a
"designed/planned" agent has a real, inspectable execution trace.

No network required: source connectors read an offline seed (or a CSV you
supply). Swap in live GEPIR/GDSN/GUDID/GLEIF calls where marked TODO(live).

Usage:
    python thingdaddy_agent_fleet.py                 # run built-in Samsung seed
    python thingdaddy_agent_fleet.py hits.csv        # run against your CSV
    python thingdaddy_agent_fleet.py --status        # print fleet status table
"""

from __future__ import annotations
import csv, json, re, sys, uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent.parent / "data"
LEDGER  = OUT_DIR / "agent_fleet_run_ledger.json"

def now() -> str:
    return datetime.now(timezone.utc).isoformat()

def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"

# ── GSRN passport - every agent carries one (TD-A-01 Agent Passport Issuer) ──
TD_SERVICE_PREFIX = "0DEMOTDA"
def agent_gsrn(agent_id: str) -> str:
    n = re.sub(r"[^0-9]", "", agent_id).rjust(4, "0")
    return f"urn:epc:id:gsrn:{TD_SERVICE_PREFIX}.AGENT{n}"

# ── The fleet registry - mirrors the Agent Builder Registry (TD-A-00..32) ──
FLEET = [
    ("TD-A-00","Master Orchestrator","F0","designed"),
    ("TD-A-01","Agent Passport Issuer","F0","build44"),
    ("TD-A-02","Loop Controller","F0","build44"),
    ("TD-A-03","Health & Monitor","F0","designed"),
    ("TD-A-04","Look-back Reviewer","F0","planned"),
    ("TD-A-05","Population Agent","F1","build44"),
    ("TD-A-06","Source Connector Suite","F1","partial"),
    ("TD-A-07","Dedupe & Merge","F1","designed"),
    ("TD-A-08","Population Simulator","F1","build44"),
    ("TD-A-09","Verification Agent","F2","partial"),
    ("TD-A-10","Exception-Gate Agent","F2","build44"),
    ("TD-A-11","Governance / Policy Agent","F2","build44"),
    ("TD-A-12","Register Agent","F3","build44"),
    ("TD-A-13","Role Deriver","F3","designed"),
    ("TD-A-14","Namespace Pre-populator","F3","designed"),
    ("TD-A-15","Relationship Discovery","F4","partial"),
    ("TD-A-16","Partner-Table Builder","F4","designed"),
    ("TD-A-17","Graph Assembler","F4","build44"),
    ("TD-A-18","Edge Inferrer","F4","designed"),
    ("TD-A-19","Driver-Authoring (Encoder)","F5","build44"),
    ("TD-A-20","Workflow / Protocol Agent","F5","designed"),
    ("TD-A-21","Capability Mapper","F5","designed"),
    ("TD-A-22","Binding Agent","F6","build44"),
    ("TD-A-23","Re-home Agent","F6","designed"),
    ("TD-A-24","No-Assumption Guard","F6","designed"),
    ("TD-A-25","Edge / Telemetry Agent","F6","partial"),
    ("TD-A-26","MCP Resolution","F7","build44"),
    ("TD-A-27","Suggestion / Combinatorial","F7","partial"),
    ("TD-A-28","Evidence Writer","F7","build44"),
    ("TD-A-29","Action-Loop Executor","F7","build44"),
    ("TD-A-30","Demo / Scenario Builder","F8","build44"),
    ("TD-A-31","Book-Binding Agent","F8","planned"),
    ("TD-A-32","Counter / Aggregator","F8","build44"),
]

# ── Shared context: run ledger + audit trail (TD-A-28 Evidence Writer) ──
@dataclass
class RunContext:
    events: list = field(default_factory=list)
    registry: dict = field(default_factory=dict)
    counters: dict = field(default_factory=lambda: {"staged":0,"verified":0,"exception":0,"registered":0})
    def emit(self, agent_id, kind, detail):
        self.events.append({"eventId":new_id("evt"),"at":now(),"agent":agent_id,
                            "agentGSRN":agent_gsrn(agent_id),"kind":kind,**detail})

# ── F0 TD-A-01 Agent Passport Issuer ──
def issue_passport(agent_id, name, rights):
    return {"agent":agent_id,"name":name,"gsrn":agent_gsrn(agent_id),"rights":rights,"issuedAt":now()}

# ── F1 TD-A-06 Source Connector Suite (offline seed; TODO(live)) ──
def source_connectors(target):
    SEED = {"samsung":[
        {"key":"8806088","name":"SAMSUNG ELECTRONICS CO., LTD.","mo":"GS1 Korea","gln":"8801643000011","verified_anchor":True,"lei":"2038003BXBLQFRWCFO70"},
        {"key":"6009802063","name":"Samsung Electronics S A","mo":"GS1 South Africa","lei":"2038003BXBLQFRWCFO70"},
        {"key":"8801234","name":"SAMSUNG SDI CO., LTD.","mo":"GS1 Korea","lei":"9884000000000000SDI1"},
        {"key":"880917009","name":"SAMSUNG FOOD","mo":"GS1 Korea"},
        {"key":"880936353","name":"SAMSUNG RIVET","mo":"GS1 Korea"},
        {"key":"880962309","name":"Samsung Farm","mo":"GS1 Korea"},
        {"key":"542502469","name":"SAMSUNG","mo":"GS1 Belgium & Lux"},
        {"key":"5990080135004","name":"Samsung Zrt.","mo":"GS1 Hungary"},
    ]}
    return SEED.get(target.lower().split()[0], [])

def load_csv(path):
    out=[]
    with path.open(newline="",encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out.append({"key":str(r.get("licence_key") or r.get("key") or "").strip(),
                        "name":str(r.get("company_name") or r.get("name") or "").strip(),
                        "mo":str(r.get("mo") or "").strip(),
                        "gln":str(r.get("gln") or "").strip()})
    return out

# ── F1 TD-A-05 Population Agent + TD-A-07 Dedupe & Merge ──
NAMESAKE={"food","farm","rivet","greetings","medical","record","unilam","nongjajae","cookand","cook","trading","travel","motors"}
POSITIVE={"electronics","sdi","electro-mechanics","electromechanics","semiconductor","display","foundry"}

def _norm(name):
    n=re.sub(r"[.,]"," ",name.lower()).strip(); n=re.sub(r"\s+"," ",n)
    for suf in ["co ltd","co.,ltd","co., ltd","ltd","inc","corp","corporation","zrt","s a","sa","gmbh"]:
        if n.endswith(" "+suf): n=n[:-(len(suf)+1)].strip()
    return n

def population_agent(ctx, raw):
    seen, staged = set(), []
    for r in raw:
        norm=_norm(r["name"]); dk=(norm,r.get("key",""))
        if dk in seen: continue
        seen.add(dk)
        staged.append({**r,"norm":norm,"state":"staged"})
        ctx.counters["staged"]+=1
        ctx.emit("TD-A-05","staged_candidate",{"key":r.get("key"),"name":r["name"]})
    return staged

# ── F2 TD-A-09 Verification Agent + TD-A-10 Exception Gate ──
def _exception(ctx, cand, reasons):
    cand.update(state="exception",tier="REJECTED",reasons=reasons)
    ctx.counters["exception"]+=1
    ctx.emit("TD-A-10","exception_held",{"key":cand.get("key"),"name":cand["name"],"why":reasons})
    return cand

def verify_agent(ctx, cand, home_mo, core_token):
    toks=set(cand["norm"].split()); reasons=[]; score=0.0
    if cand.get("verified_anchor"):
        cand.update(state="verified",tier="VERIFIED",score=1.0,
                    reasons=["operator-confirmed GEPIR anchor",f"LEI {cand.get('lei','-')}"])
        ctx.counters["verified"]+=1
        ctx.emit("TD-A-09","verified",{"key":cand["key"],"name":cand["name"]})
        return cand
    if core_token not in toks:
        return _exception(ctx,cand,["missing core token"])
    if toks & NAMESAKE: reasons.append("namesake token"); score-=0.6
    if any(p in cand["norm"] for p in POSITIVE): reasons.append("operating-line token"); score+=0.5
    if cand.get("mo")==home_mo: reasons.append("home MO band"); score+=0.15
    else: reasons.append(f"non-home MO ({cand.get('mo')})"); score-=0.35
    if cand.get("lei"):
        reasons.append("GLEIF LEI confirms group member"); score+=0.5
        reasons.append("prefix not a verified anchor - hold")
    if score>=0.35:
        cand.update(state="candidate",tier="CANDIDATE",score=round(score,2),reasons=reasons)
        ctx.emit("TD-A-09","candidate_held",{"key":cand["key"],"name":cand["name"],"score":cand["score"]})
        return cand
    return _exception(ctx,cand,reasons+[f"score {round(score,2)} below threshold"])

# ── F3 TD-A-13 Role Deriver + TD-A-12 Register Agent (the addParty() gate) ──
def role_deriver(cand):
    roles=["party"]
    if any(p in cand["norm"] for p in POSITIVE): roles+=["manufacturer","brand-owner"]
    return roles

def register_agent(ctx, cand):
    # THE GATE: only a VERIFIED candidate with a confirmed prefix registers.
    if cand.get("state")!="verified" or not cand.get("key"):
        return None
    prefix=cand["key"]; roles=role_deriver(cand)
    party={"orgName":cand["name"],"prefix":prefix,"gln":cand.get("gln") or f"{prefix}000000",
           "root":f"urn:epc:id:sgln:{prefix}.0.0","roles":roles,"lei":cand.get("lei"),
           "registeredAt":now(),"source":"Agent Fleet - verified-or-exception"}
    ctx.registry[prefix]=party
    ctx.counters["registered"]+=1
    ctx.emit("TD-A-12","registered_party",{"prefix":prefix,"orgName":cand["name"],"roles":roles})
    return party

# ── F0 TD-A-02 Loop Controller ──
def loop_controller(ctx, loop_name, items, fn, **kw):
    ctx.emit("TD-A-02","loop_start",{"loop":loop_name,"count":len(items)})
    out=[]
    for it in items:
        try: out.append(fn(ctx,it,**kw))
        except Exception as e: ctx.emit("TD-A-02","loop_item_error",{"loop":loop_name,"error":str(e)})
    ctx.emit("TD-A-02","loop_end",{"loop":loop_name,"produced":len(out)})
    return out

# ── F0 TD-A-00 Master Orchestrator ──
def orchestrate(target, home_mo, raw):
    ctx=RunContext()
    ctx.emit("TD-A-00","run_start",{"target":target,"home_mo":home_mo,"sources":len(raw)})
    core_token=target.lower().split()[0]
    staged=population_agent(ctx, loop_controller(ctx,"ingest",raw,lambda c,r:r))
    verified_or_held=loop_controller(ctx,"verify",staged,verify_agent,home_mo=home_mo,core_token=core_token)
    registered=[]
    for cand in verified_or_held:
        party=register_agent(ctx,cand)
        if party: registered.append(party)
    ctx.emit("TD-A-32","counters",dict(ctx.counters))
    ctx.emit("TD-A-00","run_end",{"registered":len(registered)})
    return ctx

# ── Reporting ──
def print_fleet_status():
    by={}
    for _i,_n,_f,st in FLEET: by[st]=by.get(st,0)+1
    print("ThingDaddy Agent Fleet - 33 agents (TD-A-00..32), 9 families")
    print("-"*66); fam=None
    for aid,name,f,st in FLEET:
        if f!=fam: print(f"\n{f}"); fam=f
        print(f"  {aid}  {name:<30} [{st:<8}] {agent_gsrn(aid)}")
    print("\n"+"-"*66); print("status totals:",dict(sorted(by.items())))

def print_run(ctx):
    print("="*70); print("ThingDaddy Agent Fleet - run complete"); print("="*70)
    print("counters:",dict(ctx.counters))
    print(f"\nregistered parties ({len(ctx.registry)}):")
    for prefix,p in ctx.registry.items():
        print(f"  OK {prefix}  {p['orgName']}  roles={p['roles']}  LEI={p.get('lei') or '-'}")
    print(f"\naudit events: {len(ctx.events)} (written to ledger)")
    held=ctx.counters["staged"]-ctx.counters["registered"]
    print(f"gate held back {held} of {ctx.counters['staged']} staged "
          f"(candidates + exceptions) - nothing minted without a verified prefix.")

def main(argv):
    if "--status" in argv:
        print_fleet_status(); return 0
    target,home_mo="Samsung","GS1 Korea"
    if len(argv)>1 and not argv[1].startswith("--"):
        raw=load_csv(Path(argv[1])); src=argv[1]
    else:
        raw=source_connectors(target); src=f"built-in seed: {target}"
    ctx=orchestrate(target,home_mo,raw)
    print_run(ctx)
    OUT_DIR.mkdir(parents=True,exist_ok=True)
    LEDGER.write_text(json.dumps({"target":target,"source":src,"ranAt":now(),
        "counters":ctx.counters,"registry":ctx.registry,"events":ctx.events,
        "fleet":[{"id":a,"name":n,"family":f,"status":s,"gsrn":agent_gsrn(a)} for a,n,f,s in FLEET]},indent=2))
    print(f"\nledger written: {LEDGER}")
    return 0

if __name__=="__main__":
    raise SystemExit(main(sys.argv))
