"""
POST HOC reporting analysis (added for IJMEDI checklist items 9, 11, 13, 19, 22). Not an endpoint.

Reports, for one NHANES period (discovery 2011-2014 or confirmation 2015-2018):
  1. Classification performance of the models whose explanations PLCA audits, on the 30% test split:
     AUROC, AUPRC, accuracy, balanced accuracy, sensitivity, specificity, PPV, NPV and prevalence,
     at the FIXED threshold 0.5 (the same threshold used for counterfactual queries).
  2. Calibration: Brier score, calibration intercept (calibration-in-the-large, slope fixed at 1)
     and calibration slope (logistic recalibration on logit p), decile table and a vector PDF plot.
  3. Data characteristics of the analytic sample: feature dictionary, distribution, missingness
     (overall, train, test) and class balance.

Models are refitted exactly as in the pipeline (same cycles, features, seed, 70/30 split stratified
by Y_clin, hyperparameters); nothing in the original results folders is read for modelling or
overwritten. Two model families:
  * "cf_audit"   : XGBoost on median-imputed features (imputation medians from the training split),
                   seed 42 -- the models explained in E2/E3/E4/E5. Their test AUROC is checked against
                   auc_test in results/<period>/cf_primary/seed42/run_manifest.json; the script STOPS
                   if any difference exceeds --tol-exact (default 0.001).
  * "model_level": XGBoost with native missing-value handling (the E1 model), one fit on the full
                   training split, seed 42. E1 itself reports the mean over bootstrap refits
                   (results/<period>/model_level/baseline/P1_auc.csv), so this comparison is a
                   consistency check only (warning if |diff| > --tol-consistency, default 0.005).

Confidence intervals: percentile bootstrap of the TEST set (B = --boot, default 1000) with the fitted
model held fixed, i.e. conditional on the trained model; they do not include retraining variability.
All statistics are unweighted (analytic sample, not survey-weighted).

Usage:
    python src/posthoc_performance.py --data-dir data/raw --period confirmation \
        --ref-dir results/confirmation --out-dir outputs_posthoc/performance/confirmation
"""
import argparse
import json
import os
import sys

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

sys.path.insert(0, os.path.dirname(__file__))
from phase0_nhanes import CYCLE_SETS, build_cycle, load_cycle  # noqa: E402
from phase05_model_reliance import build_features  # noqa: E402
from utils import write_manifest  # noqa: E402

SEED = 42
THRESHOLD = 0.5
PARAMS = dict(n_estimators=300, max_depth=4, learning_rate=0.05, subsample=0.8,
              colsample_bytree=0.8, tree_method="hist", eval_metric="logloss", n_jobs=-1)
DROP_FEATURES = ["chol_checked"]          # pipeline default (structural skip; see Methods)
LABELS = {"f_self": "Y_self", "f_clin": "Y_clin140"}

# Feature dictionary (definitions follow build_features in phase05_model_reliance.py)
DICTIONARY = {
    "age": ("demographic_SES", "RIDAGEYR", "continuous", "years", "Age at screening"),
    "female": ("demographic_SES", "RIAGENDR", "binary", "", "Sex recorded by NHANES (1 = female)"),
    "race_1": ("demographic_SES", "RIDRETH3=1", "binary", "", "Mexican American"),
    "race_2": ("demographic_SES", "RIDRETH3=2", "binary", "", "Other Hispanic"),
    "race_3": ("demographic_SES", "RIDRETH3=3", "binary", "", "Non-Hispanic White"),
    "race_4": ("demographic_SES", "RIDRETH3=4", "binary", "", "Non-Hispanic Black"),
    "race_6": ("demographic_SES", "RIDRETH3=6", "binary", "", "Non-Hispanic Asian"),
    "race_7": ("demographic_SES", "RIDRETH3=7", "binary", "", "Other race, including multiracial"),
    "education": ("demographic_SES", "DMDEDUC2", "ordinal", "1-5", "Education level (codes 7/9 -> missing)"),
    "income_pir": ("demographic_SES", "INDFMPIR", "continuous", "ratio", "Family income-to-poverty ratio"),
    "insured": ("access", "HIQ011", "binary", "", "Covered by health insurance"),
    "routine_place": ("access", "HUQ030", "binary", "", "Has a routine place for health care"),
    "visits_past_year": ("access", "HUQ051/HUQ050", "ordinal", "category 0-8",
                         "Health-care visits in past year (NHANES category, not a count)"),
    "chol_checked": ("access", "BPQ060", "binary", "", "Ever had cholesterol checked (dropped by default)"),
    "diabetes_told": ("other_diagnoses", "DIQ010", "ordinal", "0/0.5/1", "Told diabetes (0.5 = borderline)"),
    "high_chol_told": ("other_diagnoses", "BPQ080", "binary", "", "Told high cholesterol"),
    "current_smoker": ("lifestyle", "SMQ020/SMQ040", "binary", "", "Current smoker (never smokers = 0)"),
    "drinks_per_day": ("lifestyle", "ALQ130 (+ALQ101/ALQ111)", "continuous", "drinks/day",
                       "Average drinks per drinking day (never drinkers = 0)"),
    "vigorous_rec_pa": ("lifestyle", "PAQ650", "binary", "", "Any vigorous recreational activity"),
    "moderate_rec_pa": ("lifestyle", "PAQ665", "binary", "", "Any moderate recreational activity"),
    "bmi": ("physiology", "BMXBMI", "continuous", "kg/m2", "Body mass index"),
    "waist": ("physiology", "BMXWAIST", "continuous", "cm", "Waist circumference"),
    "total_chol": ("physiology", "LBXTC", "continuous", "mg/dL (x0.02586 = mmol/L)", "Total cholesterol"),
    "hba1c": ("physiology", "LBXGH", "continuous", "% (NGSP)", "Glycated haemoglobin"),
    "self_rated_health": ("self_rated_health", "HUQ010", "ordinal", "1-5 (1 = excellent)",
                          "Self-rated general health"),
}
# Missingness arising from questionnaire skip logic that the feature builder resolves explicitly
SKIP_RESOLVED = {
    "current_smoker": "SMQ040 skipped for never smokers -> set to 0",
    "drinks_per_day": "ALQ130 skipped for never drinkers -> set to 0",
    "chol_checked": "BPQ060 skipped when BPQ080 = 1 (structural); feature dropped by default",
}


# ----------------------------------------------------------------- metrics
def _logit(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def _newton_logistic(y, X, offset=None, n_iter=50):
    """Unpenalised logistic regression by Newton-Raphson. X includes the intercept column."""
    off = np.zeros(len(y)) if offset is None else offset
    beta = np.zeros(X.shape[1])
    for _ in range(n_iter):
        eta = X @ beta + off
        mu = 1 / (1 + np.exp(-eta))
        w = mu * (1 - mu)
        grad = X.T @ (y - mu)
        hess = X.T @ (X * w[:, None])
        step = np.linalg.solve(hess + 1e-10 * np.eye(len(beta)), grad)
        beta += step
        if np.max(np.abs(step)) < 1e-10:
            break
    return beta


def calibration_intercept_slope(y, p):
    lp = _logit(p)
    one = np.ones((len(y), 1))
    intercept = _newton_logistic(y, one, offset=lp)[0]                  # slope fixed at 1
    slope = _newton_logistic(y, np.column_stack([one, lp]))[1]
    return float(intercept), float(slope)


def point_metrics(y, p, thr=THRESHOLD):
    y = np.asarray(y).astype(int)
    pred = (p >= thr).astype(int)
    tp = int(((pred == 1) & (y == 1)).sum())
    tn = int(((pred == 0) & (y == 0)).sum())
    fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())
    sens = tp / (tp + fn) if tp + fn else np.nan
    spec = tn / (tn + fp) if tn + fp else np.nan
    ci_, cs = calibration_intercept_slope(y, p)
    return {"auroc": roc_auc_score(y, p), "auprc": average_precision_score(y, p),
            "accuracy": (tp + tn) / len(y), "balanced_accuracy": (sens + spec) / 2,
            "sensitivity": sens, "specificity": spec,
            "ppv": tp / (tp + fp) if tp + fp else np.nan, "npv": tn / (tn + fn) if tn + fn else np.nan,
            "prevalence": y.mean(), "predicted_positive_rate": pred.mean(),
            "brier": float(np.mean((p - y) ** 2)), "cal_intercept": ci_, "cal_slope": cs,
            "tp": tp, "fp": fp, "tn": tn, "fn": fn}


def bootstrap_metrics(y, p, B, rng):
    point = point_metrics(y, p)
    keys = [k for k in point if k not in ("tp", "fp", "tn", "fn")]
    draws = {k: [] for k in keys}
    n = len(y)
    for _ in range(B):
        i = rng.integers(0, n, n)
        if y[i].min() == y[i].max():
            continue
        m = point_metrics(y[i], p[i])
        for k in keys:
            draws[k].append(m[k])
    rows = []
    for k in keys:
        a = np.asarray(draws[k], float)
        rows.append({"metric": k, "estimate": point[k], "ci_low": np.nanpercentile(a, 2.5),
                     "ci_high": np.nanpercentile(a, 97.5), "B_used": int(np.isfinite(a).sum())})
    for k in ("tp", "fp", "tn", "fn"):
        rows.append({"metric": k, "estimate": point[k], "ci_low": np.nan, "ci_high": np.nan, "B_used": 0})
    return rows


def calibration_table(y, p, n_bins=10):
    q = pd.qcut(p, n_bins, labels=False, duplicates="drop")
    df = pd.DataFrame({"bin": q, "y": y, "p": p})
    return df.groupby("bin").agg(n=("y", "size"), mean_predicted=("p", "mean"),
                                 observed_rate=("y", "mean")).reset_index()


# ----------------------------------------------------------------- data
def load_period(data_dir, period):
    frames = []
    for suf in CYCLE_SETS[period]:
        res = build_cycle(load_cycle(data_dir, suf), suf)
        if res is not None:
            frames.append(res[0])
    if not frames:
        sys.exit(f"[ERROR] no usable cycles for period '{period}' in {data_dir}")
    return pd.concat(frames, ignore_index=True)


def prepare(data):
    X_full, groups = build_features(data)
    X = X_full.drop(columns=[c for c in DROP_FEATURES if c in X_full.columns])
    X = X.drop(columns=[c for c in X.columns if X[c].notna().sum() == 0])
    y_clin = data["Y_clin140"].values.astype(int)
    idx = np.arange(len(X))
    tr, te = train_test_split(idx, test_size=0.3, random_state=SEED, stratify=y_clin)
    return X_full, X, groups, tr, te


def data_characteristics(data, X_full, X_used, tr, te, period):
    dic = pd.DataFrame([{"feature": f, "group": g, "nhanes_source": s, "type": t, "unit_or_coding": u,
                         "definition": d, "used_in_models": f in X_used.columns}
                        for f, (g, s, t, u, d) in DICTIONARY.items() if f in X_full.columns])
    dist, miss = [], []
    for f in dic["feature"]:
        v = X_full[f]
        t = DICTIONARY[f][2]
        row = {"period": period, "feature": f, "n_nonmissing": int(v.notna().sum())}
        if t == "continuous" or t == "ordinal":
            row.update({"summary": "median [IQR]", "value": v.median(), "q1": v.quantile(.25),
                        "q3": v.quantile(.75), "min": v.min(), "max": v.max()})
        else:
            row.update({"summary": "% = 1", "value": 100 * v.mean(), "q1": np.nan, "q3": np.nan,
                        "min": v.min(), "max": v.max()})
        dist.append(row)
        miss.append({"period": period, "feature": f,
                     "missing_pct_all": 100 * v.isna().mean(),
                     "missing_pct_train": 100 * v.iloc[tr].isna().mean(),
                     "missing_pct_test": 100 * v.iloc[te].isna().mean(),
                     "skip_logic_resolved": SKIP_RESOLVED.get(f, ""),
                     "handling_cf_audit_models": "median of training split" if f in X_used.columns else "not used",
                     "handling_model_level_E1": "XGBoost native" if f in X_used.columns else "not used"})
    bal = []
    for lab in ("Y_self", "Y_clin140"):
        y = data[lab].values.astype(int)
        for split, ii in (("all", np.arange(len(y))), ("train", tr), ("test", te)):
            bal.append({"period": period, "label": lab, "split": split, "n": len(ii),
                        "n_positive": int(y[ii].sum()), "prevalence_pct": 100 * y[ii].mean()})
    return dic, pd.DataFrame(dist), pd.DataFrame(miss), pd.DataFrame(bal)


# ----------------------------------------------------------------- main
def fit_models(data, X, tr, te):
    """Returns {(family, model): test predictions}."""
    preds = {}
    med = X.iloc[tr].median()
    Xi = X.fillna(med)
    for mname, lab in LABELS.items():
        y = data[lab].values.astype(int)
        m = XGBClassifier(random_state=SEED, **PARAMS).fit(Xi.iloc[tr], y[tr])
        preds[("cf_audit", mname)] = m.predict_proba(Xi.iloc[te])[:, 1]
        m2 = XGBClassifier(random_state=SEED, **PARAMS).fit(X.iloc[tr], y[tr])
        preds[("model_level", mname)] = m2.predict_proba(X.iloc[te])[:, 1]
    return preds


def reference_check(preds, data, te, ref_dir, tol_exact, tol_cons):
    man_path = os.path.join(ref_dir, "cf_primary", "seed42", "run_manifest.json")
    p1_path = os.path.join(ref_dir, "model_level", "baseline", "P1_auc.csv")
    for pth in (man_path, p1_path):
        if not os.path.exists(pth):
            sys.exit(f"[ERROR] reference file not found: {pth}")
    man = json.load(open(man_path))
    p1 = pd.read_csv(p1_path, index_col=0)
    rows, failed = [], []
    for mname, lab in LABELS.items():
        y = data[lab].values[te].astype(int)
        key = mname.replace("f_", "")
        a = roc_auc_score(y, preds[("cf_audit", mname)])
        ref = float(man["auc_test"][key])
        ok = abs(a - ref) <= tol_exact
        rows.append({"family": "cf_audit", "model": mname, "auroc_refit": a, "reference": ref,
                     "reference_source": man_path + " auc_test", "abs_diff": abs(a - ref),
                     "tolerance": tol_exact, "type": "exact refit", "pass": ok})
        if not ok:
            failed.append(mname)
        b = roc_auc_score(y, preds[("model_level", mname)])
        refb = float(p1.loc[mname, "auc_mean"])
        rows.append({"family": "model_level", "model": mname, "auroc_refit": b, "reference": refb,
                     "reference_source": p1_path + " auc_mean (bootstrap mean)", "abs_diff": abs(b - refb),
                     "tolerance": tol_cons, "type": "consistency only", "pass": abs(b - refb) <= tol_cons})
    n_ref = int(man.get("n_test", -1))
    rows.append({"family": "cf_audit", "model": "n_test", "auroc_refit": len(te), "reference": n_ref,
                 "reference_source": man_path + " n_test", "abs_diff": abs(len(te) - n_ref),
                 "tolerance": 0, "type": "exact", "pass": len(te) == n_ref})
    if len(te) != n_ref:
        failed.append("n_test")
    return pd.DataFrame(rows), failed


def plot_calibration(cal_tables, path, period):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 9, "pdf.fonttype": 42})
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 3.4), sharey=True)
    for ax, mname in zip(axes, LABELS):
        t = cal_tables[mname]
        ax.plot([0, 1], [0, 1], ls="--", lw=0.8, color="0.5")
        ax.plot(t["mean_predicted"], t["observed_rate"], marker="o", ms=3.5, lw=1.2, color="0.15")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_xlabel("Mean predicted probability (decile)")
        ax.set_title({"f_self": "Self-report model", "f_clin": "Examination-informed model"}[mname],
                     fontsize=9)
    axes[0].set_ylabel("Observed proportion")
    fig.tight_layout()
    fig.savefig(path)          # vector PDF; no figure title inside the image (caption goes in the text)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--period", choices=["discovery", "confirmation"], required=True)
    ap.add_argument("--ref-dir", required=True, help="results/<period> folder of the frozen run")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--boot", type=int, default=1000)
    ap.add_argument("--tol-exact", type=float, default=0.001)
    ap.add_argument("--tol-consistency", type=float, default=0.005)
    args = ap.parse_args()
    if os.path.abspath(args.out_dir).startswith(os.path.abspath(args.ref_dir)):
        sys.exit("[ERROR] --out-dir must not be inside --ref-dir (original results are read-only)")
    os.makedirs(args.out_dir, exist_ok=True)

    data = load_period(args.data_dir, args.period)
    X_full, X, groups, tr, te = prepare(data)
    print(f"[{args.period}] N={len(X)} train={len(tr)} test={len(te)} features={X.shape[1]}")

    preds = fit_models(data, X, tr, te)
    chk, failed = reference_check(preds, data, te, args.ref_dir, args.tol_exact, args.tol_consistency)
    chk.to_csv(f"{args.out_dir}/reference_check.csv", index=False)
    print(chk[["family", "model", "auroc_refit", "reference", "abs_diff", "type", "pass"]].to_string(index=False))
    if failed:
        sys.exit(f"[ERROR] refit does not reproduce the frozen CF-audit models: {failed}. "
                 "Check data files, package versions (xgboost/scikit-learn), seed and split. Nothing reported.")
    cons_fail = chk[(chk["type"] == "consistency only") & (~chk["pass"])]
    if len(cons_fail):
        print("[WARN] model-level single fit differs from the bootstrap-mean AUC by more than "
              f"{args.tol_consistency}; reported anyway (different estimand: single fit vs bootstrap mean).")

    rng = np.random.default_rng(SEED)
    rows, cal_rows, cal_tables = [], [], {}
    for (fam, mname), p in preds.items():
        y = data[LABELS[mname]].values[te].astype(int)
        for r in bootstrap_metrics(y, p, args.boot, rng):
            rows.append({"period": args.period, "family": fam, "model": mname, "label": LABELS[mname],
                         "threshold": THRESHOLD, **r})
        t = calibration_table(y, p)
        t.insert(0, "model", mname)
        t.insert(0, "family", fam)
        cal_rows.append(t)
        if fam == "cf_audit":
            cal_tables[mname] = t
    perf = pd.DataFrame(rows)
    perf.to_csv(f"{args.out_dir}/PERF_metrics.csv", index=False)
    pd.concat(cal_rows).to_csv(f"{args.out_dir}/PERF_calibration_deciles.csv", index=False)
    plot_calibration(cal_tables, f"{args.out_dir}/fig_calibration_{args.period}.pdf", args.period)

    dic, dist, miss, bal = data_characteristics(data, X_full, X, tr, te, args.period)
    dic.to_csv(f"{args.out_dir}/DATA_dictionary.csv", index=False)
    dist.round(3).to_csv(f"{args.out_dir}/DATA_distribution.csv", index=False)
    miss.round(2).to_csv(f"{args.out_dir}/DATA_missingness.csv", index=False)
    bal.round(2).to_csv(f"{args.out_dir}/DATA_class_balance.csv", index=False)

    write_manifest(args.out_dir, args, {"analysis": "POST HOC reporting (not an endpoint)",
                                        "n": int(len(X)), "n_train": int(len(tr)), "n_test": int(len(te)),
                                        "threshold": THRESHOLD, "ci": "test-set bootstrap, model fixed",
                                        "weights": "unweighted"})
    show = perf[perf["family"] == "cf_audit"].pivot(index="metric", columns="model", values="estimate")
    print("\n== cf_audit models, test split, threshold 0.5\n", show.round(3).to_string())
    print(f"\nDone. Outputs in {args.out_dir}")


if __name__ == "__main__":
    main()
