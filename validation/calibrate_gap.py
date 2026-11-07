"""
validation/calibrate_gap.py
────────────────────────────
Reproduces the Layer-6 gap-threshold calibration.

Uses the audit logs in logs/ (each stores the 500-char intent and website text it
compared). Reports:
  * same-site gaps  — a site's own intent vs its own website
  * cross-site gaps — site A's intent vs site B's website (unrelated by construction)

Thresholds in src/layer6/semantic_gap.py (GAP_ALIGNED_MAX / GAP_DRIFT_MAX) sit between
these two distributions: ALIGNED below the bulk of same-site gaps, MISALIGNED around the
point where gaps look like unrelated content (cross-site p25).

Usage:  python validation/calibrate_gap.py
Re-run it when many more audits have been logged, and adjust the constants if the
distributions shift.
"""

import glob
import itertools
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.utils.embedder import embed, cosine_sim   # noqa: E402


def main():
    docs = []
    for f in sorted(glob.glob(os.path.join(ROOT, "logs", "audit_*.json"))):
        with open(f, encoding="utf-8") as fh:
            g = json.load(fh).get("gap", {})
        if g.get("intent_text") and g.get("website_text"):
            docs.append((os.path.basename(f), embed(g["intent_text"]), embed(g["website_text"])))
    if len(docs) < 3:
        print("Need at least 3 logged audits with gap text.")
        return

    own = [1 - cosine_sim(i, w) for _, i, w in docs]
    cross = [1 - cosine_sim(a[1], b[2]) for a, b in itertools.permutations(docs, 2)]
    pct = lambda xs, qs: np.percentile(xs, qs).round(3).tolist()   # noqa: E731

    print(f"audits: {len(docs)}")
    print("same-site gap   min / p25 / median / p75:", round(min(own), 3), *pct(own, [25, 50, 75]))
    print("cross-site gap  p5 / p25 / median       :", *pct(cross, [5, 25, 50]))


if __name__ == "__main__":
    main()
