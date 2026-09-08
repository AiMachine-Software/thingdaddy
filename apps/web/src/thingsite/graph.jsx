// The graphs. SHAPE = key class (Chen-style) · COLOUR = key type · STATE is
// carried by opacity, never by colour. Two facts, no words.
//
// The animated graphs are built as SVG strings and mounted with innerHTML: the
// fleet redraws 210 nodes per frame, and the estate/book use SMIL <animate>,
// both of which are simpler and faster imperative than as React elements.
import React, { useEffect, useMemo, useRef } from 'react';
import { KC, OPACITY, RECORDS, SHAPE } from './data.js';

export function esc(s) {
  return String(s == null ? '' : s).replace(/[<>&]/g, (c) => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;' }[c]));
}

export function nodeSvg(x, y, k, g, r) {
  const f = KC[k] || '#8aa4b8', sh = SHAPE[k] || 'circle';
  const op = OPACITY[g] !== undefined ? OPACITY[g] : 0.55;
  const dash = g === 'slot'
    ? ` fill="none" stroke="${f}" stroke-width="1.4" stroke-dasharray="3 3" opacity="${op}"`
    : ` fill="${f}" opacity="${op}"`;
  if (sh === 'square') return `<rect x="${x - r}" y="${y - r}" width="${r * 2}" height="${r * 2}" fill="${f}"${dash}/>`;
  if (sh === 'triangle') return `<path d="M${x} ${y - r * 1.15} L${x + r * 1.1} ${y + r * 0.8} L${x - r * 1.1} ${y + r * 0.8} Z" fill="${f}"${dash}/>`;
  if (sh === 'diamond') return `<path d="M${x} ${y - r} L${x + r} ${y} L${x} ${y + r} L${x - r} ${y} Z" fill="${f}"${dash}/>`;
  return `<circle cx="${x}" cy="${y}" r="${r}"${dash}/>`;
}

/* THE FLEET GRAPH - the star. Night sky: drift, twinkle, constellations. */
export function FleetGraph() {
  const ref = useRef(null);
  useEffect(() => {
    const svg = ref.current, W = 960, H = 380;
    const KS = ['gtin', 'giai', 'cpid', 'gdti', 'pgln', 'gln', 'gsrn', 'sscc', 'grai'];
    let seed = 7;
    const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
    const N = [];
    for (let i = 0; i < 210; i++) {
      const g = rnd() < 0.13 ? 'v' : rnd() < 0.55 ? 'c' : 'slot';
      N.push({ x: 20 + rnd() * (W - 40), y: 20 + rnd() * (H - 40), r: 1.8 + rnd() * 3.0, g,
        k: KS[Math.floor(rnd() * KS.length)],
        vx: (rnd() - 0.5) * 0.09, vy: (rnd() - 0.5) * 0.07,   // slow drift
        tw: rnd() * Math.PI * 2, ts: 0.4 + rnd() * 0.9 });     // twinkle phase & speed
    }
    const LINK = 5200; // constellations form when nodes drift near
    let raf = 0;
    function frame(t) {
      for (const n of N) {
        n.x += n.vx; n.y += n.vy;
        if (n.x < 10 || n.x > W - 10) n.vx *= -1;
        if (n.y < 10 || n.y > H - 10) n.vy *= -1;
      }
      let edges = '';
      for (let i = 0; i < N.length; i++) {
        for (let j = i + 1; j < N.length; j++) {
          const dx = N[i].x - N[j].x, dy = N[i].y - N[j].y, d2 = dx * dx + dy * dy;
          if (d2 < LINK) {
            const o = (1 - d2 / LINK) * 0.42; // fades in as they approach, out as they part
            edges += `<line x1="${N[i].x.toFixed(1)}" y1="${N[i].y.toFixed(1)}" x2="${N[j].x.toFixed(1)}" y2="${N[j].y.toFixed(1)}" stroke="#3d6b7d" stroke-width="1" opacity="${o.toFixed(2)}"/>`;
          }
        }
      }
      let nodes = '';
      for (const n of N) {
        // verified nodes twinkle; candidates sit steady and dim
        const tw = n.g === 'v' ? 0.86 + 0.14 * Math.sin((t / 700) * n.ts + n.tw) : 1;
        nodes += `<g opacity="${tw.toFixed(2)}">` + nodeSvg(+n.x.toFixed(1), +n.y.toFixed(1), n.k, n.g, +n.r.toFixed(1)) + '</g>';
      }
      svg.innerHTML = edges + nodes;
      raf = requestAnimationFrame(frame);
    }
    raf = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(raf);
  }, []);
  return <svg ref={ref} viewBox="0 0 960 380" preserveAspectRatio="xMidYMid slice" />;
}

/* slide 2 - a real company's slice, assembling. Their own record, not a mock.
   Remounted (via key) each time it comes round so the assembly re-runs. */
export function EstateGraph() {
  const html = useMemo(() => {
    const g = RECORDS['diazyme.com'].graph;
    const at = (id) => g.nodes.find((n) => n.id === id);
    return g.edges.map(([a, b], i) => { const p = at(a), q = at(b);
      return `<line x1="${p.x}" y1="${p.y}" x2="${q.x}" y2="${q.y}" stroke="#20404f" stroke-width="1.4" opacity="0"><animate attributeName="opacity" from="0" to=".9" dur=".5s" begin="${320 + i * 90}ms" fill="freeze"/></line>`; }).join('')
      + g.nodes.map((n, i) => `<g opacity="0"><animate attributeName="opacity" from="0" to="1" dur=".45s" begin="${i * 110}ms" fill="freeze"/>`
        + nodeSvg(n.x, n.y * 0.92, n.k, n.g, n.k === 'pgln' ? 13 : 9)
        + `<text x="${n.x}" y="${n.y * 0.92 + 25}" fill="#8fa6b4" font-size="11" text-anchor="middle">${esc(n.label)}</text></g>`).join('');
  }, []);
  return <svg viewBox="0 0 960 380" dangerouslySetInnerHTML={{ __html: html }} />;
}

/* slide 3 - the Book. Pages, because 100 pages is part of the argument. */
export function BookArt() {
  const html = useMemo(() => {
    const sheet = (x, y, w, h, o, fill) => `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="4" fill="${fill}" opacity="${o}"/>`;
    let out = '';
    for (let i = 7; i >= 0; i--) out += sheet(300 + i * 7, 74 + i * 4, 300, 232, 0.10 + i * 0.03, '#dfe9ee'); // the stack
    out += sheet(292, 66, 300, 240, 1, '#ffffff'); // the open page
    const L = [[312, 104, 150, 9], [312, 124, 240, 6], [312, 138, 232, 6], [312, 152, 208, 6],
      [312, 176, 120, 8], [312, 194, 240, 6], [312, 208, 226, 6], [312, 222, 198, 6],
      [312, 246, 140, 8], [312, 264, 236, 6], [312, 278, 210, 6]];
    out += L.map(([x, y, w, h], i) => `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="3" fill="${h > 6 ? '#12344D' : '#c3ced6'}" opacity="0"><animate attributeName="opacity" from="0" to="1" dur=".3s" begin="${i * 70}ms" fill="freeze"/></rect>`).join('');
    // the nine-key board down the side of the page - shape carries class
    const board = [['pgln', 'v'], ['gln', 'v'], ['giai', 'c'], ['gtin', 'v'], ['gdti', 'c'],
      ['cpid', 'slot'], ['gsrn', 'slot'], ['grai', 'slot'], ['sscc', 'slot']];
    out += board.map(([k, gr], i) => `<g opacity="0"><animate attributeName="opacity" from="0" to="1" dur=".3s" begin="${760 + i * 80}ms" fill="freeze"/>` + nodeSvg(712, 96 + i * 24, k, gr, 7) + '</g>').join('');
    out += '<text x="748" y="78" fill="#8fa6b4" font-size="12" font-family="ui-monospace,Menlo,monospace">100 pages</text>';
    return out;
  }, []);
  return <svg viewBox="0 0 960 380" dangerouslySetInnerHTML={{ __html: html }} />;
}

/* their slice - labelled, because it is THEIR graph, not the fleet */
export function SliceGraph({ graph }) {
  const html = useMemo(() => {
    const at = (id) => graph.nodes.find((n) => n.id === id);
    return graph.edges.map(([a, b]) => { const p = at(a), q = at(b);
      return `<line x1="${p.x}" y1="${p.y}" x2="${q.x}" y2="${q.y}" stroke="#20404f" stroke-width="1.4"/>`; }).join('')
      + graph.nodes.map((n, i) => `<g opacity="0"><animate attributeName="opacity" from="0" to="1" dur=".45s" begin="${i * 70}ms" fill="freeze"/>`
        + nodeSvg(n.x, n.y, n.k, n.g, n.k === 'pgln' ? 12 : 8)
        + `<text x="${n.x}" y="${n.y - 16}" fill="#c8d6de" font-size="11.5" text-anchor="middle" font-family="ui-monospace,Menlo,monospace">${esc(n.k)}</text>`
        + `<text x="${n.x}" y="${n.y + 24}" fill="#8fa6b4" font-size="11" text-anchor="middle">${esc(n.label)}</text></g>`).join('');
  }, [graph]);
  return (
    <>
      <div className="graphbox"><svg viewBox="0 0 960 400" dangerouslySetInnerHTML={{ __html: html }} /></div>
      <div className="undergraph">
        <span><svg width="9" height="9"><rect width="9" height="9" fill="#5A6B78" /></svg> thing</span>
        <span><svg width="10" height="9"><path d="M5 0 L10 9 L0 9 Z" fill="#5A6B78" /></svg> document</span>
        <span><svg width="9" height="9"><circle cx="4.5" cy="4.5" r="4.5" fill="#5A6B78" /></svg> party · place · agent</span>
        <span className="sep">shape = key class &nbsp;|&nbsp; colour = key type &nbsp;|&nbsp; solid = verified · dim = candidate · dashed = slot</span>
      </div>
    </>
  );
}
