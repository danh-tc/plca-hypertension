"""
Phase 0b - supplements to Phase 0 (discovery cycles 2011-2014 only for signal tables).

  T3b  disagreement by group (G01 / G10) and SIGNED distance to the 140/90 threshold
  T7   G10 vs G11 vs G01 profile: told >=2 times (BPQ030), years since diagnosis (age - BPD035), access
  T8   G01 share among measured-positive, unmedicated adults, by cycle (cycle-effect check, counts)
  T5b  availability of lifestyle-advice and lifestyle variables across cycles
  T9   label-coding check: refused / don't know / missing-when-expected for BPQ020-050A, BPQ060, BPQ080
  T9b  BPQ080 x BPQ060 cross-tab (codebook: BPQ080 = 1 skips BPQ060)

Usage:
    python src/phase0b_supplement.py --data-dir data/raw --out-dir outputs/phase0b
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from phase0_nhanes import CYCLES, DISCOVERY, load_cycle, build_cycle, wprop  # noqa: E402

AVAIL_VARS = {
    "MCQ": [f"MCQ365{c}" for c in "ABCD"] + [f"MCQ370{c}" for c in "ABCD"]
           + [f"MCQ366{c}" for c in "ABCD"] + [f"MCQ371{c}" for c in "ABCD"],
    "BPQ": ["BPQ060", "BPQ080"],
    "HUQ": ["HUQ010"],
    "SMQ": ["SMQ020", "SMQ040"],
    "ALQ": ["ALQ101", "ALQ111", "ALQ130"],
    "PAQ": ["PAQ650", "PAQ665"],
    "DIQ": ["DIQ010"],
    "TCHOL": ["LBXTC"],
    "GHB": ["LBXGH"],
}

SIGNED_BANDS = [-np.inf, -10, -5, 0, 5, 10, np.inf]
SIGNED_LABELS = ["< -10", "-10..-5", "-5..0", "0..5", "5..10", "> 10"]


def access_cols(df):
    df = df.copy()
    df["insured"] = df["HIQ011"].map({1: 1.0, 2: 0.0}) if "HIQ011" in df else np.nan
    df["routine_place"] = df["HUQ030"].map({1: 1.0, 3: 1.0, 2: 0.0}) if "HUQ030" in df else np.nan
    vcols = [c for c in ("HUQ051", "HUQ050") if c in df.columns]
    v = df[vcols].bfill(axis=1).iloc[:, 0].where(lambda x: x < 77) if vcols else pd.Series(np.nan, index=df.index)
    df["any_visit"] = (v > 0).astype(float).where(v.notna())
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--out-dir", default="outputs/phase0b")
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    frames, avail = [], []
    for suf, years in CYCLES.items():
        tables = load_cycle(args.data_dir, suf)
        for fname, vars_ in AVAIL_VARS.items():
            t = tables.get(fname)
            for v in vars_:
                avail.append({"cycle": years, "file": fname, "variable": v,
                              "non_missing": int(t[v].notna().sum()) if t is not None and v in t.columns else 0})
        res = build_cycle(tables, suf)
        if res is not None:
            frames.append(res[0])
    data = pd.concat(frames, ignore_index=True)
    data["w"] = data["w"] / data["cycle"].nunique()

    # T9: label-coding check (adults >= 20, raw questionnaire codes) and BPQ060/BPQ080 skip pattern
    t9, t9x = [], []
    for suf, years in CYCLES.items():
        tb = load_cycle(args.data_dir, suf)
        if tb.get("BPQ") is None or tb.get("DEMO") is None:
            continue
        b = tb["BPQ"].merge(tb["DEMO"][["SEQN", "RIDAGEYR"]], on="SEQN")
        b = b[b["RIDAGEYR"] >= 20]
        for v, cond in [("BPQ020", b.index == b.index), ("BPQ030", b["BPQ020"] == 1),
                        ("BPQ040A", b["BPQ020"] == 1), ("BPQ050A", b.get("BPQ040A", pd.Series(np.nan, index=b.index)) == 1),
                        ("BPQ060", b.index == b.index), ("BPQ080", b.index == b.index)]:
            if v not in b:
                continue
            x = b.loc[cond, v]
            t9.append({"cycle": years, "variable": v, "n_expected": len(x),
                       "yes_1": int((x == 1).sum()), "no_2": int((x == 2).sum()),
                       "refused_7": int((x == 7).sum()), "dont_know_9": int((x == 9).sum()),
                       "missing_when_expected": int(x.isna().sum())})
        if {"BPQ060", "BPQ080"} <= set(b.columns):
            ct = pd.crosstab(b["BPQ080"].fillna(-1), b["BPQ060"].fillna(-1))
            ct.index.name, ct.columns.name = "BPQ080", "BPQ060"
            t9x.append(ct.assign(cycle=years).reset_index())
    pd.DataFrame(t9).to_csv(f"{args.out_dir}/T9_label_coding.csv", index=False)
    if t9x:
        pd.concat(t9x).to_csv(f"{args.out_dir}/T9b_BPQ080_x_BPQ060.csv", index=False)
    pd.DataFrame(avail).pivot_table(index=["file", "variable"], columns="cycle",
                                    values="non_missing").to_csv(f"{args.out_dir}/T5b_availability.csv")

    # T8: cycle check (counts only, all cycles)
    t8 = []
    for cyc, g in data.groupby("cycle"):
        pos_unmed = g[(g["Y_bp140"] == 1) & (g["on_med"] == 0)]
        t8.append({"cycle": CYCLES[cyc], "measured_pos_unmedicated": len(pos_unmed),
                   "G01": int((pos_unmed["Y_self"] == 0).sum()),
                   "G01_share_pct": round(100 * (pos_unmed["Y_self"] == 0).mean(), 1),
                   "mean_SBP_all": round(g["SBP"].mean(), 1), "mean_DBP_all": round(g["DBP"].mean(), 1)})
    pd.DataFrame(t8).to_csv(f"{args.out_dir}/T8_cycle_check.csv", index=False)

    disc = access_cols(data[data["cycle"].isin(DISCOVERY)])

    # T3b: signed distance, disagreeing groups only, unmedicated
    d = disc[(disc["on_med"] == 0) & disc["G140"].isin(["G01", "G10"])].copy()
    d["band"] = pd.cut(d["dist140"], SIGNED_BANDS, labels=SIGNED_LABELS, right=False)
    t3b = d.groupby(["G140", "band"], observed=False).size().rename("n").reset_index()
    t3b["share_of_all_disagreement_pct"] = (100 * t3b["n"] / len(d)).round(1)
    t3b.to_csv(f"{args.out_dir}/T3b_disagreement_by_group_signed_distance.csv", index=False)

    # T7: G10 profile
    disc["told_2plus"] = disc["BPQ030"].map({1: 1.0, 2: 0.0}) if "BPQ030" in disc else np.nan
    age_dx = disc["BPD035"].where(disc["BPD035"] < 777) if "BPD035" in disc else np.nan
    disc["years_since_dx"] = (disc["RIDAGEYR"] - age_dx).where(lambda x: x >= 0)
    t7 = []
    for grp in ["G00", "G01", "G10", "G11"]:
        g = disc[disc["G140"] == grp]
        ysd = g["years_since_dx"].dropna()
        t7.append({"group": grp, "n": len(g), "mean_age": round(g["RIDAGEYR"].mean(), 1),
                   "mean_SBP": round(g["SBP"].mean(), 1),
                   "told_2plus_pct": round(100 * wprop(g["told_2plus"], g["w"]), 1),
                   "years_since_dx_median": round(ysd.median(), 1) if len(ysd) else np.nan,
                   "years_since_dx_n": len(ysd),
                   "insured_pct": round(100 * wprop(g["insured"], g["w"]), 1),
                   "routine_place_pct": round(100 * wprop(g["routine_place"], g["w"]), 1),
                   "any_visit_pct": round(100 * wprop(g["any_visit"], g["w"]), 1)})
    pd.DataFrame(t7).to_csv(f"{args.out_dir}/T7_group_profiles.csv", index=False)

    print("Done ->", args.out_dir)
    for name in ["T3b_disagreement_by_group_signed_distance", "T7_group_profiles", "T8_cycle_check", "T9_label_coding"]:
        print(f"\n== {name}\n" + pd.read_csv(f"{args.out_dir}/{name}.csv").to_string(index=False))


if __name__ == "__main__":
    main()
