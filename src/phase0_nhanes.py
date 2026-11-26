"""
Phase 0 - Data audit: self-reported vs examination-informed hypertension in NHANES 2011-2018.

Usage:
    python phase0_nhanes.py --data-dir /path/to/xpt_files --out-dir ./phase0_out

Expected files in --data-dir (suffix G=2011-12, H=2013-14, I=2015-16, J=2017-18):
    DEMO_x.XPT  BPX_x.XPT  BPQ_x.XPT  HIQ_x.XPT  HUQ_x.XPT  MCQ_x.XPT  BMX_x.XPT

Rules followed:
  * Adults >= 20 y, not pregnant, with >=1 valid SBP and DBP reading and a valid BPQ020 answer.
  * Mean BP: mean of valid readings 2-4 if >=2 valid readings exist, otherwise the single valid reading
    (DBP <= 0 treated as missing; SBP and DBP aggregated separately).
  * Y_self      = BPQ020 == 1 ("ever told by doctor you had high blood pressure")
  * Y_clin140   = SBP >= 140 or DBP >= 90 or currently taking BP medication (BPQ050A == 1)
  * Y_clin130   = SBP >= 130 or DBP >= 80 or BPQ050A == 1   (sensitivity)
  * Signal analyses (T3, T6) use DISCOVERY cycles only (G, H). Cycles I, J are used only for
    counts (T1, T2, T4, T5) so they stay untouched for later confirmation.
  * Percentages are survey-weighted with WTMEC2YR / n_cycles (point estimates only; design-based
    SEs via strata/PSU are left for the next phase).
"""
import argparse
import os
import numpy as np
import pandas as pd

CYCLES = {"G": "2011-2012", "H": "2013-2014", "I": "2015-2016", "J": "2017-2018"}
DISCOVERY = ["G", "H"]
CONFIRMATION = ["I", "J"]
CYCLE_SETS = {"discovery": DISCOVERY, "confirmation": CONFIRMATION, "G": ["G"], "H": ["H"], "I": ["I"], "J": ["J"]}
FILES = ["DEMO", "BPX", "BPQ", "HIQ", "HUQ", "MCQ", "BMX"]
# optional tables used from Phase 0.5 on (merged if present)
EXTRA_FILES = ["SMQ", "ALQ", "PAQ", "DIQ", "TCHOL", "GHB"]

# Variables to check for cross-cycle availability (T5)
CHECK_VARS = {
    "BPQ": ["BPQ020", "BPQ030", "BPD035", "BPQ040A", "BPQ050A"],
    "HIQ": ["HIQ011"],
    "HUQ": ["HUQ030", "HUQ050", "HUQ051"],
    "MCQ": ["MCQ366A", "MCQ366B", "MCQ366C", "MCQ366D",
            "MCQ371A", "MCQ371B", "MCQ371C", "MCQ371D"],
    "BMX": ["BMXBMI", "BMXWAIST"],
    "DEMO": ["RIDAGEYR", "RIAGENDR", "RIDRETH3", "DMDEDUC2", "INDFMPIR",
             "RIDEXPRG", "WTMEC2YR", "SDMVPSU", "SDMVSTRA"],
}


def read_xpt(data_dir, name, suffix):
    for fn in (f"{name}_{suffix}.XPT", f"{name}_{suffix}.xpt"):
        p = os.path.join(data_dir, fn)
        if os.path.exists(p):
            df = pd.read_sas(p, format="xport")
            # SAS XPORT stores 0 as ~5.4e-79 when read by pandas; snap those to exact 0
            num = df.select_dtypes("number").columns
            df[num] = df[num].mask(df[num].abs() < 1e-10, 0.0)
            return df
    return None


def load_cycle(data_dir, suffix):
    tables = {n: read_xpt(data_dir, n, suffix) for n in FILES + EXTRA_FILES}
    return tables


def mean_bp(df, prefix):
    """Mean BP per rule (DBP <= 0 treated as missing):
    >= 2 valid readings -> mean of the valid readings among 2-4 (reading 1 dropped);
    exactly 1 valid reading -> that reading, whichever it is (fixed 2026-11: previously a single
    valid LATER reading was lost because reading 1 was taken unconditionally)."""
    cols = [f"{prefix}{i}" for i in range(1, 5) if f"{prefix}{i}" in df.columns]
    vals = df[cols].astype(float).copy()
    if prefix == "BPXDI":
        vals = vals.mask(vals <= 0)
    n_valid = vals.notna().sum(axis=1)
    later = vals[cols[1:]].mean(axis=1) if len(cols) > 1 else pd.Series(np.nan, index=df.index)
    single = vals.mean(axis=1)              # with exactly one valid reading = that reading
    return pd.Series(np.where(n_valid >= 2, later, single), index=df.index)


def bp_rule_check(df):
    """Count participants affected by the single-valid-later-reading fix."""
    out = {}
    for prefix in ("BPXSY", "BPXDI"):
        cols = [f"{prefix}{i}" for i in range(1, 5) if f"{prefix}{i}" in df.columns]
        vals = df[cols].astype(float)
        if prefix == "BPXDI":
            vals = vals.mask(vals <= 0)
        n_valid = vals.notna().sum(axis=1)
        out[f"{prefix}_n_valid0"] = int((n_valid == 0).sum())
        out[f"{prefix}_n_valid1"] = int((n_valid == 1).sum())
        out[f"{prefix}_single_valid_is_later"] = int(((n_valid == 1) & vals[cols[0]].isna()).sum())
        if prefix == "BPXDI":
            out["BPXDI_zero_readings"] = int((df[cols].astype(float) <= 0).sum().sum())
    return out


def build_cycle(tables, suffix):
    demo = tables["DEMO"]
    if demo is None or tables["BPX"] is None or tables["BPQ"] is None:
        return None
    df = demo[["SEQN"] + [c for c in CHECK_VARS["DEMO"] if c in demo.columns]].copy()
    for name in [n for n in FILES + EXTRA_FILES if n != "DEMO"]:
        t = tables[name]
        if t is not None:
            df = df.merge(t, on="SEQN", how="left", suffixes=("", f"_{name}"))
    df["cycle"] = suffix
    n_total = len(df)
    adult = df[(df["RIDAGEYR"] >= 20) & (df.get("RIDEXPRG", pd.Series(0, index=df.index)) != 1)]
    bp_check = {"cycle": CYCLES.get(suffix, suffix), "n_adult_nonpregnant": len(adult), **bp_rule_check(adult)}

    df["SBP"] = mean_bp(df, "BPXSY")
    df["DBP"] = mean_bp(df, "BPXDI")

    steps = [("all participants", n_total)]
    df = df[df["RIDAGEYR"] >= 20]
    steps.append(("age >= 20", len(df)))
    if "RIDEXPRG" in df.columns:
        df = df[df["RIDEXPRG"] != 1]
    steps.append(("not pregnant", len(df)))
    df = df[df["SBP"].notna() & df["DBP"].notna()]
    steps.append(("valid SBP & DBP", len(df)))
    df = df[df["BPQ020"].isin([1, 2])]
    steps.append(("valid BPQ020", len(df)))

    # Medication status, tri-state: 1 yes / 0 no (incl. structural skips) / NaN unknown.
    # Skip logic: BPQ040A asked only if BPQ020 == 1; BPQ050A asked only if BPQ040A == 1.
    ms = pd.Series(np.nan, index=df.index)
    ms[df["BPQ020"] == 2] = 0.0
    if "BPQ040A" in df.columns:
        ms[(df["BPQ020"] == 1) & (df["BPQ040A"] == 2)] = 0.0
    if "BPQ050A" in df.columns:
        ms[df["BPQ050A"] == 1] = 1.0
        ms[df["BPQ050A"] == 2] = 0.0
    df["med_status"] = ms
    df = df[df["med_status"].notna()]
    steps.append(("known BP-medication status", len(df)))

    df["Y_self"] = (df["BPQ020"] == 1).astype(int)
    # Y_self2 (told >= 2 times), tri-state: BPQ030 asked only if BPQ020 == 1; refused/don't know -> NaN
    s2 = pd.Series(np.nan, index=df.index)
    s2[df["BPQ020"] == 2] = 0.0
    if "BPQ030" in df.columns:
        s2[(df["BPQ020"] == 1) & (df["BPQ030"] == 1)] = 1.0
        s2[(df["BPQ020"] == 1) & (df["BPQ030"] == 2)] = 0.0
    df["Y_self2"] = s2
    df["on_med"] = (df["med_status"] == 1).astype(int)
    for s_thr, d_thr, tag in [(140, 90, "140"), (130, 80, "130")]:
        bp_pos = (df["SBP"] >= s_thr) | (df["DBP"] >= d_thr)
        df[f"Y_bp{tag}"] = bp_pos.astype(int)
        df[f"Y_clin{tag}"] = (bp_pos | (df["on_med"] == 1)).astype(int)
        # signed distance to threshold using BOTH SBP and DBP (positive = above threshold)
        df[f"dist{tag}"] = np.maximum(df["SBP"] - s_thr, df["DBP"] - d_thr)
        df[f"G{tag}"] = "G" + df["Y_self"].astype(str) + df[f"Y_clin{tag}"].astype(str)

    df["w"] = df["WTMEC2YR"]
    df.attrs["bp_check"] = bp_check
    return df, steps


def wprop(x, w):
    m = x.notna() & w.notna()
    if m.sum() == 0:
        return np.nan
    return float(np.average(x[m], weights=w[m]))


def dist_band(row, tag):
    if row["on_med"] == 1:
        return "on BP medication"
    d = row[f"dist{tag}"]
    if abs(d) <= 5:
        return "within ±5 mmHg"
    if abs(d) <= 10:
        return "5-10 mmHg"
    return ">10 mmHg"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--out-dir", default="phase0_out")
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    frames, attrition, avail, bpchk = [], [], [], []
    for suf, years in CYCLES.items():
        tables = load_cycle(args.data_dir, suf)
        for fname, vars_ in CHECK_VARS.items():
            t = tables.get(fname)
            for v in vars_:
                avail.append({"cycle": years, "file": fname, "variable": v,
                              "present": t is not None and v in t.columns,
                              "non_missing": int(t[v].notna().sum()) if t is not None and v in t.columns else 0})
        res = build_cycle(tables, suf)
        if res is None:
            print(f"[warn] cycle {years}: missing DEMO/BPX/BPQ, skipped")
            continue
        df, steps = res
        for s, n in steps:
            attrition.append({"cycle": years, "step": s, "n": n})
        bpchk.append(df.attrs["bp_check"])
        frames.append(df)

    if not frames:
        raise SystemExit("No usable cycles found. Check --data-dir and file names.")
    data = pd.concat(frames, ignore_index=True)
    n_cyc = data["cycle"].nunique()
    data["w"] = data["w"] / n_cyc

    # T1 attrition / T5 availability
    pd.DataFrame(attrition).to_csv(f"{args.out_dir}/T1_attrition.csv", index=False)
    pd.DataFrame(bpchk).to_csv(f"{args.out_dir}/T1b_bp_rule_check.csv", index=False)
    print("BP rule check:\n", pd.DataFrame(bpchk).to_string(index=False))
    pd.DataFrame(avail).pivot_table(index=["file", "variable"], columns="cycle",
                                    values="non_missing").to_csv(f"{args.out_dir}/T5_variable_availability.csv")

    # T2 / T4 : agreement matrix and groups, by cycle (counts) - all cycles
    rows = []
    for tag in ["140", "130"]:
        for cyc, g in data.groupby("cycle"):
            ct = g.groupby(f"G{tag}").size()
            rec = {"threshold": tag, "cycle": CYCLES[cyc], "n": len(g)}
            for k in ["G00", "G01", "G10", "G11"]:
                rec[k] = int(ct.get(k, 0))
            rec["disagree_pct_unweighted"] = round(100 * (rec["G01"] + rec["G10"]) / len(g), 2)
            rec["disagree_pct_weighted"] = round(100 * wprop((g["Y_self"] != g[f"Y_clin{tag}"]).astype(float), g["w"]), 2)
            # G10 broken down: diagnosed, no medication, normal BP (residual diagnosis-dependence of Y_clin)
            rec["G10_no_med"] = int(((g[f"G{tag}"] == "G10") & (g["on_med"] == 0)).sum())
            rec["G11_via_med_only"] = int(((g[f"G{tag}"] == "G11") & (g[f"Y_bp{tag}"] == 0)).sum())
            rows.append(rec)
    pd.DataFrame(rows).to_csv(f"{args.out_dir}/T2_T4_agreement_groups.csv", index=False)

    # ---- Signal analyses: discovery cycles only ----
    disc = data[data["cycle"].isin(DISCOVERY)].copy()

    # T3 : disagreement by distance-to-threshold band
    t3 = []
    for tag in ["140", "130"]:
        disc["band"] = disc.apply(dist_band, axis=1, tag=tag)
        disc["disagree"] = (disc["Y_self"] != disc[f"Y_clin{tag}"]).astype(float)
        for band, g in disc.groupby("band"):
            t3.append({"threshold": tag, "band": band, "n": len(g),
                       "n_disagree": int(g["disagree"].sum()),
                       "disagree_pct_weighted": round(100 * wprop(g["disagree"], g["w"]), 2)})
        tot = disc["disagree"].sum()
        for r in t3:
            if r["threshold"] == tag:
                r["share_of_all_disagreement_pct"] = round(100 * r["n_disagree"] / tot, 2) if tot else np.nan
    pd.DataFrame(t3).to_csv(f"{args.out_dir}/T3_disagreement_by_threshold_distance.csv", index=False)

    # T6 : healthcare-access profile by group, stratified by age band (core contrast: G01 vs G11)
    disc["insured"] = disc["HIQ011"].map({1: 1.0, 2: 0.0}) if "HIQ011" in disc else np.nan
    disc["routine_place"] = disc["HUQ030"].map({1: 1.0, 3: 1.0, 2: 0.0}) if "HUQ030" in disc else np.nan
    # HUQ050 (2011-12) was renamed HUQ051 from 2013-14; coalesce both (77/99 = refused/don't know)
    vcols = [c for c in ("HUQ051", "HUQ050") if c in disc.columns]
    if vcols:
        v = disc[vcols].bfill(axis=1).iloc[:, 0]
        v = v.where(v < 77)
        disc["any_visit_past_year"] = (v > 0).astype(float).where(v.notna())
    else:
        disc["any_visit_past_year"] = np.nan
    disc["age_band"] = pd.cut(disc["RIDAGEYR"], [19, 39, 59, 120], labels=["20-39", "40-59", "60+"])
    t6 = []
    for tag in ["140", "130"]:
        for (ab, grp), g in disc.groupby(["age_band", f"G{tag}"], observed=True):
            t6.append({"threshold": tag, "age_band": ab, "group": grp, "n": len(g),
                       "insured_pct": round(100 * wprop(g["insured"], g["w"]), 1),
                       "routine_place_pct": round(100 * wprop(g["routine_place"], g["w"]), 1),
                       "any_visit_pct": round(100 * wprop(g["any_visit_past_year"], g["w"]), 1)})
    pd.DataFrame(t6).to_csv(f"{args.out_dir}/T6_access_by_group_age.csv", index=False)

    data.to_parquet(f"{args.out_dir}/analytic_cohort.parquet", index=False)
    print("Done. Tables written to", args.out_dir)
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
