# Plan — responsive for the web app (apps/web)

Status: **planned, not started** (Ant, 2026-09-11: "plan ไว้ แต่ยังไม่ต้องทำ").
Scope: `apps/web` only. Legacy pages under `public/demo/` are out of scope.

## What was measured (2026-09-11, live server, 390 px wide)

Measured with a 390 px iframe on the same origin (headless Chrome at `--window-size=390`
over-reports: it enforces a minimum window width). Page `scrollWidth` was 406 px on every
route; the only element past 390 on every route was the shell nav's fifth link.

| Surface | At 390 px | Cause |
|---|---|---|
| Shell nav (`src/shell.css`) | 5th link "Demo pages" clipped; page 16 px wider than viewport on every route | 5 links on one non-wrapping flex row |
| Platform `/` (`src/platform/ThingDaddy_V4_Unified.jsx`) | header row squeezes "Start: Register a company…" into a 60 px column under the V4 badge; module tab bar (Register / Experience / Explore / Build / Platform) cut at the right | inline styles, no breakpoint; tab row does not scroll |
| ThingSite `/thingsite` (`src/thingsite/`) | left rail hidden entirely below 820 px (inherited rule), so Home / Identify / ThingSite / claimed count are unreachable; API bar wraps to 3 lines | `@media(max-width:820px){.ts .rail{display:none}}` with no replacement |
| Registry `/registry` (`src/registry/styles.css`) | usable; "Register an identity" button wraps to 3 lines; stat tiles 2×2 | has its own 640/820 breakpoints |

## Breakpoints

Use three widths and test at exactly these: **390** (phone), **768** (tablet), **1024** (small laptop).
Tailwind-style names are not needed; plain `@media (max-width: …)` in each surface's own CSS.

## Tasks, in order

### 1. Shell nav — `src/shell.css`, `src/App.jsx` (small)
- Below 640 px: let the row scroll horizontally (`overflow-x:auto; white-space:nowrap`), hide the
  brand text or shrink it, keep all links reachable. No hamburger yet — 4 links fit in a scroller.
- Acceptance: `scrollWidth === innerWidth` at 390 on every route.

### 2. ThingSite — `src/thingsite/thingsite.css`, `ThingSite.jsx` (medium)
- Replace the "rail hidden below 820" rule with a collapsible menu: a "Menu" button in the
  API bar row (or above content) that toggles the same `NAV` list as an overlay/drawer; close on
  navigate. Keep the rail as-is ≥ 820.
- API bar: below 640 hide the db name and record breakdown behind the dot + "LIVE"/"NO API" only;
  keep "show raw responses" as an icon-less short label.
- Hero: keep 380 px height ≥ 640; below that 260 px (`.graphbox.hero3` inline height → class).
- Cards (`.rcard`): action buttons wrap under the name at < 640 (already flex-wrap; verify).
- Book: TOC becomes full width above the chapter at < 820 (`.bookwrap` wraps already; set `.toc` width 100%).
- Acceptance: at 390 the user can reach Home / Identify / current ThingSite from the menu; no
  horizontal scroll; counter, search, cards readable.

### 3. Registry — `src/registry/styles.css` (small)
- `.topbar` button: allow the CTA to drop under the title at < 640 (`flex-wrap`), `white-space:nowrap`
  on the button text.
- Acceptance: button on one line, no clipping at 390.

### 4. Platform V4 — `src/platform/ThingDaddy_V4_Unified.jsx` (medium, separate round)
Rules from `src/platform/CLAUDE.md` apply: surgical edits only, `npm run parse-check` must print
`PARSE OK`, never regenerate the file.
- Header row 1: let the "Start: …" hint hide below 768 (wrap it in a span with a class; add one
  `<style>` block near the top of `ThingDaddyPlatform` with the media rules — the file already
  injects small `<style>` tags for keyframes, so this is in keeping).
- Module tab row: `overflow-x:auto` with `-webkit-overflow-scrolling:touch`, tabs `flex:0 0 auto`.
- Hero search + company chips: already wrap; verify only.
- Do not attempt the 57 modules in one pass; fix the shell (header, tabs, home) first and list
  which modules still overflow, by measurement.

### 5. Verify (every task)
Run from a Claude session with the Chrome extension, or a local page that iframes the site:

```js
// same-origin iframe at W px; lists elements whose right edge passes W
const W = 390; /* then 768, 1024 */
const f = document.createElement('iframe'); f.style.cssText = `width:${W}px;height:800px;border:0`;
f.src = '/thingsite'; document.body.appendChild(f);
await new Promise(r => f.onload = () => setTimeout(r, 2500));
const d = f.contentDocument, out = [];
for (const el of d.querySelectorAll('body *')) { const r = el.getBoundingClientRect();
  if (r.right > W + 1 && r.width) out.push(el.tagName + '.' + el.className + ' ' + Math.round(r.right)); }
({ scrollWidth: d.documentElement.scrollWidth, out: out.slice(0, 12) })
```

Pass = `scrollWidth` equals `W` and `out` is empty, on `/`, `/thingsite`, `/thingsite/site/diazyme.com`,
`/thingsite/book/diazyme.com`, `/registry`, `/demo`, at all three widths. Attach the 3-up iframe
screenshot (see `deploy/server/TASKS-2026-09-10.md` § verify for the headless recipe) to the PR.

## Estimate

Tasks 1–3 + verification: about half a day. Task 4: its own round, half a day for the shell of the
platform, unknown for the modules. Ship 1–3 as one PR to `production`; 4 as a second PR.

## Out of scope

- `public/demo/*.html` legacy pages (superseded by `/thingsite`; `td_screens_live.html` stays for `demo_up.sh`).
- The five unbuilt rail pages (Sample ThingSites, Get a Prefix, WHOIS, Pricing, Log in) — separate spec.
