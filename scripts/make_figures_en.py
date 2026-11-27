"""English Figures 2-4 of the manuscript from one results folder.

Usage: python scripts/make_figures.py results/confirmation paper/vi
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

root, out = sys.argv[1], sys.argv[2]
plt.rcParams.update({"font.family": "Inter", "font.size": 10, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.spines.left": False,
                     "axes.spines.bottom": False, "xtick.labelsize": 9, "ytick.labelsize": 9.5,
                     "xtick.color": "#444444", "ytick.color": "#1a1a1a"})
BLUE, GREY, LIGHT, TXT, SUB = "#2a78d6", "#c2c2b6", "#e3e3df", "#1a1a1a", "#666666"
vn = lambda v, d=3: f"{v:.{d}f}".replace("-", "−")


def header(fig, title, sub):
    fig.text(0.04, 0.965, title, fontsize=12.5, color=TXT, va="top")
    fig.text(0.04, 0.905, sub, fontsize=9.5, color=SUB, va="top")


# ---------------- Figure 2: group importance (E1)
p2 = pd.read_csv(os.path.join(root, "model_level/baseline/P2_group_importance.csv")).set_index(["model", "group"])
groups = [("access", "Access to care"), ("other_diagnoses", "Other diagnoses"),
          ("self_rated_health", "Self-rated health"), ("physiology", "Physiology"), ("lifestyle", "Lifestyle")]
models = [("f_self", "f_self (self-reported)", BLUE, "o"), ("f_clin", "f_clin (examination-based)", "#8f8f84", "s"),
          ("f_placebo", "f_placebo (label noise)", "#cfcfc8", "^")]
fig, ax = plt.subplots(figsize=(6.6, 4.3))
fig.subplots_adjust(left=0.27, right=0.97, top=0.76, bottom=0.12)
for gi, (g, glab) in enumerate(groups):
    for mi, (m, mlab, col, mk) in enumerate(models):
        r = p2.loc[(m, g)]
        y = -gi - mi * 0.26
        ax.plot([r["imp_ci_low"], r["imp_ci_high"]], [y, y], color=col, lw=1.6, solid_capstyle="butt")
        ax.plot(r["importance"], y, mk, color=col, ms=6.5, mec="#555555" if m == "f_placebo" else col, mew=0.6, label=mlab if gi == 0 else None)
        if g == "access" and m != "f_placebo":
            ax.text(r["imp_ci_high"] + 0.0012, y, vn(r["importance"]), va="center", fontsize=8.5, color=TXT)
ax.set_yticks([-gi - 0.26 for gi in range(len(groups))])
ax.set_yticklabels([g[1] for g in groups])
ax.tick_params(axis="y", length=0)
ax.axvline(0, color=GREY, lw=0.8)
ax.grid(axis="x", color="#e6e6e6", lw=0.7)
ax.set_xlabel("AUC drop", color=SUB, fontsize=9)
ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: vn(v, 2)))
ax.legend(loc="lower center", bbox_to_anchor=(0.36, 1.0), ncol=3, frameon=False, fontsize=8.5, handletextpad=0.3)
header(fig, "The self-report model relies more on access to care",
       "AUC drop when a whole feature group is permuted; dot = estimate, line = 95% interval")
fig.savefig(os.path.join(out, "fig2.png"), dpi=200)
plt.close(fig)

# ---------------- Figure 3: A at M0, after ablation, at M2 on S*
fig, ax = plt.subplots(figsize=(6.6, 3.9))
fig.subplots_adjust(left=0.1, right=0.98, top=0.74, bottom=0.25)
labels = ["M0: baseline constraints", "Ablation of generated CFs", "M2: new CFs, group locked"]
cols = [GREY, LIGHT, BLUE]
c6 = pd.read_csv(os.path.join(root, "cf_primary/C6_all_seeds.csv"))
xt, xl = [], []
for k, sd in enumerate((42, 43, 44)):
    e3 = c6[(c6["seed"] == sd) & (c6["endpoint"] == "E3")].iloc[0]
    st = pd.read_csv(os.path.join(root, f"cf_primary/seed{sd}/C10_ablation.csv")).set_index(["ablation", "set"]).loc[("diag_all", "S_star")]
    vals = [e3["A_M0"], st["A_ablated"], e3["A_M2"]]
    for j, v in enumerate(vals):
        x = k * 4 + j
        ax.bar(x, v, width=0.8, color=cols[j], label=labels[j] if k == 0 else None)
        ax.text(x, v + (0.004 if v >= 0 else -0.004), vn(v), ha="center", va="bottom" if v >= 0 else "top", fontsize=8.5)
    # reduction in magnitude |A|, as in E3 (decline vs. sign reversal kept apart)
    ra = 100 * (abs(vals[0]) - abs(vals[1])) / abs(vals[0]); rm = 100 * (abs(vals[0]) - abs(vals[2])) / abs(vals[0])
    flip = " (sign flip)" if vals[1] * vals[0] < 0 else ""
    xt.append(k * 4 + 1)
    xl.append(f"Seed {sd} (n = {int(e3['n_common'])})\nablation −{ra:.0f}%{flip}\nlocking −{rm:.0f}%")
ax.set_xticks(xt)
ax.set_xticklabels(xl, fontsize=8.8)
ax.tick_params(axis="x", length=0, pad=16)
ax.set_ylim(-0.04, ax.get_ylim()[1] * 1.1)
ax.axhline(0, color=GREY, lw=0.8)
ax.grid(axis="y", color="#e6e6e6", lw=0.7)
ax.set_axisbelow(True)
ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: vn(v, 2)))
ax.set_ylabel("A (percentile scale)", color=SUB, fontsize=9)
ax.legend(loc="lower left", bbox_to_anchor=(-0.02, 1.0), ncol=3, frameon=False, fontsize=8.3, handlelength=1.0, columnspacing=1.2)
header(fig, "Ablation reduces |A| more than feature locking (2015–2018)",
       "A on the same people (S02) in each seed; below: reduction in |A| relative to M0")
fig.savefig(os.path.join(out, "fig3.png"), dpi=200)
plt.close(fig)

# ---------------- Figure 4: valid-recourse coverage by constraint mode 
thtn = root
rows = []
for src, slab in (("f_self", "f_self"), ("f_clin", "f_clin")):
    for sd in (42, 43, 44):
        c1 = pd.read_csv(os.path.join(thtn, f"cf_primary/seed{sd}/C1_summary.csv")).set_index(["source", "mode"])
        rows.append((f"{slab} · seed {sd}", c1.loc[(src, "M0_global"), "valid_recourse_coverage_pct"],
                     c1.loc[(src, "M2_locked"), "valid_recourse_coverage_pct"],
                     c1.loc[(src, "M1_taxonomy"), "valid_recourse_coverage_pct"]))
fig, ax = plt.subplots(figsize=(6.6, 3.8))
fig.subplots_adjust(left=0.2, right=0.97, top=0.74, bottom=0.12)
modes = [("M0: baseline constraints", GREY), ("M2: diagnosis-related group locked", "#8fb5e6"), ("M1: guideline-based rules", BLUE)]
h = 0.26
for i, (lab, *vals) in enumerate(rows):
    for k, (v, (mlab, col)) in enumerate(zip(vals, modes)):
        y = -i + (1 - k) * h
        ax.barh(y, v, height=h * 0.9, color=col, label=mlab if i == 0 else None)
        ax.text(v + 1, y, f"{v:.1f}" + "%", va="center", fontsize=7.5, color=TXT)
ax.set_yticks([-i for i in range(len(rows))])
ax.set_yticklabels([r[0] for r in rows])
ax.tick_params(axis="y", length=0)
ax.set_xlim(0, 112)
ax.set_xticks([0, 25, 50, 75, 100])
ax.set_xticklabels(["0%", "25%", "50%", "75%", "100%"])
ax.axvline(0, color=GREY, lw=0.8)
ax.grid(axis="x", color="#e6e6e6", lw=0.7)
ax.set_axisbelow(True)
ax.legend(loc="lower center", bbox_to_anchor=(0.42, 1.0), ncol=3, frameon=False, fontsize=8.3, handlelength=1.0)
header(fig, "Guideline-based rules sharply reduce valid-CF coverage",
       "Share of the 200 selected people with at least one valid CF, by constraint mode")
fig.savefig(os.path.join(out, "fig4.png"), dpi=200)
plt.close(fig)
print("figures written to", out)
