"""English Figure 1 (PLCA design schematic)."""
import sys, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle
plt.rcParams.update({"font.family": "Inter"})
out = sys.argv[1] if len(sys.argv) > 1 else "."
BLUE, PALE, GREY, TXT, SUB = "#2a78d6", "#eef4fc", "#c2c2b6", "#1a1a1a", "#555555"
fig, ax = plt.subplots(figsize=(10, 6.2)); ax.set_xlim(0, 100); ax.set_ylim(0, 62); ax.axis("off")
def box(x, y, w, h, title, lines=(), fc="white", ec=GREY, tsize=10.5):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.25,rounding_size=0.8", fc=fc, ec=ec, lw=1.1))
    ax.text(x + w / 2, y + h - 1.8, title, ha="center", va="top", fontsize=tsize, weight="semibold", color=TXT)
    for k, l in enumerate(lines):
        ax.text(x + w / 2, y + h - 5.0 - 2.9 * k, l, ha="center", va="top", fontsize=8.8, color=SUB if k else TXT)
def arrow(x0, y0, x1, y1):
    ax.annotate("", xy=(x1, y1), xytext=(x0, y0), arrowprops=dict(arrowstyle="-|>", color="#888888", lw=1.1))
# data
box(2, 50, 96, 10, "Same NHANES adults, two labels",
    ["Y_self: ever told by a doctor that they have hypertension   ·   Y_clin: BP ≥ 140/90 mmHg or current treatment",
     "Same features, same data, same XGBoost settings; only the training label differs"], fc=PALE, ec=BLUE)
# model level
box(2, 13, 27, 33, "Model level (E1)", ["Reliance", "f_self, f_clin, f_placebo", "grouped permutation importance",
                                       "AUC drop and importance share", "f_placebo: class-wise", "random label flips"])
# CF level
box(32, 13, 44, 33, "Counterfactual level", ["DiCE CFs: M0 baseline, M1 guideline rules, M2 locked",
                                            "each CF is scored by both evaluation models"])
# 2x2 matrix
mx, my, cw, chh = 45, 24.4, 10.5, 3.5
ax.text(mx + cw, my + 2 * chh + 2.3, "evaluation model", ha="center", fontsize=8, color=SUB)
for j, t in enumerate(["g_self", "g_clin"]):
    ax.text(mx + cw * j + cw / 2, my + 2 * chh + 0.1, t, ha="center", va="bottom", fontsize=8.5, color=TXT)
for i, (src, cells) in enumerate([("CF from f_self", ["R_ss", "R_sc"]), ("CF from f_clin", ["R_cs", "R_cc"])]):
    yy = my + chh * (1 - i)
    ax.text(mx - 0.8, yy + chh / 2, src, ha="right", va="center", fontsize=8.5, color=TXT)
    for j, c in enumerate(cells):
        same = (i == j)
        ax.add_patch(Rectangle((mx + cw * j, yy), cw, chh, fc=BLUE if same else "white", ec=GREY, lw=0.9))
        ax.text(mx + cw * j + cw / 2, yy + chh / 2, c, ha="center", va="center", fontsize=9, color="white" if same else TXT)
ax.text(55.5, 21.9, "A = (R_ss + R_cs) − (R_sc + R_cc)", ha="center", fontsize=9, color=TXT)
for k, (t, s1, s2) in enumerate([("E2 · contribution", "reset the group in", "generated CFs"),
                                 ("E3 · locking", "new CFs with the", "group locked (M2)"),
                                 ("E4 · coverage", "valid CFs under", "guideline rules (M1)")]):
    x = 33.5 + 14.2 * k
    ax.add_patch(FancyBboxPatch((x, 13.7), 12.6, 6.9, boxstyle="round,pad=0.15,rounding_size=0.5", fc=PALE, ec=BLUE, lw=0.8))
    ax.text(x + 6.3, 20.0, t, ha="center", va="top", fontsize=8.4, weight="semibold", color=TXT)
    ax.text(x + 6.3, 17.8, s1, ha="center", va="top", fontsize=7.6, color=SUB)
    ax.text(x + 6.3, 16.0, s2, ha="center", va="top", fontsize=7.6, color=SUB)
# screening
box(79, 13, 19, 33, "Screening (E5)", ["Simulated selection", "top 30% of scores", "per model", "share of G01 people", "(Y_clin = 1, Y_self = 0)", "McNemar test"])
for x in (15.5, 54, 88.5): arrow(x, 50, x, 46.6)
ax.text(50, 8.5, "2011–2014: develop the procedure   ·   2015–2018: report results, with all models retrained",
        ha="center", fontsize=9.2, color=SUB)
ax.text(50, 4.5, "Results describe the models and data of this study; they are not causal clinical effects.",
        ha="center", fontsize=8.5, color=SUB, style="italic")
fig.savefig(f"{out}/fig1.png", dpi=200, bbox_inches="tight", pad_inches=0.1)
