"""
Design-based standard errors for the descriptive tables (survey-weighted proportions).

Taylor linearisation for a ratio estimator p = sum(w*y*d) / sum(w*d) over a domain d, using the
NHANES design: strata SDMVSTRA (made unique per cycle) and PSU SDMVPSU, with-replacement PSU
approximation. Domain estimation is done on the FULL MEC-examined sample (WTMEC2YR > 0) of the chosen
cycles: rows outside the analytic sample stay in the design with zero contribution, as recommended for
NHANES subgroup analysis. S0 reports strata / PSU counts in the full MEC sample vs the analytic sample
and any singleton strata (which contribute no variance). Weights = WTMEC2YR / number of pooled cycles.

Outputs (for the chosen cycle set):
  S1  label disagreement (weighted %) by threshold, with SE and 95% CI
  S2  healthcare-access profile by group x age band (T6 with SE)
  S3  healthcare-access profile by group, all ages (T7 access columns with SE)
  S0  design check: strata / PSU in the full MEC sample vs analytic sample

    python src/design_se.py --data-dir data/raw --out-dir outputs/design_se --cycles discovery
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd
from scipy.stats import t as tdist

sys.path.insert(0, os.path.dirname(__file__))
from phase0_nhanes import CYCLE_SETS, load_cycle, build_cycle  # noqa: E402
from phase0b_supplement import access_cols  # noqa: E402
from utils import write_manifest  # noqa: E402


def svy_prop(df, var, domain):
    """Weighted proportion of `var` (0/1, NaN = excluded) within boolean `domain`; returns
    (p, se, n_unweighted, df_design). Linearised SE with strata/PSU (with replacement)."""
    y = df[var]
    d = domain & y.notna()
    w = df["w"].where(d, 0.0)
    W = w.sum()
    if W <= 0 or d.sum() == 0:
        return np.nan, np.nan, 0, np.nan
    yy = y.fillna(0.0)
    p = float((w * yy).sum() / W)
    z = w * (yy - p) / W                                  # linearised values, 0 outside domain
    tab = pd.DataFrame({"h": df["stratum"], "psu": df["psu"], "z": z})
    psu_tot = tab.groupby(["h", "psu"])["z"].sum().reset_index()
    var_p = 0.0
    for _, g in psu_tot.groupby("h"):
        n_h = len(g)
        if n_h < 2:
            continue
        var_p += n_h / (n_h - 1) * ((g["z"] - g["z"].mean()) ** 2).sum()
    n_psu = len(psu_tot)
    n_str = psu_tot["h"].nunique()
    return p, float(np.sqrt(var_p)), int(d.sum()), int(n_psu - n_str)


def row(df, var, domain, **keys):
    p, se, n, dfd = svy_prop(df, var, domain)
    tq = tdist.ppf(0.975, dfd) if dfd and dfd > 0 else 1.96
    return {**keys, "n": n, "pct": round(100 * p, 1) if n else np.nan,
            "se_pct": round(100 * se, 2) if n else np.nan,
            "ci_low": round(100 * max(p - tq * se, 0), 1) if n else np.nan,
            "ci_high": round(100 * min(p + tq * se, 1), 1) if n else np.nan, "design_df": dfd}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--out-dir", default="outputs/design_se")
    ap.add_argument("--cycles", choices=list(CYCLE_SETS), default="discovery")
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    suf = CYCLE_SETS[args.cycles]
    full_frames, ana_frames = [], []
    for c in suf:
        tables = load_cycle(args.data_dir, c)
        demo = tables["DEMO"][["SEQN", "SDMVSTRA", "SDMVPSU", "WTMEC2YR"]].copy()
        demo = demo[demo["WTMEC2YR"] > 0]
        demo["cycle"] = c
        full_frames.append(demo)
        ana_frames.append(build_cycle(tables, c)[0])
    full = pd.concat(full_frames, ignore_index=True)
    ana = pd.concat(ana_frames, ignore_index=True)
    ana = ana.drop(columns=[k for k in ("SDMVSTRA", "SDMVPSU", "WTMEC2YR", "w") if k in ana.columns])
    data = full.merge(ana, on=["SEQN", "cycle"], how="left", indicator=True)
    data["analytic"] = data["_merge"] == "both"
    data = data.drop(columns="_merge")
    data["w"] = data["WTMEC2YR"] / len(suf)
    data["stratum"] = data["cycle"].astype(str) + "_" + data["SDMVSTRA"].astype(int).astype(str)
    data["psu"] = data["SDMVPSU"].astype(int)
    s0 = []
    for name, sub in [("full_MEC", data), ("analytic", data[data["analytic"]])]:
        sp = sub.groupby("stratum")["psu"].nunique()
        s0.append({"sample": name, "n": len(sub), "n_strata": int(sp.size), "n_psu": int(sp.sum()),
                   "singleton_strata": int((sp < 2).sum())})
    pd.DataFrame(s0).to_csv(f"{args.out_dir}/S0_design_check.csv", index=False)
    print("== S0 design check\n", pd.DataFrame(s0).to_string(index=False))
    data = access_cols(data)
    data["age_band"] = pd.cut(data["RIDAGEYR"], [19, 39, 59, 120], labels=["20-39", "40-59", "60+"])
    allrows = data["analytic"]

    s1 = []
    for tag in ["140", "130"]:
        data[f"disagree{tag}"] = (data["Y_self"] != data[f"Y_clin{tag}"]).astype(float).where(data["analytic"])
        s1.append(row(data, f"disagree{tag}", allrows, threshold=tag))
    pd.DataFrame(s1).to_csv(f"{args.out_dir}/S1_disagreement_se.csv", index=False)

    s2, s3 = [], []
    for var in ["insured", "routine_place", "any_visit"]:          # whole analytic sample (Table 1 "Overall")
        s3.append(row(data, var, data["analytic"], threshold="all", group="Overall", variable=var))
    for tag in ["140", "130"]:
        for grp in ["G00", "G01", "G10", "G11"]:
            for var in ["insured", "routine_place", "any_visit"]:
                s3.append(row(data, var, data["analytic"] & (data[f"G{tag}"] == grp), threshold=tag, group=grp, variable=var))
                for ab in ["20-39", "40-59", "60+"]:
                    s2.append(row(data, var, data["analytic"] & (data[f"G{tag}"] == grp) & (data["age_band"] == ab),
                                  threshold=tag, age_band=ab, group=grp, variable=var))
    pd.DataFrame(s2).to_csv(f"{args.out_dir}/S2_access_by_group_age_se.csv", index=False)
    pd.DataFrame(s3).to_csv(f"{args.out_dir}/S3_access_by_group_se.csv", index=False)
    write_manifest(args.out_dir, args, {"n_full_mec": int(len(data)), "n_analytic": int(data["analytic"].sum())})
    print(pd.DataFrame(s1).to_string(index=False))
    print(pd.DataFrame(s3).query("threshold == '140'").to_string(index=False))


if __name__ == "__main__":
    main()
