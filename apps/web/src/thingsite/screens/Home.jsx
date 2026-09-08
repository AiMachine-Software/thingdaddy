// S1 · HOME - the generic door. The counter lives on the search, NOT in the graph.
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Counter from '../Counter.jsx';
import { BookArt, EstateGraph, FleetGraph } from '../graph.jsx';
import { useThingSite } from '../store.jsx';

const SLIDES = ['The fleet', 'A real estate', 'The Book'];

export default function Home() {
  const { status, lastQuery } = useThingSite();
  const navigate = useNavigate();
  const [q, setQ] = useState(lastQuery);
  const [slide, setSlide] = useState(0);
  const [paused, setPaused] = useState(false);
  const [estateRun, setEstateRun] = useState(0); // remount key: the assembly re-runs each time it comes round

  // THE HERO ROTATES - fleet -> a real estate assembling -> the Book.
  useEffect(() => {
    if (paused) return undefined;
    const t = setInterval(() => setSlide((s) => (s + 1) % 3), 7000);
    return () => clearInterval(t);
  }, [paused, slide]);
  useEffect(() => { if (slide === 1) setEstateRun((n) => n + 1); }, [slide]);

  function submit(e) {
    e.preventDefault();
    navigate('/thingsite/reveal?q=' + encodeURIComponent(q.trim()));
  }

  return (
    <section>
      <h1 className="lede">You have a Website.<br /><span className="ask">Are you doing Physical AI?</span><br />Then you need a ThingSite for all of your physical things.</h1>
      <p className="sub">We have one for you. Just enter your company name.<br /><span className="try">Type <b>ACME</b> to see a demo.</span></p>

      <form className="brow" onSubmit={submit}>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Enter your company name" autoComplete="off" />
        <button type="submit" aria-label="Look up">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.4"><circle cx="11" cy="11" r="7" /><line x1="21" y1="21" x2="16.5" y2="16.5" /></svg>
        </button>
      </form>

      <Counter status={status} />

      <div className="graphbox hero3" style={{ height: 380 }}>
        <div className={'slide' + (slide === 0 ? ' on' : '')}><FleetGraph /></div>
        <div className={'slide' + (slide === 1 ? ' on' : '')}><EstateGraph key={estateRun} /></div>
        <div className={'slide' + (slide === 2 ? ' on' : '')}><BookArt /></div>
      </div>
      <div className="pills">
        {SLIDES.map((label, i) => (
          <button key={label} type="button" className={'pill' + (slide === i ? ' on' : '')} onClick={() => setSlide(i)}>{label}</button>
        ))}
        <button type="button" className="pill pause" onClick={() => setPaused((p) => !p)} title={paused ? 'play' : 'pause'}>
          {paused ? '▶' : '❙❙'}
        </button>
      </div>
    </section>
  );
}
