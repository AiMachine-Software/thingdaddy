import React, { useState, useEffect, useCallback, useRef } from "react";

/*
  THINGDADDY PLATFORM — SAMPLE SKELETON  (pre-built for the team)
  ---------------------------------------------------------------
  This is the SEED the platform grows from. Two things, in one runnable file:
    1) The FIRST SCREEN  — GoDaddy-style: land -> find your company -> claim
    2) The 5-PILLAR WORKSPACE SHELL — the tabs ARE the five pillars, in order

  It is wired to the REAL population API (the 82K-company registry) so
  "find your company" returns real results. Everything is honest:
  - verified-or-exception: state chips never fake a status
  - workspace = prefix: a claimed company's prefix is shown prominently
  - the 5 pillar tabs are clean placeholders to be FILLED IN in later sprints

  HOW TO EVOLVE THIS (for the team):
  - Split into platform/src/* files matching the repo layout.
  - Fill each pillar tab with harvested Build 44 components.
  - Keep it isolated; it talks to the population API only over HTTP.

  Set the API base to your running population API (default localhost:8787).
*/

const API_BASE =
  (typeof window !== "undefined" && window.__TD_API__) || "http://localhost:8787";

// ---- design tokens (clean + minimal; brand later) ----------------------
const C = {
  ink: "#14202E",
  sub: "#5A6b7a",
  line: "#E4E9EF",
  bg: "#F7F9FB",
  card: "#FFFFFF",
  accent: "#2D6CDF",
  accentSoft: "#EAF1FD",
  verified: "#16A34A",
  candidate: "#D97706",
  exception: "#DC2626",
  chipBg: "#F1F5F9",
};

const STATE_COLOR = {
  verified: C.verified,
  candidate: C.candidate,
  exception: C.exception,
};

// ---- the five pillars (the workspace navigation) -----------------------
const PILLARS = [
  { id: "ids", n: "1", label: "In-Context IDs", tag: "Your identities",
    desc: "Your prefix and every ID minted under it — GLNs, GIAIs, GSRNs. The spine everything roots in." },
  { id: "drivers", n: "2", label: "SiLA Drivers", tag: "The Rules",
    desc: "What each asset may do. SiLA-modified drivers, bound to each asset's In-Context ID." },
  { id: "workflows", n: "3", label: "Allotrope Workflows", tag: "The Events",
    desc: "What each asset does, and when. Allotrope-modified workflows over your identities." },
  { id: "cloud", n: "4", label: "Cloud Bindings", tag: "Where it runs",
    desc: "Map your identities, drivers, and workflows to GCP / Azure / AWS. Every cloud face resolves to one In-Context ID." },
  { id: "graph", n: "5", label: "AI Graph", tag: "Everything connected",
    desc: "The symphony: assets friend each other, agents conduct, provenance forever. The destination." },
];

// ======================================================================
//  ROOT
// ======================================================================
export default function App() {
  const [claimed, setClaimed] = useState(null); // the company whose workspace we're in

  return (
    <div style={{ minHeight: "100vh", background: C.bg, color: C.ink,
      fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif" }}>
      <TopBar claimed={claimed} onExit={() => setClaimed(null)} />
      {claimed
        ? <Workspace company={claimed} />
        : <FirstScreen onClaim={setClaimed} />}
      <FooterNote />
    </div>
  );
}

// ======================================================================
//  TOP BAR
// ======================================================================
function TopBar({ claimed, onExit }) {
  return (
    <div style={{ borderBottom: `1px solid ${C.line}`, background: C.card,
      padding: "14px 24px", display: "flex", alignItems: "center", gap: 12 }}>
      <div style={{ width: 26, height: 26, borderRadius: 7, background: C.accent,
        color: "#fff", display: "grid", placeItems: "center", fontWeight: 800, fontSize: 15 }}>T</div>
      <div style={{ fontWeight: 800, letterSpacing: -0.3 }}>
        ThingDaddy<span style={{ color: C.sub, fontWeight: 500 }}>.com</span>
      </div>
      <div style={{ fontSize: 12, color: C.sub, marginLeft: 4 }}>
        the registrar of the physical world
      </div>
      {claimed && (
        <button onClick={onExit} style={ghostBtn}>
          ← Leave workspace
        </button>
      )}
    </div>
  );
}

// ======================================================================
//  FIRST SCREEN  — land -> find your company -> claim
// ======================================================================
function FirstScreen({ onClaim }) {
  const [q, setQ] = useState("");
  const [rows, setRows] = useState([]);
  const [status, setStatus] = useState("idle"); // idle | loading | ok | error | empty
  const [err, setErr] = useState("");
  const timer = useRef(null);

  const search = useCallback(async (term) => {
    if (!term.trim()) { setRows([]); setStatus("idle"); return; }
    setStatus("loading"); setErr("");
    try {
      const r = await fetch(`${API_BASE}/search?q=${encodeURIComponent(term)}`);
      if (!r.ok) throw new Error(`API responded ${r.status}`);
      const data = await r.json();
      const list = data.rows || [];
      setRows(list);
      setStatus(list.length ? "ok" : "empty");
    } catch (e) {
      setErr(String(e.message || e));
      setStatus("error");
    }
  }, []);

  // debounce typing
  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => search(q), 250);
    return () => timer.current && clearTimeout(timer.current);
  }, [q, search]);

  return (
    <div style={{ maxWidth: 760, margin: "0 auto", padding: "56px 24px 40px" }}>
      <div style={{ fontSize: 13, fontWeight: 700, color: C.accent,
        letterSpacing: 0.4, textTransform: "uppercase", marginBottom: 14 }}>
        Register your ThingDaddy
      </div>
      <h1 style={{ fontSize: 40, lineHeight: 1.1, margin: "0 0 14px", letterSpacing: -1 }}>
        Every physical thing needs<br />a unique, in-context digital ID.
      </h1>
      <p style={{ fontSize: 17, color: C.sub, margin: "0 0 28px", maxWidth: 560 }}>
        Unique because it roots in a prefix. In-context because it carries the
        thing's rules, events, and connections. Find your company and claim its
        prefix — the root of every ID.
      </p>

      {/* search box */}
      <div style={{ position: "relative" }}>
        <input
          autoFocus
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search your company by name, GS1 prefix, or GLN…"
          style={{ width: "100%", boxSizing: "border-box", padding: "16px 18px",
            fontSize: 16, borderRadius: 12, border: `1.5px solid ${C.line}`,
            outline: "none", background: C.card }}
          onFocus={(e) => (e.target.style.borderColor = C.accent)}
          onBlur={(e) => (e.target.style.borderColor = C.line)}
        />
      </div>

      {/* results */}
      <div style={{ marginTop: 16 }}>
        {status === "loading" && <Muted>Searching the registry…</Muted>}
        {status === "idle" && <Muted>Start typing to find your company in the live registry.</Muted>}
        {status === "empty" && (
          <Muted>No match yet. Your company may not be pre-built — that becomes a named
          exception to resolve, never a guess.</Muted>
        )}
        {status === "error" && (
          <div style={{ padding: 14, borderRadius: 10, background: "#FEF2F2",
            border: `1px solid #FCA5A5`, color: "#991B1B", fontSize: 14 }}>
            Can’t reach the registry API at <code>{API_BASE}</code>. Start the population
            API (<code>cd population/api &amp;&amp; npm start</code>) and try again.
            <div style={{ marginTop: 6, opacity: 0.8 }}>{err}</div>
          </div>
        )}
        {status === "ok" && rows.map((row) => (
          <CompanyRow key={row.id} row={row} onClaim={() => onClaim(row)} />
        ))}
      </div>
    </div>
  );
}

function CompanyRow({ row, onClaim }) {
  const state = row.state || "candidate";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 14, padding: "14px 16px",
      background: C.card, border: `1px solid ${C.line}`, borderRadius: 12, marginBottom: 10 }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontWeight: 700, fontSize: 15 }}>{row.legal_name}</div>
        <div style={{ fontSize: 13, color: C.sub, marginTop: 3 }}>
          {row.prefix
            ? <>prefix <b style={{ color: C.accent, fontFamily: "monospace" }}>{row.prefix}</b></>
            : <i>no prefix yet</i>}
          {row.mo ? <>  ·  {row.mo}</> : null}
          {row.source ? <>  ·  source {row.source}</> : null}
        </div>
      </div>
      <StateChip state={state} />
      <button onClick={onClaim} style={primaryBtn}>Claim</button>
    </div>
  );
}

// ======================================================================
//  WORKSPACE  — workspace = prefix; tabs = the 5 pillars
// ======================================================================
function Workspace({ company }) {
  const [tab, setTab] = useState(PILLARS[0].id);
  const pillar = PILLARS.find((p) => p.id === tab);

  return (
    <div style={{ maxWidth: 1080, margin: "0 auto", padding: "28px 24px 40px" }}>
      {/* workspace header: the company IS its prefix namespace */}
      <div style={{ background: C.card, border: `1px solid ${C.line}`, borderRadius: 14,
        padding: "20px 22px", marginBottom: 20 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div>
            <div style={{ fontSize: 12, color: C.sub, fontWeight: 600,
              textTransform: "uppercase", letterSpacing: 0.4 }}>Workspace</div>
            <div style={{ fontSize: 22, fontWeight: 800, marginTop: 2 }}>{company.legal_name}</div>
          </div>
          <StateChip state={company.state || "candidate"} />
        </div>
        <div style={{ marginTop: 10, fontSize: 14, color: C.sub }}>
          {company.prefix
            ? <>This workspace is rooted in prefix{" "}
                <b style={{ color: C.accent, fontFamily: "monospace" }}>{company.prefix}</b>
                {" "}— its namespace. Every In-Context ID here roots in it.</>
            : <><i>No verified prefix yet.</i> This company is a candidate — it can hold a
                pre-built graph, but nothing is verified until a real prefix resolves. Honest by rule.</>}
        </div>
      </div>

      {/* the 5-pillar tab bar */}
      <div style={{ display: "flex", gap: 6, borderBottom: `1px solid ${C.line}`,
        marginBottom: 22, overflowX: "auto" }}>
        {PILLARS.map((p) => {
          const active = p.id === tab;
          return (
            <button key={p.id} onClick={() => setTab(p.id)}
              style={{ appearance: "none", border: "none", background: "none", cursor: "pointer",
                padding: "12px 14px 14px", whiteSpace: "nowrap",
                borderBottom: `2.5px solid ${active ? C.accent : "transparent"}`,
                color: active ? C.ink : C.sub, fontWeight: active ? 800 : 600, fontSize: 14 }}>
              <span style={{ color: active ? C.accent : C.sub, fontWeight: 800, marginRight: 7 }}>{p.n}</span>
              {p.label}
            </button>
          );
        })}
      </div>

      {/* the active pillar (placeholder to fill in later sprints) */}
      <PillarPanel pillar={pillar} company={company} />
    </div>
  );
}

function PillarPanel({ pillar, company }) {
  return (
    <div style={{ background: C.card, border: `1px solid ${C.line}`, borderRadius: 14,
      padding: "28px 26px", minHeight: 280 }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
        <div style={{ fontSize: 12, fontWeight: 800, color: C.accent }}>PILLAR {pillar.n}</div>
        <div style={{ fontSize: 12, color: C.sub, fontWeight: 600 }}>· {pillar.tag}</div>
      </div>
      <h2 style={{ fontSize: 24, margin: "6px 0 10px", letterSpacing: -0.4 }}>{pillar.label}</h2>
      <p style={{ fontSize: 15, color: C.sub, maxWidth: 620, margin: "0 0 22px", lineHeight: 1.55 }}>
        {pillar.desc}
      </p>

      <div style={{ padding: "18px 20px", borderRadius: 12, background: C.accentSoft,
        border: `1px dashed ${C.accent}`, color: C.ink, fontSize: 14, maxWidth: 620 }}>
        <b>To build here (a later sprint):</b> {buildHint(pillar.id, company)}
      </div>
    </div>
  );
}

function buildHint(id, company) {
  const p = company.prefix ? `prefix ${company.prefix}` : "this candidate";
  switch (id) {
    case "ids": return `List every In-Context ID minted under ${p} — GLNs (locations), GIAIs (assets), GSRNs (people/agents). Harvest Build 44's EPC encoder.`;
    case "drivers": return `Show the SiLA-modified driver for each machine asset, bound to its GIAI. Harvest Build 44's driver components.`;
    case "workflows": return `Show the Allotrope-modified workflows this company's assets participate in. Harvest Build 44's workflow components.`;
    case "cloud": return `Map the above to GCP / Azure / AWS — each a carrier resolving to one In-Context ID. Harvest Build 44's cloud/edge.`;
    case "graph": return `Render this company's GLN symphonies — assets, drivers, workflows, and friendings — as one graph. Consolidate Build 44's graph components into one engine.`;
    default: return "";
  }
}

// ======================================================================
//  SMALL PARTS
// ======================================================================
function StateChip({ state }) {
  const color = STATE_COLOR[state] || C.candidate;
  const label = state.charAt(0).toUpperCase() + state.slice(1);
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12,
      fontWeight: 700, color, background: `${color}14`, padding: "5px 10px", borderRadius: 999 }}>
      <span style={{ width: 7, height: 7, borderRadius: 999, background: color }} />
      {label}
    </span>
  );
}

function Muted({ children }) {
  return <div style={{ color: C.sub, fontSize: 14, padding: "12px 2px" }}>{children}</div>;
}

function FooterNote() {
  return (
    <div style={{ maxWidth: 1080, margin: "0 auto", padding: "8px 24px 40px",
      color: C.sub, fontSize: 12 }}>
      Sample skeleton · wired to the live population registry · verified-or-exception,
      prefix-is-root, one In-Context ID spine. Fill the pillars in later sprints.
    </div>
  );
}

const primaryBtn = {
  appearance: "none", border: "none", cursor: "pointer",
  background: C.accent, color: "#fff", fontWeight: 700, fontSize: 14,
  padding: "10px 16px", borderRadius: 10,
};
const ghostBtn = {
  appearance: "none", cursor: "pointer", marginLeft: "auto",
  background: "none", border: `1px solid ${C.line}`, color: C.sub,
  fontWeight: 600, fontSize: 13, padding: "8px 12px", borderRadius: 9,
};
