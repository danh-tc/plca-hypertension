"""
Descriptive (motivated by Zanger-Tishler, Nyarko & Goel, Sci Adv 2024): conditional association of
each feature with Y_self vs Y_clin140, from standardized logistic regressions on the same cohort,
preprocessing and features. Bootstrap (B) intervals on coefficients; reports whether the two
coefficients have opposite signs with both intervals excluding 0. Not an endpoint, not causal.

    python src/coef_signs.py --data-dir data/raw --out-dir outputs/coef_signs --cycles discovery --boot 200
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, os.path.dirname(__file__))
from phase0_nhanes import CYCLE_SETS, load_cycle, build_cycle  # noqa: E402
from phase05_model_reliance import build_features  # noqa: E402
from utils import write_manifest  # noqa: E402


def fit_coefs(X, y, seed):
    m = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                      LogisticRegression(max_iter=5000, random_state=seed))
    m.fit(X, y)
    return m[-1].coef_[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--out-dir", default="outputs/coef_signs")
    ap.add_argument("--cycles", choices=["discovery", "confirmation", "G", "H", "I", "J"], default="discovery",
                    help="cycle set; single cycles (G/H/I/J) for the per-cycle sensitivity")
    ap.add_argument("--boot", type=int, default=200)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--drop-features", nargs="*", default=["chol_checked"])
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    data = pd.concat([build_cycle(load_cycle(args.data_dir, s), s)[0] for s in CYCLE_SETS[args.cycles]],
                     ignore_index=True)
    X, groups = build_features(data)
    X = X.drop(columns=[c for c in args.drop_features if c in X.columns])
    X = X.drop(columns=[c for c in X.columns if X[c].notna().sum() == 0])
    group_of = {f: g for g, fs in groups.items() for f in fs}
    y = {"self": data["Y_self"].values, "clin": data["Y_clin140"].values}
    idx = np.arange(len(X))
    tr, _ = train_test_split(idx, test_size=0.3, random_state=args.seed, stratify=y["clin"])
    rng = np.random.default_rng(args.seed)
    est = {k: fit_coefs(X.iloc[tr], v[tr], args.seed) for k, v in y.items()}
    boots = {k: [] for k in y}
    for b in range(args.boot):
        tb = rng.choice(tr, size=len(tr), replace=True)
        for k, v in y.items():
            boots[k].append(fit_coefs(X.iloc[tb], v[tb], args.seed + b))
    rows = []
    for j, f in enumerate(X.columns):
        r = {"feature": f, "group": group_of.get(f, "")}
        for k in y:
            bj = np.array(boots[k])[:, j]
            r[f"coef_{k}"], r[f"{k}_lo"], r[f"{k}_hi"] = est[k][j], np.percentile(bj, 2.5), np.percentile(bj, 97.5)
        # paired difference: both labels are refit on the SAME bootstrap resample in each replicate
        dj = np.array(boots["self"])[:, j] - np.array(boots["clin"])[:, j]
        r["diff_self_minus_clin"] = est["self"][j] - est["clin"][j]
        r["diff_lo"], r["diff_hi"] = np.percentile(dj, 2.5), np.percentile(dj, 97.5)
        excl = lambda k: r[f"{k}_lo"] > 0 or r[f"{k}_hi"] < 0  # noqa: E731
        r["opposite_sign_point"] = bool(np.sign(r["coef_self"]) != np.sign(r["coef_clin"]))
        r["opposite_sign_both_excl0"] = r["opposite_sign_point"] and excl("self") and excl("clin")
        rows.append(r)
    out = pd.DataFrame(rows)
    out.round(4).to_csv(f"{args.out_dir}/K1_coef_signs.csv", index=False)
    write_manifest(args.out_dir, args, {"n_train": int(len(tr))})
    print(out.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
