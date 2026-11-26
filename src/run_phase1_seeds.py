"""
Run the Phase 1 CF audit over several seeds (seed changes split, models, alt bootstrap and DiCE
sampling) and pool the C1 summaries as mean / sd / min / max across seeds.

    python src/run_phase1_seeds.py --data-dir data/raw --out-root outputs/phase1_seeds \
        --seeds 42 43 44 --n-queries 200
Extra arguments after -- are passed to phase1_cf_audit.py (e.g. -- --modes M0_global M3_evidence).
"""
import argparse
import os
import subprocess
import sys

import numpy as np
import pandas as pd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--out-root", default="outputs/phase1_seeds")
    ap.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44])
    ap.add_argument("--n-queries", type=int, default=200)
    args, extra = ap.parse_known_args()
    extra = [e for e in extra if e != "--"]
    script = os.path.join(os.path.dirname(__file__), "phase1_cf_audit.py")
    c1, c3, c6 = [], [], []
    for sd in args.seeds:
        out = os.path.join(args.out_root, f"seed{sd}")
        print(f"\n######## seed {sd}")
        subprocess.run([sys.executable, script, "--data-dir", args.data_dir, "--out-dir", out,
                        "--seed", str(sd), "--n-queries", str(args.n_queries)] + extra, check=True)
        c1.append(pd.read_csv(os.path.join(out, "C1_summary.csv")).assign(seed=sd))
        c3.append(pd.read_csv(os.path.join(out, "C3_coverage_by_group.csv")).assign(seed=sd))
        f6 = os.path.join(out, "C6_endpoints_E3_E4.csv")
        if os.path.exists(f6) and os.path.getsize(f6) > 1:
            c6.append(pd.read_csv(f6).assign(seed=sd))
        f10 = os.path.join(out, "C10_ablation.csv")
        if os.path.exists(f10) and os.path.getsize(f10) > 1:
            e6 = pd.read_csv(f10)
            e6 = e6[(e6["ablation"] == "diag_all") & (e6["set"] == "S_M0")]
            if len(e6):
                c6.append(e6.assign(endpoint="E6", n_common=e6["n_patients"], seed=sd))
    c1 = pd.concat(c1)
    num = [c for c in c1.columns if c not in ("source", "mode", "seed") and pd.api.types.is_numeric_dtype(c1[c])]
    pooled = c1.groupby(["source", "mode"])[num].agg(["mean", "std", "min", "max"]).round(3)
    pooled.columns = [f"{a}_{b}" for a, b in pooled.columns]
    pooled.to_csv(os.path.join(args.out_root, "C1_pooled.csv"))
    pd.concat(c3).to_csv(os.path.join(args.out_root, "C3_all_seeds.csv"), index=False)
    if c6:
        c6 = pd.concat(c6, ignore_index=True)
        c6.to_csv(os.path.join(args.out_root, "C6_all_seeds.csv"), index=False)
        # robustness rule: the primary seed (first in --seeds) decides; every
        # secondary seed must be present, evaluable (inference_ok) and give the SAME SIGN for every
        # endpoint component (point estimates)
        # E3 robustness: point estimates of ALL three components (a) A(M0), (b) A(M0) - A(M2), (c) A(M0) + A(M2)
        # must be positive at seeds 43/44 (H3 is about magnitude; (c) carries the magnitude condition)
        comps = {"E3": ["A_M0", "A_M0_minus_A_M2", "A_M0_plus_A_M2"], "E6": ["E6"]}   # E4 is descriptive
        primary = args.seeds[0]
        rob = []
        for ep, g in c6.groupby("endpoint"):
            if ep[:2] not in comps:
                continue
            cols = comps[ep[:2]]
            pr = g[g["seed"] == primary]
            if pr.empty:
                continue
            pr = pr.iloc[0]
            others = g[g["seed"] != primary]
            missing = [sd for sd in args.seeds[1:] if sd not in set(others["seed"])]
            not_eval = [int(r["seed"]) for _, r in others.iterrows() if not bool(r["inference_ok"])]
            same = bool(all(np.sign(others[c]).eq(np.sign(pr[c])).all() for c in cols)) if len(others) else False
            # robust      : primary met, every secondary seed present, evaluable and same sign
            # not_robust  : primary met, all secondary seeds evaluable, at least one sign differs
            # not_evaluable: a secondary seed is missing or below the feasibility thresholds
            if not bool(pr["inference_ok"]):
                status = "primary_not_evaluable"
            elif not bool(pr["met"]):
                status = "primary_not_met"
            elif missing or not_eval:
                status = "not_evaluable"
            else:
                status = "robust" if same else "not_robust"
            rob.append({"endpoint": ep, "primary_seed": primary, "primary_met": bool(pr["met"]),
                        "primary_inference_ok": bool(pr["inference_ok"]),
                        "secondary_seeds_missing": " ".join(map(str, missing)),
                        "secondary_seeds_not_evaluable": " ".join(map(str, not_eval)),
                        "secondary_same_sign": same, "robustness_status": status,
                        "met_and_robust": status == "robust",
                        **{f"{c}_seed{int(r['seed'])}": r[c] for _, r in g.iterrows()
                           for c in cols if c in r},
                        **{f"n_common_seed{int(r['seed'])}": r["n_common"] for _, r in g.iterrows()}})
        rob = pd.DataFrame(rob)
        # robustness is judged only over the seeds passed in --seeds (confirmation: 42 43 44)
        rob["seeds_evaluated"] = " ".join(map(str, args.seeds))
        rob.to_csv(os.path.join(args.out_root, "C6_robustness.csv"), index=False)
        print("\n== C6 robustness across seeds\n", rob.T.to_string())
    key = ["ECD_mean", "ECD_min", "ECD_max", "validity_own_pct_mean", "queries_with_cf_pct_mean",
           "care_reducing_pct_mean", "taxonomy_violation_pct_mean", "bmi_rel_change_mean_pct_mean"]
    print("\n== pooled key metrics\n", pooled[[k for k in key if k in pooled.columns]].to_string())


if __name__ == "__main__":
    main()
