# ThingDaddy Platform — area CLAUDE.md (apps/web/src/platform/)

Rules specific to the V4 unified React platform. Read the root `CLAUDE.md` first
for the four laws and the registration spine.

---

## The file

- `ThingDaddy_V4_Unified.jsx` — ONE file, ~37K lines, ~2.5 MB. It is the whole
  platform: version manifest, GS1 ID generators, the GoDaddy design system (`GD`),
  the `IDContext`/`useIDs` provider, ~57 modules, and the default export
  `ThingDaddyPlatform`.
- It is the consolidation of the old Core + Group A + Group B + Build-44 files.
  Those are superseded — do not resurrect the `lazyA/lazyB` / `window.TDGroup*`
  split; every module is inline and referenced directly in the render switch.

## Editing discipline

- **NEVER regenerate the whole file.** Make surgical `str_replace` edits. A full
  rewrite of a 37K-line file loses work and breaks things.
- After ANY edit, run `./parse-check.sh` — it must print `PARSE OK` (Babel TSX
  parse) before you commit.
- Keep exactly one definition of each module function and each top-level const.
  If you add a module, grep first to confirm it doesn't already exist.

## Adding a module (the pattern)

1. Write the module function `function FooModule({ setActiveModule }) { … }`
   using `useIDs()`, the `GD` palette, and `CompanySearchHeader`/`LiveIDsBanner`.
2. Add a registry entry to the `MODULES` array:
   `{ id:"foo", icon:"🧩", label:"Foo", sub:"…", color:"#…", group:"…" }`
   (groups: foundation | identity | build | demos | standards).
3. Add a render line: `{activeModule==="foo" && <FooModule setActiveModule={setActiveModule}/>}`
4. Parse-check.

## Hard constraints (iOS/webview safe)

- No ES2021 numeric separators (`1_000`) or logical-assignment (`||=`, `&&=`) —
  the webview chokes on them.
- Use the `useRef` pattern for registry creation.
- All UIs must stack on phone and expand at ≥820px.
- No `localStorage`/`sessionStorage` in artifact contexts (platform uses the
  persistent-storage API or in-memory state).

## The identity rule in code

- Registration goes through `addParty()` ONLY. No prefix → no registration.
- Verified prefixes: Telular 0702054, Western Research 0899728002, Samsung
  8806088. Everything else renders as a `0DEMO…` candidate, clearly flagged.

## Semantic Graph ↔ agent loop

- `SemanticGraphModule` renders `SEED_ASSOCIATIONS` + live provenance +
  `window.TD_LOOPB_GRAPH` (the agent loop's export). To show the loop's edges,
  load `data/loopB_seed_associations.json` into `window.TD_LOOPB_GRAPH` before
  mount (see `apps/web/src/App.jsx`, route `/`). Edge `state` (verified/candidate/exception)
  carries into the UI — never force an edge to "verified" it didn't earn.

## Build

```bash
npm install
npm run dev        # from the repo root; confirm it renders at http://localhost:5173/
./parse-check.sh   # must print PARSE OK
```
