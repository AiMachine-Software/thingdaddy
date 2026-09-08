#!/usr/bin/env python3
"""
run_all.py — production entrypoint. Runs Loop A (profiles) then Loop B (edges)
against one shared SQLite graph, so relationship edges attach to unified profiles.
Caps + checkpoints make every run resumable; a capped run resumes next cadence.
"""
import argparse, os, sys
_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _ROOT)
from common.harness import Store
from common.logging_setup import setup as log_setup
from loop_a.run import load_cfg, run_all as run_a
from loop_b.run import run_all as run_b

def main():
    ap = argparse.ArgumentParser(description="ThingDaddy Loops — full pipeline (A then B)")
    ap.add_argument("--db", default="civilization.db")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--out", default="out")
    ap.add_argument("--only", choices=["a", "b"], help="run only one loop")
    a = ap.parse_args()
    log = log_setup(name="loops")
    cfg = load_cfg(a.config)
    store = Store(a.db)
    try:
        if a.only != "b":
            log.info("Loop A start (offline=%s)", cfg.get("offline"))
            run_a(store, cfg, a.out)
        if a.only != "a":
            log.info("Loop B start")
            run_b(store, cfg, a.out)
    finally:
        store.close()
    log.info("pipeline complete; outputs in %s/", a.out)

if __name__ == "__main__":
    main()
