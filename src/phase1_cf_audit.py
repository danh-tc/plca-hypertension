"""
Phase 1 - Counterfactual audit: do counterfactuals from the self-report model (f_self) route through
the two diagnosis channels found in Phase 0.5, and do they transfer to the examination-informed
model (f_clin) as well as to an independently trained model with the SAME label?

Design (discovery cycles 2011-2014, Y_self vs Y_clin140, chol_checked dropped - leak):
  * Models: f_self, f_clin on the same training rows; f_self_alt, f_clin_alt on a bootstrap of the
    training rows with another seed (within-label control for model multiplicity).
  * Queries: test individuals flagged high-risk (p >= 0.5) by BOTH f_self and f_clin, top-N by mean
    risk percentile -> identical query set for both models.
  * DiCE (random), 5 CFs per query, desired class 0, two modes:
      M0 global: everything mutable except age, sex, race
      M2 locked: M0 minus access, other_diagnoses, self_rated_health (diagnosis-channel features)
  * All features treated as continuous inside DiCE (as in Thieu 2026); binary/ordinal features are
    rounded afterwards and every CF is re-scored after rounding.

Transfer metric: risk-percentile reduction dr_m = F_m(f_m(x)) - F_m(f_m(x')), F_m = empirical CDF of
model m on the test set. ECD (per patient, then averaged over patients) = dr(own-label alt model) - dr(other-label alt model);
both evaluators are trained on the same bootstrap sample (symmetric). The earlier asymmetric
version (cross = other-label main model) is still reported as ECD_all_asym for comparison.

Usage:
    python src/phase1_cf_audit.py --data-dir data/raw --out-dir outputs/phase1 --n-queries 200
"""
import argparse
import os
import sys
import random
import time
import warnings

os.environ.setdefault("TQDM_DISABLE", "1")  # silence DiCE progress bars

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

sys.path.insert(0, os.path.dirname(__file__))
from phase0_nhanes import CYCLE_SETS, load_cycle, build_cycle  # noqa: E402
from phase05_model_reliance import build_features  # noqa: E402
from utils import write_manifest  # noqa: E402
from sklearn.metrics import roc_auc_score  # noqa: E402

warnings.filterwarnings("ignore")

IMMUTABLE = ["age", "female", "race_1", "race_2", "race_3", "race_4", "race_6", "race_7"]
ROUND_FEATURES = ["female", "race_1", "race_2", "race_3", "race_4", "race_6", "race_7", "insured",
                  "routine_place", "high_chol_told", "current_smoker", "vigorous_rec_pa",
                  "moderate_rec_pa", "education", "visits_past_year", "self_rated_health",
                  "drinks_per_day"]
# Explicit value schema (not inferred from imputed data)
BINARY_FEATURES = ["female", "race_1", "race_2", "race_3", "race_4", "race_6", "race_7", "insured",
                   "routine_place", "chol_checked", "high_chol_told", "current_smoker",
                   "vigorous_rec_pa", "moderate_rec_pa"]
INTEGER_FEATURES = ["education", "visits_past_year", "self_rated_health", "drinks_per_day"]
HALF_STEP_FEATURES = ["diabetes_told"]          # 0 / 0.5 (borderline) / 1
# "care-reducing" = moving these DOWN; "relabel" = un-diagnosing or better self-rated health
CARE_DOWN = ["insured", "routine_place", "visits_past_year"]
DX_DOWN = ["diabetes_told", "high_chol_told"]
SRH_BETTER_IS_DOWN = ["self_rated_health"]  # HUQ010: 1 excellent ... 5 poor

# T-HTN: hypertension guideline-informed directional taxonomy (spec: docs/taxonomy_THTN.md).
# Modes M1_taxonomy and M3_evidence.
# Every feature not listed is frozen.
#   up          : x -> [x, train max]                        (binary 0 -> 1)
#   down        : x -> [train min, x]                        (binary 1 -> 0)
#   down_floor1 : x > 1 -> [1, x], else frozen               (ALQ130 = drinks on drinking days)
#   down_to_T   : x > T -> [T, x], else frozen               (BMI: T = 23 if race_6 else 25;
#                                                             waist: T = 88 cm if female else 102 cm)
# M3_evidence adds: BMI and waist may fall by at most 5% (lower bound max(T, 0.95 x)).
# Features whose value was missing before median imputation are frozen per query (M1/M3 only).
THTN = {
    "insured": "up", "routine_place": "up",
    "current_smoker": "down", "drinks_per_day": "down_floor1",
    "moderate_rec_pa": "up", "vigorous_rec_pa": "up",
    "bmi": "down_to_T", "waist": "down_to_T",
}
THTN_MODES = ("M1_taxonomy", "M3_evidence")
# direction map used for the descriptive taxonomy_violation_pct
THTN_DIRECTION = {f: ("up" if t == "up" else "down") for f, t in THTN.items()}


def thtn_threshold(f, q):
    """Operational lower bound T for BMI / waist (AHA/ACC 2025 BMI classes; AHA/NHLBI 2005 waist cut-offs)."""
    if f == "bmi":
        asian = "race_6" in q and float(q["race_6"].iloc[0]) == 1.0   # NHANES RIDRETH3 = 6, Non-Hispanic Asian
        return 23.0 if asian else 25.0
    if f == "waist":
        return 88.0 if float(q["female"].iloc[0]) == 1.0 else 102.0
    raise KeyError(f)


def thtn_range(f, x, a, b, q, mode):
    """Permitted range under T-HTN for feature f with query value x and training range [a, b];
    None means frozen."""
    t = THTN.get(f)
    if t is None:
        return None
    if t == "up":
        return (x, b)
    if t == "down":
        return (a, x)
    if t == "down_floor1":
        return (max(a, 1.0), x) if x > 1.0 else None
    if t == "down_to_T":
        T = thtn_threshold(f, q)
        if x <= T:
            return None
        low = max(a, T)
        if mode == "M3_evidence":
            low = max(low, 0.95 * x)
        return (low, x)
    raise ValueError(t)


def query_ranges(q, mode, feats, lo, hi, groups, missing=()):
    """Return (features_to_vary, permitted_range) for one query under a mode.
    missing: features whose value was missing before imputation; frozen in T-HTN modes only."""
    vary, pr = [], {}
    for f in feats:
        if f in IMMUTABLE:
            continue
        x, a, b = float(q[f].iloc[0]), float(lo[f]), float(hi[f])
        if mode in THTN_MODES:
            if f in missing:
                continue
            r = thtn_range(f, x, a, b, q, mode)
            if r is None:
                continue
            rng_ = r
            if rng_[1] - rng_[0] > 1e-9:
                vary.append(f)
                pr[f] = [float(rng_[0]), float(rng_[1])]
            continue
        if mode == "M0_global":
            rng_ = (a, b)
        elif mode == "M2_locked":
            locked = groups.get("access", []) + groups.get("other_diagnoses", []) + groups.get("self_rated_health", [])
            if f in locked:
                continue
            rng_ = (a, b)
        elif mode == "M2_phys":
            # alternative feature-group restriction control: lock physiology only (not a negative control)
            if f in groups.get("physiology", []):
                continue
            rng_ = (a, b)
        else:
            raise ValueError(mode)
        if rng_[1] - rng_[0] > 1e-9:
            vary.append(f)
            pr[f] = [float(rng_[0]), float(rng_[1])]
    return vary, pr


def ecdf(ref):
    ref = np.sort(np.asarray(ref))
    return lambda p: np.searchsorted(ref, p, side="right") / len(ref)


def round_cf(df, cols):
    df = df.copy()
    for c in cols:
        if c in df:
            df[c] = df[c].round()
    if "diabetes_told" in df:
        df["diabetes_told"] = (df["diabetes_told"] * 2).round() / 2
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--out-dir", default="outputs/phase1")
    ap.add_argument("--n-queries", type=int, default=200)
    ap.add_argument("--n-cfs", type=int, default=5)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--cycles", choices=["discovery", "confirmation", "G", "H", "I", "J"], default="discovery",
                    help="cycle set; single cycles (G/H/I/J) for the per-cycle sensitivity")
    ap.add_argument("--model", choices=["xgb", "logreg"], default="xgb",
                    help="classifier family (logreg = sensitivity analysis)")
    ap.add_argument("--boot-patients", type=int, default=5000, help="patient bootstrap replicates")
    ap.add_argument("--min-common", type=int, default=40, help="minimum common patients for E3 inference and E4 ECD")
    ap.add_argument("--min-queries", type=int, default=80,
                    help="minimum eligible queries; below this E3/E4 are reported as not evaluable")
    ap.add_argument("--clin-label", choices=["clin140", "clin130"], default="clin140",
                    help="comparison label for f_clin (clin130 = threshold sensitivity)")
    ap.add_argument("--self-label", choices=["self", "self2"], default="self")
    ap.add_argument("--chol-reconstruct", action="store_true",
                    help="sensitivity: keep chol_checked rebuilt from the BPQ080 skip (pass --drop-features with no names)")
    ap.add_argument("--drop-features", nargs="*", default=["chol_checked"])
    ap.add_argument("--dice-method", choices=["random", "genetic"], default="random",
                    help="genetic = DiCE-algorithm sensitivity")
    ap.add_argument("--coverage-only", action="store_true",
                    help="fit models and write C3 coverage (E5) only; no CF generation (per-cycle E5)")
    ap.add_argument("--modes", nargs="*", default=["M0_global", "M1_taxonomy", "M2_locked"],
                    help="any of M0_global M1_taxonomy M2_locked M2_phys M3_evidence (M1/M3 = T-HTN)")
    ap.add_argument("--query-pool", choices=["all", "unmedicated", "clinpos_unmedicated"], default="unmedicated",
                    help="clinpos_unmedicated = sensitivity: Y_clin140 = 1 and not on BP medication")
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    import dice_ml  # imported here so --help works without it

    frames = [build_cycle(load_cycle(args.data_dir, s), s)[0] for s in CYCLE_SETS[args.cycles]]
    data = pd.concat(frames, ignore_index=True)
    if args.self_label == "self2":
        data = data[data["Y_self2"].notna()].reset_index(drop=True)
        data["Y_self"] = data["Y_self2"].astype(int)
    clin_col = {"clin140": "Y_clin140", "clin130": "Y_clin130"}[args.clin_label]
    X, groups = build_features(data, chol_reconstruct=args.chol_reconstruct)
    X = X.drop(columns=[c for c in args.drop_features if c in X.columns])
    X = X.drop(columns=[c for c in X.columns if X[c].notna().sum() == 0])
    groups = {k: [c for c in v if c in X.columns] for k, v in groups.items()}
    y = {"self": data["Y_self"].values, "clin": data[clin_col].values}
    grp = ("G" + data["Y_self"].astype(str) + data[clin_col].astype(str)).values

    idx = np.arange(len(X))
    tr, te = train_test_split(idx, test_size=0.3, random_state=args.seed, stratify=y["clin"])
    med = X.iloc[tr].median()
    Xi = X.fillna(med)  # DiCE cannot handle NaN; models for the CF audit are trained on imputed data
    params = dict(n_estimators=300, max_depth=4, learning_rate=0.05, subsample=0.8,
                  colsample_bytree=0.8, tree_method="hist", eval_metric="logloss", n_jobs=-1)
    rng = np.random.default_rng(args.seed)
    tr_alt = rng.choice(tr, size=len(tr), replace=True)
    def make_model(seed):
        if args.model == "logreg":
            from sklearn.linear_model import LogisticRegression
            from sklearn.pipeline import make_pipeline
            from sklearn.preprocessing import StandardScaler
            return make_pipeline(StandardScaler(), LogisticRegression(max_iter=5000, random_state=seed))
        return XGBClassifier(random_state=seed, **params)
    models = {}
    for lab in ["self", "clin"]:
        models[lab] = make_model(args.seed).fit(Xi.iloc[tr], y[lab][tr])
        models[f"{lab}_alt"] = make_model(args.seed + 1000).fit(Xi.iloc[tr_alt], y[lab][tr_alt])
    X_te = Xi.iloc[te]
    p_te = {k: m.predict_proba(X_te)[:, 1] for k, m in models.items()}
    F = {k: ecdf(v) for k, v in p_te.items()}

    # ---- coverage: who gets flagged at all (threshold 0.5 and matched screening budgets) ----
    from scipy.stats import binomtest
    cov = []
    rules = [("threshold_0.5", p_te["self"] >= 0.5, p_te["clin"] >= 0.5)]
    seqn_te = data["SEQN"].values[te]

    def topk(score, k_pct):
        """exactly round(k% of test) individuals; ties broken by ascending SEQN"""
        k = int(round(len(score) * k_pct / 100))
        order = np.lexsort((seqn_te, -score))
        flag = np.zeros(len(score), bool)
        flag[order[:k]] = True
        return flag
    for k in (10, 20, 30):
        rules.append((f"top_{k}pct", topk(p_te["self"], k), topk(p_te["clin"], k)))
    for rule, fs_all, fc_all in rules:
        for g in ["G00", "G01", "G10", "G11", "all"]:
            m = np.ones(len(te), bool) if g == "all" else grp[te] == g
            fs, fc = fs_all[m], fc_all[m]
            b, c = int((fs & ~fc).sum()), int((~fs & fc).sum())   # discordant pairs
            cov.append({"rule": rule, "group": g, "n_test": int(m.sum()),
                        "flagged_by_f_self_pct": round(100 * fs.mean(), 1) if m.any() else np.nan,
                        "flagged_by_f_clin_pct": round(100 * fc.mean(), 1) if m.any() else np.nan,
                        "self_only": b, "clin_only": c,
                        "mcnemar_exact_p": binomtest(b, b + c, 0.5).pvalue if b + c else np.nan})
    pd.DataFrame(cov).to_csv(f"{args.out_dir}/C3_coverage_by_group.csv", index=False)
    if args.coverage_only:
        write_manifest(args.out_dir, args, {"coverage_only": True})
        print("coverage-only run: C3 written, no CF generation")
        return

    # ---- matched query set ----
    both = (p_te["self"] >= 0.5) & (p_te["clin"] >= 0.5)
    if args.query_pool in ("unmedicated", "clinpos_unmedicated"):
        both &= data["on_med"].values[te] == 0
    if args.query_pool == "clinpos_unmedicated":
        both &= y["clin"][te] == 1
    score = (F["self"](p_te["self"]) + F["clin"](p_te["clin"])) / 2
    order = np.argsort(-score)
    q_pos = [i for i in order if both[i]][: args.n_queries]
    queries = X_te.iloc[q_pos]
    # pre-imputation missingness of each query (T-HTN freezes these features in M1/M3 only)
    q_missing = [set(X.columns[X.iloc[te[i]].isna().values]) for i in q_pos]
    qinfo = {"query_pool": args.query_pool, "n_queries": len(queries), "eligible": int(both.sum()),
             **{f"n_{k}": int(v) for k, v in pd.Series(grp[te][q_pos]).value_counts().items()},
             "mean_p0_self": float(p_te["self"][q_pos].mean()) if q_pos else np.nan,
             "mean_p0_clin": float(p_te["clin"][q_pos].mean()) if q_pos else np.nan}
    pd.DataFrame([qinfo]).to_csv(f"{args.out_dir}/C0_query_set.csv", index=False)
    pd.DataFrame({"query": range(len(q_pos)), "SEQN": data["SEQN"].values[te][q_pos].astype(int),
                  "group": grp[te][q_pos], "p0_self": p_te["self"][q_pos], "p0_clin": p_te["clin"][q_pos]}) \
        .to_csv(f"{args.out_dir}/C0_query_ids.csv", index=False)
    print("query set:", qinfo)
    if len(queries) < args.n_queries:
        print(f"[warn] only {len(queries)} eligible queries (< {args.n_queries})")
    qgroup = dict(enumerate(grp[te][q_pos]))

    feats = list(Xi.columns)
    lo, hi = Xi.iloc[tr].min(), Xi.iloc[tr].max()
    binary = [f for f in BINARY_FEATURES if f in feats]
    integer_only = [f for f in INTEGER_FEATURES if f in feats]
    integer = [f for f in ROUND_FEATURES if f in feats]
    rows, status_rows = [], []
    for src in ["self", "clin"]:
        dtrain = Xi.iloc[tr].copy()
        dtrain["y"] = y[src][tr]
        d = dice_ml.Data(dataframe=dtrain, continuous_features=feats, outcome_name="y")
        exp = dice_ml.Dice(d, dice_ml.Model(model=models[src], backend="sklearn"), method=args.dice_method)
        for mode in args.modes:
            t0 = time.time()
            for qi in range(len(queries)):
                q = queries.iloc[[qi]]
                fv, prange = query_ranges(q, mode, feats, lo, hi, groups, missing=q_missing[qi])
                st = {"source": src, "mode": mode, "query": qi, "group": qgroup[qi], "n_vary": len(fv),
                      "status": None, "n_returned": 0, "error_type": "", "error_message": ""}
                cfs = None
                if not fv:
                    st["status"] = "no_actionable_features"
                else:
                    try:
                        if args.dice_method == "random":
                            res = exp.generate_counterfactuals(q, total_CFs=args.n_cfs, desired_class=0,
                                                               features_to_vary=fv, permitted_range=prange,
                                                               random_seed=args.seed + qi, verbose=False)
                        else:   # DiCE genetic has no random_seed argument: seed the global RNGs per query
                            np.random.seed(args.seed + qi)
                            random.seed(args.seed + qi)
                            res = exp.generate_counterfactuals(q, total_CFs=args.n_cfs, desired_class=0,
                                                               features_to_vary=fv, permitted_range=prange,
                                                               verbose=False)
                        cfs = res.cf_examples_list[0].final_cfs_df
                        st["status"] = "success" if cfs is not None and len(cfs) else "no_cf_found"
                    except Exception as e:  # noqa: BLE001
                        msg = str(e)
                        # DiCE 0.12 signals "search found nothing" by raising this exception
                        if type(e).__name__ == "UserConfigValidationException" and "No counterfactuals found" in msg:
                            st["status"] = "no_cf_found"
                        else:
                            st["status"] = "exception"
                        st["error_type"], st["error_message"] = type(e).__name__, msg[:300]
                        cfs = None
                status_rows.append(st)
                if st["status"] != "success":
                    continue
                cfs = cfs[feats].astype(float).reset_index(drop=True)
                # round ONLY features that were allowed to vary; everything else is reset to the query value
                cfs = round_cf(cfs, [c for c in integer if c in fv])
                if "diabetes_told" not in fv and "diabetes_told" in cfs:
                    cfs["diabetes_told"] = q["diabetes_told"].iloc[0]
                for f in feats:
                    if f not in fv:
                        cfs[f] = q[f].iloc[0]
                st["n_returned"] = len(cfs)
                p0 = {k: float(m.predict_proba(q)[:, 1][0]) for k, m in models.items()}
                p1 = {k: m.predict_proba(cfs)[:, 1] for k, m in models.items()}
                delta = cfs.values - q.values
                for j in range(len(cfs)):
                    # post-processing constraint check
                    ok_c = True
                    for n, f in enumerate(feats):
                        v = cfs[f].iloc[j]
                        if f in fv:
                            a, b = prange[f]
                            ok_c &= (a - 1e-6) <= v <= (b + 1e-6)
                        else:
                            ok_c &= abs(delta[j, n]) < 1e-9
                        if f in fv:   # value-type check only where the CF may change the value
                            if f in binary:
                                ok_c &= v in (0.0, 1.0)
                            elif f in integer_only:
                                ok_c &= float(v).is_integer()
                            elif f in HALF_STEP_FEATURES:
                                ok_c &= v in (0.0, 0.5, 1.0)
                    rec = {"source": src, "mode": mode, "query": qi, "group": qgroup[qi], "cf": j,
                           "constraint_valid": bool(ok_c), "model_valid": bool(p1[src][j] < 0.5)}
                    rec["valid_recourse"] = rec["constraint_valid"] and rec["model_valid"]
                    rec.update({f"d_{f}": float(delta[j, n]) for n, f in enumerate(feats)})
                    rec.update({f"x0_{f}": float(q[f].iloc[0]) for f in ("bmi", "total_chol", "hba1c")})
                    for k in models:
                        rec[f"p0_{k}"], rec[f"p1_{k}"] = p0[k], float(p1[k][j])
                        rec[f"dr_{k}"] = float(F[k](p0[k]) - F[k](p1[k][j]))
                    rows.append(rec)
            print(f"  {src} {mode}: {len(queries)} queries in {time.time() - t0:.0f}s")
    long = pd.DataFrame(rows)
    long.to_csv(f"{args.out_dir}/cf_long.csv", index=False)
    stat = pd.DataFrame(status_rows)
    stat.to_csv(f"{args.out_dir}/C5_generation_status.csv", index=False)

    # ---- summaries (unit of analysis = patient; symmetric evaluators = both bootstrap-trained alt models) ----
    other = {"self": "clin", "clin": "self"}
    brng = np.random.default_rng(args.seed)

    def pboot(per_q, B=args.boot_patients):
        v = np.asarray(per_q, float)
        if len(v) == 0:
            return np.nan, np.nan, np.nan
        bs = [v[brng.integers(0, len(v), len(v))].mean() for _ in range(B)]
        return float(v.mean()), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))

    def per_patient_ecd(h, src, symmetric=True):
        cross = f"dr_{other[src]}_alt" if symmetric else f"dr_{other[src]}"
        return (h[f"dr_{src}_alt"] - h[cross]).groupby(h["query"]).mean()

    summ, fchg = [], []
    for (src, mode), st_g in stat.groupby(["source", "mode"]):
        n_q = st_g["query"].nunique()
        rec = {"source": f"f_{src}", "mode": mode, "n_queries": n_q}
        for k in ["success", "no_cf_found", "exception", "no_actionable_features"]:
            rec[f"status_{k}_pct"] = round(100 * (st_g["status"] == k).mean(), 1)
        g = long[(long["source"] == src) & (long["mode"] == mode)] if len(long) else long
        rec["returned_cf_pct"] = round(100 * g["query"].nunique() / n_q, 1) if len(g) else 0.0
        rec["valid_recourse_coverage_pct"] = 0.0
        if len(g):
            vr = g[g["valid_recourse"]]
            rec["valid_recourse_coverage_pct"] = round(100 * vr["query"].nunique() / n_q, 1)
            rec["constraint_valid_cf_pct"] = round(100 * g["constraint_valid"].mean(), 1)
            rec["model_valid_cf_pct"] = round(100 * g["model_valid"].mean(), 1)
            for label, h, sym in [("all", g, True), ("valid", vr, True), ("all_asym", g, False)]:
                m, l, u = pboot(per_patient_ecd(h, src, sym)) if len(h) else (np.nan,) * 3
                rec[f"ECD_{label}"], rec[f"ECD_{label}_lo"], rec[f"ECD_{label}_hi"] = m, l, u
            rec["ECD_valid_n_patients"] = vr["query"].nunique()
            desc = vr if len(vr) else g     # descriptive rates on valid recourse CFs (fallback: all returned)
            rec["descriptives_on"] = "valid_recourse" if len(vr) else "all_returned"
            rec["flip_within_pct"] = 100 * (desc[f"p1_{src}_alt"] < 0.5).mean()
            rec["flip_cross_pct"] = 100 * (desc[f"p1_{other[src]}_alt"] < 0.5).mean()
            for gname, cols in groups.items():
                ch = np.zeros(len(desc), dtype=bool)
                for c in cols:
                    ch |= desc[f"d_{c}"].abs().values > 1e-9
                rec[f"uses_{gname}_pct"] = 100 * ch.mean()
            down = lambda cols: np.any([desc[f"d_{c}"].values < -1e-9 for c in cols if f"d_{c}" in desc], axis=0)  # noqa: E731
            rec["care_reducing_pct"] = 100 * down(CARE_DOWN).mean()
            rec["undiagnose_pct"] = 100 * down(DX_DOWN).mean()
            rec["srh_better_pct"] = 100 * down(SRH_BETTER_IS_DOWN).mean()
            bmi_rel = desc["d_bmi"] / desc["x0_bmi"]
            rec["bmi_rel_change_mean_pct"] = 100 * bmi_rel.mean()
            rec["bmi_drop_gt10pct_pct"] = 100 * (bmi_rel < -0.10).mean()
            rec["chol_increase_pct"] = 100 * (desc["d_total_chol"] > 1e-9).mean()
            rec["hba1c_increase_pct"] = 100 * (desc["d_hba1c"] > 1e-9).mean()
            viol = np.zeros(len(desc), dtype=bool)
            for f, t in THTN_DIRECTION.items():
                if f"d_{f}" not in desc:
                    continue
                dd = desc[f"d_{f}"].values
                viol |= (dd < -1e-9) if t == "up" else (dd > 1e-9) if t == "down" else \
                    (np.abs(dd) > 1e-9) if t == "frozen" else np.zeros(len(dd), bool)
            rec["taxonomy_violation_pct"] = 100 * viol.mean()
            for f in feats:
                dd = desc[f"d_{f}"]
                fchg.append({"source": f"f_{src}", "mode": mode, "feature": f,
                             "changed_pct": 100 * (dd.abs() > 1e-9).mean(),
                             "decrease_pct": 100 * (dd < -1e-9).mean(),
                             "increase_pct": 100 * (dd > 1e-9).mean(),
                             "mean_delta_when_changed": dd[dd.abs() > 1e-9].mean() if (dd.abs() > 1e-9).any() else np.nan})
        summ.append(rec)
    summ = pd.DataFrame(summ)
    summ.round(4).to_csv(f"{args.out_dir}/C1_summary.csv", index=False)
    pd.DataFrame(fchg).round(3).to_csv(f"{args.out_dir}/C2_feature_changes.csv", index=False)

    # ---- paired mode comparison on common patients (valid recourse in BOTH modes) ----
    c4 = []
    if len(long):
        for src in ["self", "clin"]:
            for mode in [m for m in args.modes if m != "M0_global"]:
                a = long[(long["source"] == src) & (long["mode"] == "M0_global") & long["valid_recourse"]]
                b = long[(long["source"] == src) & (long["mode"] == mode) & long["valid_recourse"]]
                ea, eb = per_patient_ecd(a, src), per_patient_ecd(b, src)
                common = ea.index.intersection(eb.index)
                m, l, u = pboot(ea[common] - eb[common])
                c4.append({"source": f"f_{src}", "comparison": f"M0_global - {mode}", "n_common": len(common),
                           "ECD_M0": ea[common].mean() if len(common) else np.nan,
                           "ECD_mode": eb[common].mean() if len(common) else np.nan,
                           "diff": m, "diff_lo": l, "diff_hi": u})
    pd.DataFrame(c4).round(4).to_csv(f"{args.out_dir}/C4_paired_modes.csv", index=False)

    # ---- E3 (primary) and E4 (descriptive) on common patients ----
    # E3: one-sided test via the 2.5th percentile of the patient bootstrap.
    # E4: recourse feasibility under T-HTN (coverage M1 vs M0) and ECD_self(M0) - ECD_self(M1), descriptive.
    def valid_ecd(src, mode, valid_only=True):
        if not len(long):
            return pd.Series(dtype=float)
        h = long[(long["source"] == src) & (long["mode"] == mode)]
        if valid_only:
            h = h[h["valid_recourse"]]
        return per_patient_ecd(h, src) if len(h) else pd.Series(dtype=float)

    def joint_boot(mat, B=args.boot_patients):
        """mat: (n, k) per-patient statistics -> means and 2.5th percentiles of column means, same resamples"""
        n = len(mat)
        if n == 0:
            return np.full(mat.shape[1], np.nan), np.full(mat.shape[1], np.nan)
        bs = np.array([mat[brng.integers(0, n, n)].mean(axis=0) for _ in range(B)])
        return mat.mean(axis=0), np.percentile(bs, 2.5, axis=0)

    ends = []
    n_q_total = len(queries)
    enough_queries = n_q_total >= args.min_queries   # feasibility rule (>= 80 queries)
    # primary = valid recourse CFs; sensitivity = all returned CFs (same paired construction)
    for cf_set in ("valid_recourse", "all_returned"):
        vo = cf_set == "valid_recourse"
        tag = "" if vo else "_all_returned"
        if {"M0_global", "M2_locked"} <= set(args.modes):
            e = {m: {src: valid_ecd(src, m, vo) for src in ("self", "clin")} for m in ("M0_global", "M2_locked")}
            s_m0 = e["M0_global"]["self"].index.intersection(e["M0_global"]["clin"].index)
            s_m2 = e["M2_locked"]["self"].index.intersection(e["M2_locked"]["clin"].index)
            s_star = s_m0.intersection(s_m2)
            a0 = (e["M0_global"]["self"][s_star] - e["M0_global"]["clin"][s_star]).values
            a2 = (e["M2_locked"]["self"][s_star] - e["M2_locked"]["clin"][s_star]).values
            mat = np.column_stack([a0, a0 - a2, a0 + a2]) if len(s_star) else np.empty((0, 3))
            mean, lb = joint_boot(mat)
            ok = enough_queries and len(s_star) >= args.min_common
            ends.append({"endpoint": "E3" + tag, "cf_set": cf_set, "n_queries": n_q_total,
                         "n_common": len(s_star), "retention_pct": 100 * len(s_star) / max(n_q_total, 1),
                         "A_M0": mean[0], "A_M0_lb": lb[0], "A_M0_minus_A_M2": mean[1], "A_M0_minus_A_M2_lb": lb[1],
                         "A_M0_plus_A_M2": mean[2], "A_M0_plus_A_M2_lb": lb[2],
                         "A_M2": float(np.mean(a2)) if len(a2) else np.nan,
                         "ECD_self_M0": e["M0_global"]["self"][s_star].mean(), "ECD_clin_M0": e["M0_global"]["clin"][s_star].mean(),
                         "ECD_self_M2": e["M2_locked"]["self"][s_star].mean(), "ECD_clin_M2": e["M2_locked"]["clin"][s_star].mean(),
                         "met": ok and bool(np.all(lb > 0)), "inference_ok": ok})
        if {"M0_global", "M1_taxonomy"} <= set(args.modes):
            e0, e1m = valid_ecd("self", "M0_global", vo), valid_ecd("self", "M1_taxonomy", vo)
            common = e0.index.intersection(e1m.index)
            mat = np.column_stack([(e0[common] - e1m[common]).values, e1m[common].values]) if len(common) else np.empty((0, 2))
            mean, lb = joint_boot(mat)
            ok = enough_queries and len(common) >= args.min_common
            ends.append({"endpoint": "E4" + tag, "cf_set": cf_set, "n_queries": n_q_total,
                         "n_common": len(common), "retention_pct": 100 * len(common) / max(n_q_total, 1),
                         "ECD_self_M0_minus_M1": mean[0], "ECD_self_M0_minus_M1_lb": lb[0],
                         "ECD_self_M1_residual": mean[1], "ECD_self_M1_residual_lb": lb[1],
                         "valid_coverage_M0_pct": e0.index.size / max(n_q_total, 1) * 100,
                         "valid_coverage_M1_pct": e1m.index.size / max(n_q_total, 1) * 100,
                         "role": "descriptive", "met": np.nan, "inference_ok": ok})
    pd.DataFrame(ends).to_csv(f"{args.out_dir}/C6_endpoints_E3_E4.csv", index=False)

    # ---- sensitivity: alternative feature-group restriction (M2_phys) on the common set of M0, M2, M2_phys ----
    c9 = []
    if {"M0_global", "M2_locked", "M2_phys"} <= set(args.modes):
        modes3 = ("M0_global", "M2_locked", "M2_phys")
        e = {m: {src: valid_ecd(src, m) for src in ("self", "clin")} for m in modes3}
        common = None
        for m in modes3:
            sm = e[m]["self"].index.intersection(e[m]["clin"].index)
            common = sm if common is None else common.intersection(sm)
        A = {m: (e[m]["self"][common] - e[m]["clin"][common]).values for m in modes3}
        if len(common):
            mat = np.column_stack([A["M0_global"], A["M2_locked"], A["M2_phys"],
                                   A["M0_global"] - A["M2_locked"], A["M0_global"] - A["M2_phys"],
                                   A["M2_phys"] - A["M2_locked"]])
            n = len(mat)
            bs = np.array([mat[brng.integers(0, n, n)].mean(axis=0) for _ in range(args.boot_patients)])
            lo, hi = np.percentile(bs, 2.5, axis=0), np.percentile(bs, 97.5, axis=0)
            names = ["A_M0", "A_M2", "A_M2phys", "A_M0_minus_A_M2", "A_M0_minus_A_M2phys", "A_M2phys_minus_A_M2"]
            for k, nm in enumerate(names):
                c9.append({"quantity": nm, "n_common": n, "retention_pct": 100 * n / max(len(queries), 1),
                           "mean": mat[:, k].mean(), "lo_2.5": lo[k], "hi_97.5": hi[k]})
            # descriptive magnitude contrast D = |A(M2_phys)| - |A(M2)| on the same patients and resamples.
            # Reported with the signed components; its interval is NOT interpreted (|.| is non-regular near 0).
            d_bs = np.abs(bs[:, 2]) - np.abs(bs[:, 1])
            c9.append({"quantity": "D_absA_M2phys_minus_absA_M2 (descriptive)", "n_common": n,
                       "retention_pct": 100 * n / max(len(queries), 1),
                       "mean": abs(mat[:, 2].mean()) - abs(mat[:, 1].mean()),
                       "lo_2.5": np.percentile(d_bs, 2.5), "hi_97.5": np.percentile(d_bs, 97.5)})
            for m in modes3:
                for src in ("self", "clin"):
                    c9.append({"quantity": f"ECD_{src}_{m}", "n_common": n, "mean": e[m][src][common].mean()})
        else:
            c9.append({"quantity": "no common patients", "n_common": 0})
    pd.DataFrame(c9).to_csv(f"{args.out_dir}/C9_alt_restriction_M2phys.csv", index=False)

    # ---- descriptive: cross-label transfer split by diagnosis-channel use (valid recourse CFs) ----
    c7 = []
    if len(long):
        vr_all = long[long["valid_recourse"]].copy()
        care = np.any([vr_all[f"d_{c}"] < -1e-9 for c in CARE_DOWN if f"d_{c}" in vr_all], axis=0)
        dxd = np.any([vr_all[f"d_{c}"] < -1e-9 for c in DX_DOWN if f"d_{c}" in vr_all], axis=0)
        srh = vr_all["d_self_rated_health"] < -1e-9 if "d_self_rated_health" in vr_all else False
        # directional definition: moves access/diagnosis DOWN or self-rated health toward "better"
        vr_all["channel_directional"] = np.where(care | dxd | srh, "uses_channel", "no_channel")
        # any-change definition: same rule as uses_<group>_pct in C1 (any change in access,
        # other_diagnoses or self_rated_health features, in either direction)
        chan_cols = [c for gname in ("access", "other_diagnoses", "self_rated_health")
                     for c in groups.get(gname, []) if f"d_{c}" in vr_all]
        anych = np.any([vr_all[f"d_{c}"].abs() > 1e-9 for c in chan_cols], axis=0) if chan_cols else False
        vr_all["channel_any_change"] = np.where(anych, "uses_channel", "no_channel")
        for defn in ("channel_directional", "channel_any_change"):
          for (src, mode, ch), h in vr_all.groupby(["source", "mode", defn]):
            c7.append({"definition": defn, "source": f"f_{src}", "mode": mode, "subset": ch, "n_cfs": len(h), "n_patients": h["query"].nunique(),
                       "dr_within_alt": h[f"dr_{src}_alt"].mean(), "dr_cross_alt": h[f"dr_{other[src]}_alt"].mean(),
                       "flip_cross_alt_pct": 100 * (h[f"p1_{other[src]}_alt"] < 0.5).mean()})
    pd.DataFrame(c7).round(4).to_csv(f"{args.out_dir}/C7_transfer_by_channel.csv", index=False)

    # ---- E6 (secondary): paired counterfactual feature-group ablation on M0 valid CFs ----
    # x'_abl = x' with a feature group reset to the query value; C_m = F_m(f_m,alt(x'_abl)) - F_m(f_m,alt(x'))
    # D_i^(s) = mean_j (C_self - C_clin) over CFs of source s; D_i = (D^(self) + D^(clin)) / 2; E6 = mean_i D_i.
    # Identity on the same patients/CFs: A(M0) - A_ablated = 2 * E6.
    c10 = []
    n_q_total = len(queries)
    E6_COLS = ["E6", "E6_lb", "E6_hi", "D_self_source", "D_self_lb", "D_self_hi", "D_clin_source", "D_clin_lb",
               "D_clin_hi", "A_M0", "A_ablated", "A_M0_minus_A_ablated", "check_2xE6", "absA_M0_minus_absA_ablated",
               "cfs_touching_group_pct_self", "cfs_touching_group_pct_clin"]

    def empty_row(gname, setname):
        primary = gname == "diag_all" and setname == "S_M0"
        return {"ablation": gname, "set": setname, "role": "E6 endpoint" if primary else "descriptive",
                "n_queries": n_q_total, "n_patients": 0, "retention_pct": 0.0, **{c: np.nan for c in E6_COLS},
                "inference_ok": False if primary else np.nan, "met": False if primary else np.nan}
    m0v = long[(long["mode"] == "M0_global") & long["valid_recourse"]].copy() if len(long) else long
    if len(m0v) and "M0_global" in args.modes:
        dcols = [f"d_{f}" for f in feats]
        qvals = queries[feats].values
        x_cf = qvals[m0v["query"].values] + m0v[dcols].values
        x_q = qvals[m0v["query"].values]
        diag = {"diag_all": groups.get("access", []) + groups.get("other_diagnoses", []) + groups.get("self_rated_health", []),
                "access_only": groups.get("access", []), "other_dx_only": groups.get("other_diagnoses", []),
                "srh_only": groups.get("self_rated_health", [])}
        p_cf = {m: models[f"{m}_alt"].predict_proba(pd.DataFrame(x_cf, columns=feats))[:, 1] for m in ("self", "clin")}
        # integrity: CF rebuilt from query + delta must reproduce the stored CF scores
        recon_err = max(float(np.max(np.abs(p_cf[m] - m0v[f"p1_{m}_alt"].values))) for m in ("self", "clin"))
        s_self = set(m0v[m0v["source"] == "self"]["query"]); s_clin = set(m0v[m0v["source"] == "clin"]["query"])
        s_m0 = sorted(s_self & s_clin)
        s_star_set = None
        if "M2_locked" in args.modes:
            m2v = long[(long["mode"] == "M2_locked") & long["valid_recourse"]]
            s_star_set = set(m2v[m2v["source"] == "self"]["query"]) & set(m2v[m2v["source"] == "clin"]["query"]) & set(s_m0)
        enough = n_q_total >= args.min_queries
        for gname, cols in diag.items():
            idx_c = [feats.index(c) for c in cols if c in feats]
            if not idx_c:
                continue
            x_abl = x_cf.copy()
            x_abl[:, idx_c] = x_q[:, idx_c]
            touched = np.any(np.abs(x_cf[:, idx_c] - x_q[:, idx_c]) > 1e-9, axis=1)
            other_idx = [k for k in range(len(feats)) if k not in idx_c]
            # integrity: ablation changes only the chosen group
            abl_only_group = bool(np.allclose(x_abl[:, other_idx], x_cf[:, other_idx]))
            h = m0v[["source", "query", "cf"]].copy()
            for m in ("self", "clin"):
                p_abl = models[f"{m}_alt"].predict_proba(pd.DataFrame(x_abl, columns=feats))[:, 1]
                h[f"C_{m}"] = F[f"{m}_alt"](p_abl) - F[f"{m}_alt"](p_cf[m])
                # A_ablated components: ablated reduction dr_abl = dr - C
                h[f"dr_{m}_alt"] = m0v[f"dr_{m}_alt"].values
                h[f"dr_abl_{m}_alt"] = h[f"dr_{m}_alt"] - h[f"C_{m}"]
            h["touched"] = touched
            max_abs_C_untouched = float(np.max(np.abs(h.loc[~touched, ["C_self", "C_clin"]].values))) if (~touched).any() else 0.0
            h["dC"] = h["C_self"] - h["C_clin"]
            per_s = h.groupby(["query", "source"])["dC"].mean().unstack()
            own = {"self": "self", "clin": "clin"}
            # ECD per source (original and ablated), same patients/CFs
            def ecd(col_prefix, src):
                hh = h[h["source"] == src]
                o = "clin" if src == "self" else "self"
                return (hh[f"{col_prefix}_{src}_alt"] - hh[f"{col_prefix}_{o}_alt"]).groupby(hh["query"]).mean()
            for setname, pats in [("S_M0", s_m0), ("S_star", sorted(s_star_set) if s_star_set is not None else None)]:
                if pats is None or gname != "diag_all" and setname != "S_M0":
                    continue
                pats = [q for q in pats if q in per_s.index]
                if not pats:
                    c10.append({**empty_row(gname, setname), "recon_max_abs_err": recon_err})
                    continue
                d_self, d_clin = per_s.loc[pats, "self"].values, per_s.loc[pats, "clin"].values
                d_i = (d_self + d_clin) / 2
                a0 = (ecd("dr", "self")[pats] - ecd("dr", "clin")[pats]).values
                aab = (ecd("dr_abl", "self")[pats] - ecd("dr_abl", "clin")[pats]).values
                n = len(d_i)
                bs = np.array([np.column_stack([d_i, d_self, d_clin])[brng.integers(0, n, n)].mean(axis=0)
                               for _ in range(args.boot_patients)])
                lo, hi = np.percentile(bs, 2.5, axis=0), np.percentile(bs, 97.5, axis=0)
                primary = gname == "diag_all" and setname == "S_M0"
                ok = enough and n >= args.min_common
                hp = h[h["query"].isin(pats)]
                c10.append({"ablation": gname, "set": setname, "role": "E6 endpoint" if primary else "descriptive",
                            "n_queries": n_q_total, "n_patients": n, "retention_pct": 100 * n / max(n_q_total, 1),
                            "E6": d_i.mean(), "E6_lb": lo[0], "E6_hi": hi[0],
                            "D_self_source": d_self.mean(), "D_self_lb": lo[1], "D_self_hi": hi[1],
                            "D_clin_source": d_clin.mean(), "D_clin_lb": lo[2], "D_clin_hi": hi[2],
                            "A_M0": a0.mean(), "A_ablated": aab.mean(),
                            "A_M0_minus_A_ablated": a0.mean() - aab.mean(), "check_2xE6": 2 * d_i.mean(),
                            "absA_M0_minus_absA_ablated": abs(a0.mean()) - abs(aab.mean()),
                            "cfs_touching_group_pct_self": 100 * hp[hp["source"] == "self"]["touched"].mean(),
                            "cfs_touching_group_pct_clin": 100 * hp[hp["source"] == "clin"]["touched"].mean(),
                            "inference_ok": ok if primary else np.nan,
                            "met": (ok and bool(lo[0] > 0)) if primary else np.nan,
                            "recon_max_abs_err": recon_err, "ablation_changes_only_group": abl_only_group,
                            "max_abs_C_untouched": max_abs_C_untouched})
    if not c10 and "M0_global" in args.modes:
        c10.append(empty_row("diag_all", "S_M0"))      # no valid M0 CFs at all: E6 not evaluable
    pd.DataFrame(c10).to_csv(f"{args.out_dir}/C10_ablation.csv", index=False)

    write_manifest(args.out_dir, args, {"model": args.model, "n": int(len(X)), "n_train": int(len(tr)), "n_test": int(len(te)),
                                        "n_queries": len(queries),
                                        "auc_test": {k: float(roc_auc_score(y[k.replace('_alt', '')][te], v))
                                                     for k, v in p_te.items()}})
    pd.set_option("display.width", 250)
    print("\n== C5 generation status\n", stat.groupby(["source", "mode"])["status"].value_counts().unstack(fill_value=0).to_string())
    print("\n== C1 summary\n", summ.round(3).T.to_string())
    print("\n== C4 paired modes\n", pd.DataFrame(c4).round(3).to_string(index=False))
    print("\n== C3 coverage (G01)\n", pd.DataFrame(cov).query("group == 'G01'").to_string(index=False))
    print("\n== C6 endpoints\n", pd.DataFrame(ends).T.to_string())
    print("\n== C7 transfer by channel\n", pd.DataFrame(c7).round(3).to_string(index=False))
    print("\n== C9 M2_phys (alternative restriction)\n", pd.DataFrame(c9).round(4).to_string(index=False))
    print("\n== C10 E6 ablation\n", pd.DataFrame(c10).round(4).T.to_string())


if __name__ == "__main__":
    main()
