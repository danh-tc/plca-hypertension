"""
Phase 0.5 - Model-level reliance: does a model trained on the self-reported label lean more on
healthcare-access features than a model trained on the examination-informed phenotype?

Models (same features, same training rows, discovery cycles 2011-2014 only):
  f_self     : Y_self      (BPQ020 == 1)
  f_clin     : Y_clin140   (SBP>=140 or DBP>=90 or on BP medication)
  f_placebo  : class-conditional placebo built from Y_clin140 by flipping labels at the observed
               transition rates P(Y_self=1 | Y_clin=0) and P(Y_self=0 | Y_clin=1)  (control P2)

Reliance = grouped permutation importance (drop in test AUC when all columns of a feature group
are permuted jointly), also as a share of total importance. B bootstrap refits of the training set
give percentile 95% CIs; each bootstrap draws a fresh placebo label.

Excluded from features: measured BP, all BP questionnaire items (BPQ020-BPQ050A, BPD035).

Usage:
    python src/phase05_model_reliance.py --data-dir data/raw --out-dir outputs/phase05 --boot 30
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

sys.path.insert(0, os.path.dirname(__file__))
from phase0_nhanes import CYCLES, CYCLE_SETS, load_cycle, build_cycle  # noqa: E402
from utils import write_manifest  # noqa: E402


def yn(s, yes=1, no=2):
    return s.map({yes: 1.0, no: 0.0})


def build_features(df, chol_reconstruct=False):
    X = pd.DataFrame(index=df.index)
    g = {}
    # demographic / socioeconomic
    X["age"] = df["RIDAGEYR"]
    X["female"] = (df["RIAGENDR"] == 2).astype(float)
    for code in [1, 2, 3, 4, 6, 7]:
        X[f"race_{code}"] = (df["RIDRETH3"] == code).astype(float)
    X["education"] = df["DMDEDUC2"].where(df["DMDEDUC2"] < 7) if "DMDEDUC2" in df else np.nan
    X["income_pir"] = df.get("INDFMPIR")
    g["demographic_SES"] = ["age", "female", "education", "income_pir"] + [f"race_{c}" for c in [1, 2, 3, 4, 6, 7]]
    # healthcare access / utilisation
    X["insured"] = yn(df["HIQ011"]) if "HIQ011" in df else np.nan
    X["routine_place"] = df["HUQ030"].map({1: 1.0, 3: 1.0, 2: 0.0}) if "HUQ030" in df else np.nan
    vcols = [c for c in ("HUQ051", "HUQ050") if c in df.columns]
    X["visits_past_year"] = df[vcols].bfill(axis=1).iloc[:, 0].where(lambda v: v < 77) if vcols else np.nan
    X["chol_checked"] = yn(df["BPQ060"]) if "BPQ060" in df else np.nan
    if chol_reconstruct and "BPQ080" in df:
        # codebook skip: BPQ080 == 1 (told high cholesterol) skips BPQ060 -> cholesterol was checked
        X.loc[df["BPQ080"] == 1, "chol_checked"] = 1.0
    g["access"] = ["insured", "routine_place", "visits_past_year", "chol_checked"]
    # other physician diagnoses (diagnosis-related, not BP)
    X["diabetes_told"] = df["DIQ010"].map({1: 1.0, 3: 0.5, 2: 0.0}) if "DIQ010" in df else np.nan
    X["high_chol_told"] = yn(df["BPQ080"]) if "BPQ080" in df else np.nan
    g["other_diagnoses"] = ["diabetes_told", "high_chol_told"]
    # lifestyle (self-report)
    if "SMQ020" in df:
        cur = pd.Series(np.nan, index=df.index)
        cur[df["SMQ020"] == 2] = 0.0
        if "SMQ040" in df:
            cur[(df["SMQ020"] == 1) & df["SMQ040"].isin([1, 2])] = 1.0
            cur[(df["SMQ020"] == 1) & (df["SMQ040"] == 3)] = 0.0
        X["current_smoker"] = cur
    else:
        X["current_smoker"] = np.nan
    drinks = df["ALQ130"].where(df["ALQ130"] < 777) if "ALQ130" in df else pd.Series(np.nan, index=df.index)
    for never in ("ALQ101", "ALQ111"):
        if never in df:
            drinks = drinks.where(~((df[never] == 2) & drinks.isna()), 0.0)
    X["drinks_per_day"] = drinks
    X["vigorous_rec_pa"] = yn(df["PAQ650"]) if "PAQ650" in df else np.nan
    X["moderate_rec_pa"] = yn(df["PAQ665"]) if "PAQ665" in df else np.nan
    g["lifestyle"] = ["current_smoker", "drinks_per_day", "vigorous_rec_pa", "moderate_rec_pa"]
    # physiology (measured)
    X["bmi"] = df.get("BMXBMI")
    X["waist"] = df.get("BMXWAIST")
    X["total_chol"] = df.get("LBXTC")
    X["hba1c"] = df.get("LBXGH")
    g["physiology"] = ["bmi", "waist", "total_chol", "hba1c"]
    # self-rated health
    X["self_rated_health"] = df["HUQ010"].where(df["HUQ010"] < 7) if "HUQ010" in df else np.nan
    g["self_rated_health"] = ["self_rated_health"]
    X = X.astype(float)
    return X, g


def make_placebo(y_clin, rate_01, rate_10, rng):
    u = rng.random(len(y_clin))
    flip = np.where(y_clin == 0, u < rate_01, u < rate_10)
    return np.where(flip, 1 - y_clin, y_clin)


def group_importance(model, X_te, y_te, groups, rng, n_rep=3, perms=None):
    """Grouped permutation importance (AUC drop). `perms` = {group: [index arrays]} lets several
    models share identical permutations (paired contrasts)."""
    base = roc_auc_score(y_te, model.predict_proba(X_te)[:, 1])
    out = {}
    for name, cols in groups.items():
        drops = []
        plist = perms[name] if perms is not None else [rng.permutation(len(X_te)) for _ in range(n_rep)]
        for perm in plist:
            Xp = X_te.copy()
            Xp[cols] = Xp[cols].values[perm]
            drops.append(base - roc_auc_score(y_te, model.predict_proba(Xp)[:, 1]))
        out[name] = float(np.mean(drops))
    return base, out


def ci(a):
    a = np.asarray(a, dtype=float)
    return np.nanmean(a), np.nanpercentile(a, 2.5), np.nanpercentile(a, 97.5)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--out-dir", default="outputs/phase05")
    ap.add_argument("--boot", type=int, default=30)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--cycles", choices=["discovery", "confirmation", "G", "H", "I", "J"], default="discovery",
                    help="cycle set; single cycles (G/H/I/J) for the per-cycle sensitivity")
    ap.add_argument("--model", choices=["xgb", "logreg"], default="xgb",
                    help="classifier family (logreg = sensitivity; median-imputed, standardized)")
    ap.add_argument("--fixed-test", action="store_true",
                    help="pilot behaviour: no test-set resampling (default: two-level bootstrap)")
    ap.add_argument("--self-label", choices=["self", "self2"], default="self",
                    help="self = ever told (BPQ020); self2 = told >=2 times (BPQ030)")
    ap.add_argument("--clin-label", choices=["clin140", "clin130", "bp140"], default="clin140",
                    help="comparison label: clin140 (primary), clin130 (threshold sensitivity), "
                         "bp140 = measured BP only (use with --population unmedicated -> f_bp)")
    ap.add_argument("--population", choices=["all", "unmedicated"], default="all",
                    help="unmedicated = restrict the whole cohort (train and test) to on_med == 0")
    ap.add_argument("--drop-features", nargs="*", default=["chol_checked"],
                    help="features to remove (default: chol_checked; pass --drop-features with no names to keep it)")
    ap.add_argument("--chol-reconstruct", action="store_true",
                    help="rebuild chol_checked using the BPQ080->BPQ060 skip (use with --drop-features)")
    ap.add_argument("--exclude-group", choices=["G01", "G10"], default=None,
                    help="remove a discordant group from the TRAINING set only (common test set)")
    ap.add_argument("--random-drop-like", choices=["G01", "G10"], default=None,
                    help="control: drop the same number of random training rows with the same Y_self")
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    rng = np.random.default_rng(args.seed)

    frames = []
    for suf in CYCLE_SETS[args.cycles]:
        res = build_cycle(load_cycle(args.data_dir, suf), suf)
        if res is not None:
            frames.append(res[0])
    data = pd.concat(frames, ignore_index=True)
    if args.self_label == "self2":
        n0 = len(data)
        data = data[data["Y_self2"].notna()].reset_index(drop=True)
        data["Y_self"] = data["Y_self2"].astype(int)
        print(f"self2: dropped {n0 - len(data)} rows with unknown BPQ030")
    if args.population == "unmedicated":
        n0 = len(data)
        data = data[data["on_med"] == 0].reset_index(drop=True)
        print(f"unmedicated population: kept {len(data)} of {n0}")
    clin_col = {"clin140": "Y_clin140", "clin130": "Y_clin130", "bp140": "Y_bp140"}[args.clin_label]
    data["Y_cmp"] = data[clin_col].astype(int)
    grp = ("G" + data["Y_self"].astype(str) + data["Y_cmp"].astype(str)).values
    X, groups = build_features(data, chol_reconstruct=args.chol_reconstruct)

    # leak check: missingness of every feature by label (skip patterns tied to BPQ020 would leak)
    leak = []
    for c in X.columns:
        miss = X[c].isna()
        leak.append({"feature": c, "missing_pct_all": round(100 * miss.mean(), 1),
                     "missing_pct_self1": round(100 * miss[data["Y_self"] == 1].mean(), 1),
                     "missing_pct_self0": round(100 * miss[data["Y_self"] == 0].mean(), 1),
                     "missing_pct_clin1": round(100 * miss[data["Y_cmp"] == 1].mean(), 1),
                     "missing_pct_clin0": round(100 * miss[data["Y_cmp"] == 0].mean(), 1)})
    leak = pd.DataFrame(leak)
    leak["self_gap_pp"] = (leak["missing_pct_self1"] - leak["missing_pct_self0"]).round(1)
    leak.to_csv(f"{args.out_dir}/leak_check_missingness.csv", index=False)
    flagged = leak[leak["self_gap_pp"].abs() >= 10]
    if len(flagged):
        print("[LEAK WARNING] missingness differs by Y_self by >=10 pp:\n", flagged.to_string(index=False))
    X = X.drop(columns=[c for c in args.drop_features if c in X.columns])
    # drop features entirely missing (e.g. a table not downloaded) and report them
    empty = [c for c in X.columns if X[c].notna().sum() == 0]
    if empty:
        print("[warn] features with no data (check downloads / variable names):", empty)
    X = X.drop(columns=empty)
    groups = {k: [c for c in v if c in X.columns] for k, v in groups.items()}
    groups = {k: v for k, v in groups.items() if v}
    pd.DataFrame([{"group": k, "features": ", ".join(v)} for k, v in groups.items()]) \
        .to_csv(f"{args.out_dir}/feature_groups.csv", index=False)
    X.notna().mean().round(3).rename("non_missing_share").to_csv(f"{args.out_dir}/feature_missingness.csv")

    y_self = data["Y_self"].values
    y_clin = data["Y_cmp"].values   # f_clin is trained on the chosen comparison label (default Y_clin140)
    idx = np.arange(len(X))
    tr, te = train_test_split(idx, test_size=0.3, random_state=args.seed, stratify=y_clin)
    # placebo transition rates estimated on the TRAINING split only
    rate_01 = float(y_self[tr][y_clin[tr] == 0].mean())        # P(self=1 | clin=0)
    rate_10 = float(1 - y_self[tr][y_clin[tr] == 1].mean())    # P(self=0 | clin=1)
    # leave-group-out / random-drop control act on TRAINING rows only; test set stays common
    if args.exclude_group or args.random_drop_like:
        gname = args.exclude_group or args.random_drop_like
        in_g = grp[tr] == gname
        if args.exclude_group:
            tr = tr[~in_g]
        else:
            same_self = np.where(y_self[tr] == int(gname[1]))[0]
            drop = rng.choice(same_self, size=int(in_g.sum()), replace=False)
            tr = np.delete(tr, drop)
        print(f"{'excluded' if args.exclude_group else 'random-dropped'} {int(in_g.sum())} training rows ({gname})")
    print(f"N={len(X)} train={len(tr)} test={len(te)}  prev self={y_self.mean():.3f} clin={y_clin.mean():.3f}  "
          f"flip rates (train) 0->1={rate_01:.3f} 1->0={rate_10:.3f}")
    params = dict(n_estimators=300, max_depth=4, learning_rate=0.05, subsample=0.8,
                  colsample_bytree=0.8, tree_method="hist", eval_metric="logloss", n_jobs=-1)

    rows = []
    for b in range(args.boot):
        tb = rng.choice(tr, size=len(tr), replace=True)
        y_plc_full = make_placebo(y_clin, rate_01, rate_10, rng)
        # two-level bootstrap: resample the test set too; identical test rows and permutations for all models
        te_b = te if args.fixed_test else rng.choice(te, size=len(te), replace=True)
        perms = {g: [rng.permutation(len(te_b)) for _ in range(3)] for g in groups}
        for mname, y in [("f_self", y_self), ("f_clin", y_clin), ("f_placebo", y_plc_full)]:
            if args.model == "logreg":
                from sklearn.impute import SimpleImputer
                from sklearn.linear_model import LogisticRegression
                from sklearn.pipeline import make_pipeline
                from sklearn.preprocessing import StandardScaler
                m = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                                  LogisticRegression(max_iter=5000, random_state=args.seed + b))
            else:
                m = XGBClassifier(random_state=args.seed + b, **params)
            m.fit(X.iloc[tb], y[tb])
            auc, imp = group_importance(m, X.iloc[te_b], y[te_b], groups, rng, perms=perms)
            tot = sum(max(v, 0) for v in imp.values()) or np.nan
            for gname, v in imp.items():
                rows.append({"boot": b, "model": mname, "auc": auc, "group": gname,
                             "importance": v, "share": max(v, 0) / tot})
        print(f"  bootstrap {b + 1}/{args.boot} done")
    long = pd.DataFrame(rows)
    long.to_csv(f"{args.out_dir}/bootstrap_long.csv", index=False)

    # P1 AUC
    auc = long.drop_duplicates(["boot", "model"]).groupby("model")["auc"].apply(lambda s: ci(s)).apply(pd.Series)
    auc.columns = ["auc_mean", "ci_low", "ci_high"]
    auc.round(4).to_csv(f"{args.out_dir}/P1_auc.csv")

    # P2 group importance per model
    p2 = []
    for (mname, gname), s in long.groupby(["model", "group"]):
        im, il, ih = ci(s["importance"])
        sm, sl, sh = ci(s["share"])
        p2.append({"model": mname, "group": gname, "importance": im, "imp_ci_low": il, "imp_ci_high": ih,
                   "share": sm, "share_ci_low": sl, "share_ci_high": sh})
    pd.DataFrame(p2).round(4).to_csv(f"{args.out_dir}/P2_group_importance.csv", index=False)
    # NOTE: intervals are two-level (training refit x test resample) unless --fixed-test

    # E1 (primary): absolute access AUC-drop f_self - f_clin, paired within each bootstrap draw;
    # met if the 2.5th percentile > 0 AND the share contrast f_self - f_placebo is positive (same direction)
    wa = long.pivot_table(index=["boot", "group"], columns="model", values="importance").reset_index()
    ws = long.pivot_table(index=["boot", "group"], columns="model", values="share").reset_index()
    acc_a, acc_s = wa[wa["group"] == "access"], ws[ws["group"] == "access"]
    if len(acc_a):
        d_abs = (acc_a["f_self"] - acc_a["f_clin"]).values
        d_sh = (acc_s["f_self"] - acc_s["f_placebo"]).values
        # share is undefined in a draw where all grouped importances are <= 0 (e.g. a near-chance placebo);
        # such draws are excluded from the share contrast and counted
        e1 = {"B": len(d_abs), "abs_self_minus_clin_mean": d_abs.mean(),
              "abs_lo_2.5": np.percentile(d_abs, 2.5), "abs_hi_97.5": np.percentile(d_abs, 97.5),
              "share_B_defined": int(np.isfinite(d_sh).sum()),
              "share_self_minus_placebo_mean": np.nanmean(d_sh) if np.isfinite(d_sh).any() else np.nan,
              "share_lo_2.5": np.nanpercentile(d_sh, 2.5) if np.isfinite(d_sh).any() else np.nan,
              "share_hi_97.5": np.nanpercentile(d_sh, 97.5) if np.isfinite(d_sh).any() else np.nan}
        # placebo contrast is interpretable only if the share is defined in >= 80% of draws 
        e1["placebo_share_interpretable"] = bool(e1["share_B_defined"] >= 0.8 * e1["B"])
        e1["E1_met"] = bool(e1["abs_lo_2.5"] > 0 and e1["placebo_share_interpretable"]
                            and e1["share_self_minus_placebo_mean"] > 0)
        e1["interval_type"] = "fixed-test training-resampling" if args.fixed_test else "two-level (train refit x test resample)"
        pd.DataFrame([e1]).to_csv(f"{args.out_dir}/E1_endpoint.csv", index=False)
        print("\n== E1\n", pd.DataFrame([e1]).T.to_string())

    # P3 paired contrasts (same bootstrap draw): self - clin, placebo - clin, excess = self - placebo
    wide = long.pivot_table(index=["boot", "group"], columns="model", values="share").reset_index()
    p3 = []
    for gname, s in wide.groupby("group"):
        for label, diff in [("share_self_minus_clin", s["f_self"] - s["f_clin"]),
                            ("share_placebo_minus_clin", s["f_placebo"] - s["f_clin"]),
                            ("share_self_minus_placebo", s["f_self"] - s["f_placebo"])]:
            m, lo, hi = ci(diff)
            p3.append({"group": gname, "contrast": label, "mean": m, "ci_low": lo, "ci_high": hi,
                       "ci_excludes_0": bool(lo > 0 or hi < 0)})
    p3 = pd.DataFrame(p3).round(4)
    p3.to_csv(f"{args.out_dir}/P3_contrasts.csv", index=False)

    write_manifest(args.out_dir, args, {"n": int(len(X)), "n_train": int(len(tr)), "n_test": int(len(te)),
                                        "rate_01": rate_01, "rate_10": rate_10})
    print("\n== P1 AUC\n", auc.round(3).to_string())
    print("\n== P2 share of importance (mean)\n",
          pd.DataFrame(p2).pivot(index="group", columns="model", values="share").round(3).to_string())
    print("\n== P3 contrasts\n", p3.to_string(index=False))


if __name__ == "__main__":
    main()
