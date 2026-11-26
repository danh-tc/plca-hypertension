"""
Intervals are training-resampling variability intervals conditional on a fixed test set.
Run the Phase 0.5 robustness checks and summarise the key contrasts in one table.

    python src/run_checks.py --data-dir data/raw --out-root outputs/phase05_checks --boot 30
"""
import argparse
import os
import subprocess
import sys

import pandas as pd

CONFIGS = {
    "baseline": [],                                                    # primary: chol_checked dropped
    "chol_kept_raw": ["--drop-features"],                              # sensitivity: raw BPQ060 (leaky skip)
    "chol_reconstructed": ["--drop-features", "--chol-reconstruct"],   # sensitivity: BPQ080 skip filled
    "exclude_G01_train": ["--exclude-group", "G01"],
    "randdrop_G01_train": ["--random-drop-like", "G01"],
    "exclude_G10_train": ["--exclude-group", "G10"],
    "randdrop_G10_train": ["--random-drop-like", "G10"],
    "self2": ["--self-label", "self2"],
    "clin130": ["--clin-label", "clin130"],
    "bp140_unmedicated": ["--clin-label", "bp140", "--population", "unmedicated"],   # f_self vs f_bp, same population
    "logreg": ["--model", "logreg"],
}
KEY = [("access", "share_self_minus_placebo"), ("access", "share_self_minus_clin"),
       ("other_diagnoses", "share_self_minus_placebo"), ("self_rated_health", "share_self_minus_placebo")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--out-root", default="outputs/phase05_checks")
    ap.add_argument("--boot", type=int, default=30)
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--cycles", choices=["discovery", "confirmation", "G", "H", "I", "J"], default="discovery",
                    help="cycle set; single cycles (G/H/I/J) for the per-cycle sensitivity")
    args = ap.parse_args()
    script = os.path.join(os.path.dirname(__file__), "phase05_model_reliance.py")
    rows = []
    for name, extra in CONFIGS.items():
        if args.only and name not in args.only:
            continue
        out = os.path.join(args.out_root, name)
        print(f"\n######## {name}")
        subprocess.run([sys.executable, script, "--data-dir", args.data_dir, "--out-dir", out,
                        "--boot", str(args.boot), "--cycles", args.cycles] + extra, check=True)
        p3 = pd.read_csv(os.path.join(out, "P3_contrasts.csv"))
        p2 = pd.read_csv(os.path.join(out, "P2_group_importance.csv"))
        auc = pd.read_csv(os.path.join(out, "P1_auc.csv")).set_index("model")["auc_mean"]
        for g, c in KEY:
            r = p3[(p3["group"] == g) & (p3["contrast"] == c)].iloc[0]
            absimp = p2[p2["group"] == g].set_index("model")["importance"]
            rows.append({"config": name, "group": g, "contrast": c, "mean": r["mean"],
                         "ci_low": r["ci_low"], "ci_high": r["ci_high"],
                         "abs_auc_drop_self": absimp.get("f_self"), "abs_auc_drop_clin": absimp.get("f_clin"),
                         "abs_auc_drop_placebo": absimp.get("f_placebo"),
                         "auc_self": auc.get("f_self"), "auc_clin": auc.get("f_clin")})
    summary = pd.DataFrame(rows).round(4)
    summary.to_csv(os.path.join(args.out_root, "SUMMARY.csv"), index=False)
    print("\n== SUMMARY\n", summary.to_string(index=False))


if __name__ == "__main__":
    main()
