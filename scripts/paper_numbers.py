"""Collect every number reported in the manuscript from one results folder.

Usage:  python scripts/paper_numbers.py results/confirmation
Prints label -> value so text numbers can be checked against the files.
"""
import os
import sys

import pandas as pd


def numbers(root):
    out = {}
    rd = lambda f: pd.read_csv(os.path.join(root, f))

    # ---------------- model level (E1 and sensitivity)
    for cfg in ["baseline", "clin130", "self2", "bp140_unmedicated", "exclude_G01_train", "randdrop_G01_train",
                "logreg", "chol_reconstructed"]:
        e = rd(f"model_level/{cfg}/E1_endpoint.csv").iloc[0]
        out[f"E1.{cfg}.abs"] = e["abs_self_minus_clin_mean"]
        out[f"E1.{cfg}.lo"] = e["abs_lo_2.5"]
        out[f"E1.{cfg}.hi"] = e["abs_hi_97.5"]
        out[f"E1.{cfg}.met"] = e["E1_met"]
    e = rd("model_level/baseline/E1_endpoint.csv").iloc[0]
    out["E1.share"] = e["share_self_minus_placebo_mean"]
    out["E1.share_lo"] = e["share_lo_2.5"]
    out["E1.share_hi"] = e["share_hi_97.5"]
    for cyc, d in [("I", "model_level_cycle_I"), ("J", "model_level_cycle_J")]:
        e = rd(f"{d}/baseline/E1_endpoint.csv").iloc[0]
        out[f"E1.cycle{cyc}.abs"] = e["abs_self_minus_clin_mean"]
        out[f"E1.cycle{cyc}.met"] = e["E1_met"]
    auc = rd("model_level/baseline/P1_auc.csv").set_index("model")["auc_mean"]
    out["AUC.self"], out["AUC.clin"] = auc["f_self"], auc["f_clin"]
    p2 = rd("model_level/baseline/P2_group_importance.csv").set_index(["model", "group"])
    out["share.access.self"] = p2.loc[("f_self", "access"), "share"]
    out["share.access.placebo"] = p2.loc[("f_placebo", "access"), "share"]
    out["imp.demo.self"] = p2.loc[("f_self", "demographic_SES"), "importance"]
    out["imp.demo.clin"] = p2.loc[("f_clin", "demographic_SES"), "importance"]

    # ---------------- CF primary, per seed
    c6 = rd("cf_primary/C6_all_seeds.csv")
    for sd in (42, 43, 44):
        g = c6[c6["seed"] == sd].set_index("endpoint")
        e3 = g.loc["E3"]
        for k in ["A_M0", "A_M0_lb", "A_M0_minus_A_M2", "A_M0_minus_A_M2_lb", "A_M0_plus_A_M2",
                  "A_M0_plus_A_M2_lb", "A_M2", "n_common", "ECD_self_M0", "ECD_clin_M0", "ECD_self_M2", "ECD_clin_M2"]:
            out[f"E3.{sd}.{k}"] = e3[k]
        out[f"E3.{sd}.I_M0"] = e3["ECD_self_M0"] + e3["ECD_clin_M0"]
        out[f"E3.{sd}.I_M2"] = e3["ECD_self_M2"] + e3["ECD_clin_M2"]
        out[f"E3.{sd}.M2_reduction_pct"] = 100 * (abs(e3["A_M0"]) - abs(e3["A_M2"])) / abs(e3["A_M0"])
        out[f"E3.{sd}.M2_abs_red"] = abs(e3["A_M0"]) - abs(e3["A_M2"])
        ar = g.loc["E3_all_returned"]
        out[f"E3all.{sd}.diff"], out[f"E3all.{sd}.diff_lb"] = ar["A_M0_minus_A_M2"], ar["A_M0_minus_A_M2_lb"]
        e4 = g.loc["E4"]
        for k in ["ECD_self_M0_minus_M1", "ECD_self_M0_minus_M1_lb", "ECD_self_M1_residual", "n_common"]:
            out[f"E4.{sd}.{k}"] = e4[k]
        e6 = g.loc["E6"]
        for k in ["E6", "E6_lb", "n_patients", "D_self_source", "D_clin_source"]:
            out[f"E6.{sd}.{k}"] = e6[k]
        c10 = rd(f"cf_primary/seed{sd}/C10_ablation.csv").set_index(["ablation", "set"])
        st = c10.loc[("diag_all", "S_star")]
        out[f"abl.{sd}.Sstar.A_M0"], out[f"abl.{sd}.Sstar.A_abl"] = st["A_M0"], st["A_ablated"]
        out[f"abl.{sd}.Sstar.reduction_pct"] = 100 * (1 - st["A_ablated"] / st["A_M0"])
        for grp in ["access_only", "other_dx_only", "srh_only"]:
            out[f"abl.{sd}.{grp}"] = c10.loc[(grp, "S_M0"), "E6"]
        m0 = c10.loc[("diag_all", "S_M0")]
        out[f"touch.{sd}.SM0.self"] = m0["cfs_touching_group_pct_self"]      # % valid CFs changing >= 1 diag var
        out[f"touch.{sd}.SM0.clin"] = m0["cfs_touching_group_pct_clin"]
        out[f"abl.{sd}.Sstar.abs_red"] = abs(st["A_M0"]) - abs(st["A_ablated"])
        out[f"abl.{sd}.Sstar.mag_red_pct"] = 100 * out[f"abl.{sd}.Sstar.abs_red"] / abs(st["A_M0"])
        c1 = rd(f"cf_primary/seed{sd}/C1_summary.csv").set_index(["source", "mode"])
        for src in ("f_self", "f_clin"):
            for m in ("M0_global", "M1_taxonomy", "M2_locked"):
                out[f"cov.{sd}.{src}.{m}"] = c1.loc[(src, m), "valid_recourse_coverage_pct"]
            for k in ("bmi_rel_change_mean_pct", "bmi_drop_gt10pct_pct"):
                out[f"bmi.{sd}.{src}.{k}"] = c1.loc[(src, "M1_taxonomy"), k]
    rob = rd("cf_primary/C6_robustness.csv").set_index("endpoint")["robustness_status"]
    for ep in rob.index:
        out[f"robust.{ep}"] = rob[ep]

    # transfer matrix by CF (seed 42), pooled over channel subsets
    c7 = rd("cf_primary/seed42/C7_transfer_by_channel.csv")
    c7 = c7[c7["definition"] == "channel_directional"]
    for (src, mode), h in c7.groupby(["source", "mode"]):
        n = h["n_cfs"].sum()
        w = (h["dr_within_alt"] * h["n_cfs"]).sum() / n
        c = (h["dr_cross_alt"] * h["n_cfs"]).sum() / n
        on_self, on_clin = (w, c) if src == "f_self" else (c, w)
        out[f"A3.{src}.{mode}.n"] = n
        out[f"A3.{src}.{mode}.on_self"], out[f"A3.{src}.{mode}.on_clin"] = on_self, on_clin
        out[f"A3.{src}.{mode}.same_minus_cross"] = w - c

    # E5 (seed 42) and per-cycle
    c3 = rd("cf_primary/seed42/C3_coverage_by_group.csv").set_index(["rule", "group"])
    for rule in ("top_30pct", "threshold_0.5"):
        r = c3.loc[(rule, "G01")]
        out[f"E5.{rule}.self"], out[f"E5.{rule}.clin"] = r["flagged_by_f_self_pct"], r["flagged_by_f_clin_pct"]
        out[f"E5.{rule}.self_only"], out[f"E5.{rule}.clin_only"] = r["self_only"], r["clin_only"]
        out[f"E5.{rule}.p"] = r["mcnemar_exact_p"]
    for cyc in ("I", "J"):
        out[f"E5.cycle{cyc}.p"] = rd(f"coverage_cycle_{cyc}/C3_coverage_by_group.csv").set_index(
            ["rule", "group"]).loc[("top_30pct", "G01"), "mcnemar_exact_p"]

    # ---------------- CF sensitivity (seed 42)
    for d in ("cf_logreg", "cf_genetic", "cf_clinpos"):
        g = rd(f"{d}/C6_endpoints_E3_E4.csv").set_index("endpoint")
        out[f"{d}.E3.met"], out[f"{d}.E3.n"] = g.loc["E3", "met"], g.loc["E3", "n_common"]
        out[f"{d}.E3.A_M0"], out[f"{d}.E3.A_M2"] = g.loc["E3", "A_M0"], g.loc["E3", "A_M2"]
        out[f"{d}.E3.reduction_pct"] = 100 * (1 - g.loc["E3", "A_M2"] / g.loc["E3", "A_M0"])
        c10 = rd(f"{d}/C10_ablation.csv").set_index(["ablation", "set"])
        out[f"{d}.E6"] = c10.loc[("diag_all", "S_M0"), "E6"]
    m2p = rd("cf_M2phys/C9_alt_restriction_M2phys.csv").set_index("quantity")
    for q in ("A_M0", "A_M2phys"):
        out[f"M2phys.{q}"] = m2p.loc[q, "mean"]
    out["M2phys.n"] = m2p.loc["A_M0", "n_common"]
    r = m2p.loc["A_M0_minus_A_M2"]
    out["M2phys.diff"], out["M2phys.diff_lo"], out["M2phys.diff_hi"] = r["mean"], r["lo_2.5"], r["hi_97.5"]
    m3 = rd("cf_M3/C1_summary.csv").set_index(["source", "mode"])
    for src in ("f_self", "f_clin"):
        out[f"M3.{src}.valid_pct"] = m3.loc[(src, "M3_evidence"), "valid_recourse_coverage_pct"]
    k = rd("coef_signs/K1_coef_signs.csv").set_index("feature")
    out["coef.visits.self"], out["coef.visits.clin"] = k.loc["visits_past_year", "coef_self"], k.loc["visits_past_year", "coef_clin"]
    out["coef.opposite_both_excl0"] = int(k["opposite_sign_both_excl0"].sum())
    s1 = rd("design_se/S1_disagreement_se.csv").set_index("threshold")
    out["disagree140"], out["disagree130"] = s1.loc[140, "pct"], s1.loc[130, "pct"]
    return out


if __name__ == "__main__":
    cols = {os.path.basename(p.rstrip("/")): numbers(p) for p in sys.argv[1:]}
    df = pd.DataFrame(cols)
    pd.set_option("display.max_rows", 500)
    pd.set_option("display.width", 200)
    print(df.to_string(float_format=lambda v: f"{v:.4f}"))
