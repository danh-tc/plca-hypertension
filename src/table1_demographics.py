"""
Table 1 (descriptive only) - sample characteristics of the analytic cohort, by label-agreement group.

Descriptive table for the paper. It is not an endpoint and does not touch models or CFs.
It rebuilds the analytic cohort with the same phase0 rules (build_cycle), so N matches T1_attrition.

Usage:
    python src/table1_demographics.py --data-dir data/raw --cycles confirmation --out-dir results/table1
Output:
    T1c_demographics.csv   (rows = characteristics, columns = Overall, G00, G01, G10, G11 at the 140/90 threshold)
Percentages and means are survey-weighted with WTMEC2YR / n_cycles (point estimates); n is unweighted.
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from phase0_nhanes import CYCLE_SETS, load_cycle, build_cycle, wprop  # noqa: E402

RACE = {1: "Mexican American", 2: "Other Hispanic", 3: "Non-Hispanic White",
        4: "Non-Hispanic Black", 6: "Non-Hispanic Asian", 7: "Other / multiracial"}
EDU = {1: "< High school", 2: "< High school", 3: "High school / GED",
       4: "Some college / AA", 5: "College graduate +"}


def wmean(x, w):
    m = x.notna() & w.notna()
    return float(np.average(x[m], weights=w[m])) if m.any() else np.nan


def wsd(x, w):
    m = x.notna() & w.notna()
    if not m.any():
        return np.nan
    mu = np.average(x[m], weights=w[m])
    return float(np.sqrt(np.average((x[m] - mu) ** 2, weights=w[m])))


def describe(g):
    w = g["w"]
    out = {"n (unweighted)": f"{len(g):,}"}
    out["Age, years, mean (SD)"] = f"{wmean(g['RIDAGEYR'], w):.1f} ({wsd(g['RIDAGEYR'], w):.1f})"
    for lo, hi, lab in [(20, 39, "20-39"), (40, 59, "40-59"), (60, 200, ">= 60")]:
        out[f"Age {lab}, %"] = f"{100 * wprop(g['RIDAGEYR'].between(lo, hi).astype(float), w):.1f}"
    out["Female, %"] = f"{100 * wprop((g['RIAGENDR'] == 2).astype(float), w):.1f}"
    for code, lab in RACE.items():
        out[f"Race/ethnicity: {lab}, %"] = f"{100 * wprop((g['RIDRETH3'] == code).astype(float), w):.1f}"
    if "DMDEDUC2" in g:
        edu = g["DMDEDUC2"].map(EDU)
        for lab in dict.fromkeys(EDU.values()):
            out[f"Education: {lab}, %"] = f"{100 * wprop((edu == lab).astype(float).where(edu.notna()), w):.1f}"
    if "INDFMPIR" in g:
        out["Income-to-poverty ratio < 1.3, %"] = f"{100 * wprop((g['INDFMPIR'] < 1.3).astype(float).where(g['INDFMPIR'].notna()), w):.1f}"
    if "HIQ011" in g:
        out["Health insurance, %"] = f"{100 * wprop(g['HIQ011'].map({1: 1.0, 2: 0.0}), w):.1f}"
    if "BMXBMI" in g:
        out["BMI, kg/m2, mean (SD)"] = f"{wmean(g['BMXBMI'], w):.1f} ({wsd(g['BMXBMI'], w):.1f})"
    out["SBP, mmHg, mean (SD)"] = f"{wmean(g['SBP'], w):.1f} ({wsd(g['SBP'], w):.1f})"
    out["DBP, mmHg, mean (SD)"] = f"{wmean(g['DBP'], w):.1f} ({wsd(g['DBP'], w):.1f})"
    out["On BP medication, %"] = f"{100 * wprop(g['on_med'].astype(float), w):.1f}"
    out["Y_self = 1, %"] = f"{100 * wprop(g['Y_self'].astype(float), w):.1f}"
    out["Y_clin140 = 1, %"] = f"{100 * wprop(g['Y_clin140'].astype(float), w):.1f}"
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--cycles", default="confirmation", choices=sorted(CYCLE_SETS))
    ap.add_argument("--out-dir", default="results/table1")
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    frames = []
    for suf in CYCLE_SETS[args.cycles]:
        res = build_cycle(load_cycle(args.data_dir, suf), suf)
        if res is None:
            raise SystemExit(f"cycle {suf}: missing DEMO/BPX/BPQ in {args.data_dir}")
        frames.append(res[0])
    data = pd.concat(frames, ignore_index=True)
    data["w"] = data["w"] / data["cycle"].nunique()

    cols = {"Overall": describe(data)}
    for grp in ["G00", "G01", "G10", "G11"]:
        cols[grp] = describe(data[data["G140"] == grp])
    tab = pd.DataFrame(cols)
    tab.index.name = "characteristic"
    path = os.path.join(args.out_dir, f"T1c_demographics_{args.cycles}.csv")
    tab.to_csv(path)
    print(tab.to_string())
    print("Written:", path)


if __name__ == "__main__":
    main()
