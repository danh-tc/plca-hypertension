"""Builds appendix Tables A7 (performance/calibration) and A8 (data characteristics) as markdown
from results_posthoc/performance/<period>/*.csv. Post hoc reporting, not an endpoint."""
import sys
import pandas as pd

root = sys.argv[1] if len(sys.argv) > 1 else "results_posthoc/performance"
P = {"discovery": "2011–2014", "confirmation": "2015–2018"}
M = [("auroc", "AUC"), ("auprc", "AUPRC"), ("accuracy", "Accuracy"), ("balanced_accuracy", "Balanced accuracy"),
     ("sensitivity", "Sensitivity"), ("specificity", "Specificity"), ("ppv", "PPV"), ("npv", "NPV"),
     ("prevalence", "Prevalence (test set)"), ("brier", "Brier score"),
     ("cal_intercept", "Calibration intercept"), ("cal_slope", "Calibration slope")]
perf = {p: pd.read_csv(f"{root}/{p}/PERF_metrics.csv").query("family == 'cf_audit'") for p in P}
f = lambda r: f"{r.estimate:.3f} [{r.ci_low:.3f}; {r.ci_high:.3f}]".replace("-", "−")
out = ["**Table A7.** Test-set performance and calibration of the models used to generate counterfactuals "
       "(post hoc reporting; threshold 0.5).", "",
       "| Metric | f_self, 2011–2014 | f_clin, 2011–2014 | f_self, 2015–2018 | f_clin, 2015–2018 |",
       "|---|---|---|---|---|"]
for k, lab in M:
    cells = []
    for p in P:
        for m in ("f_self", "f_clin"):
            r = perf[p].query("model == @m and metric == @k").iloc[0]
            cells.append(f(r))
    out.append(f"| {lab} | " + " | ".join(cells) + " |")
n = {p: int(pd.read_csv(f"{root}/{p}/DATA_class_balance.csv").query("label=='Y_self' and split=='test'").n.iloc[0]) for p in P}
out += ["", f"*Each model against its own training label (f_self: Y_self; f_clin: Y_clin). XGBoost with training-split median "
        f"imputation, seed 42, 30% test split (n = {n['discovery']:,} and {n['confirmation']:,}). 95% intervals: test-set "
        "bootstrap (B = 1,000) with the fitted model held fixed; retraining variability is not included. Unweighted. "
        "The refitted test AUC matched the frozen run exactly. AUC: area under the receiver operating characteristic curve; AUPRC: area under the precision-recall curve; PPV/NPV: positive/negative predictive value. Calibration intercept with slope fixed at 1; slope from "
        "logistic recalibration on logit p. CF analyses use percentile scores, which depend only on the ranking of scores.*", ""]

dic = pd.read_csv(f"{root}/confirmation/DATA_dictionary.csv")
d = {p: pd.read_csv(f"{root}/{p}/DATA_distribution.csv").set_index("feature") for p in P}
mi = {p: pd.read_csv(f"{root}/{p}/DATA_missingness.csv").set_index("feature") for p in P}
def summ(p, ft, t):
    r = d[p].loc[ft]
    if t == "ordinal" or ft == "age":
        return f"{r.value:.0f} [{r.q1:.0f}; {r.q3:.0f}]"
    if t == "continuous":
        k = 2 if ft == "income_pir" else (0 if ft == "total_chol" else 1)
        return f"{r.value:.{k}f} [{r.q1:.{k}f}; {r.q3:.{k}f}]"
    return f"{r.value:.1f}%"
out += ["**Table A8.** Features, coding, distribution and missingness of the analytic samples (unweighted).", "",
        "| Feature | NHANES source; coding | 2011–2014, median [IQR] or % | Missing, % | 2015–2018, median [IQR] or % | Missing, % |",
        "|---|---|---|---|---|---|"]
G = {"demographic_SES": "demographic", "access": "access", "other_diagnoses": "other diagnoses",
     "lifestyle": "lifestyle", "physiology": "physiology", "self_rated_health": "self-rated health"}
NAME = {"age": "Age", "female": "Female sex", "education": "Education", "income_pir": "Income-to-poverty ratio",
        "insured": "Insured", "routine_place": "Usual place of care", "visits_past_year": "Visits in past year",
        "chol_checked": "Cholesterol ever checked (not used)", "diabetes_told": "Told diabetes",
        "high_chol_told": "Told high cholesterol", "current_smoker": "Current smoker", "drinks_per_day": "Drinks per drinking day",
        "vigorous_rec_pa": "Vigorous recreational activity", "moderate_rec_pa": "Moderate recreational activity",
        "bmi": "BMI", "waist": "Waist", "total_chol": "Total cholesterol", "hba1c": "HbA1c", "self_rated_health": "Self-rated health"}
races = [f for f in dic.feature if f.startswith("race_")]
for _, r in dic.iterrows():
    if r.feature.startswith("race_"):
        if r.feature != races[0]:
            continue
        cells = []
        for p in P:
            cells += [" / ".join(f"{d[p].loc[f].value:.1f}" for f in races),
                      f"{mi[p].loc[races, 'missing_pct_all'].max():.1f}"]
        out.append(f"| Race/ethnicity, % ({len(races)} indicators) | RIDRETH3 = 1 / 2 / 3 / 4 / 6 / 7 | " + " | ".join(cells) + " |")
        continue
    code = f"{r.nhanes_source.replace('/', ', ')}; {r.unit_or_coding}" if isinstance(r.unit_or_coding, str) and r.unit_or_coding else r.nhanes_source
    code = code if isinstance(code, str) else ""
    code = code.replace("/", ", ") if ";" not in code else code
    out.append(f"| {NAME[r.feature]} | {code} | {summ('discovery', r.feature, r.type)} | "
               f"{mi['discovery'].loc[r.feature, 'missing_pct_all']:.1f} | {summ('confirmation', r.feature, r.type)} | "
               f"{mi['confirmation'].loc[r.feature, 'missing_pct_all']:.1f} |")
bal = {p: pd.read_csv(f"{root}/{p}/DATA_class_balance.csv").query("split == 'all'").set_index("label") for p in P}
out += ["", "*Feature groups as in Section 2.2. RIDRETH3: 1 Mexican American, 2 Other Hispanic, 3 non-Hispanic White, 4 non-Hispanic Black, "
        "6 non-Hispanic Asian, 7 other or multiracial. Missing % differed by at most "
        f"{max((mi[p].missing_pct_train - mi[p].missing_pct_test).abs().max() for p in P):.1f} percentage points between "
        "training and test splits. Skip patterns resolved by the feature builder: never smokers have current_smoker = 0 and "
        "never drinkers have drinks_per_day = 0; BPQ060 is skipped when high cholesterol was reported and was dropped. "
        "Refused and don't-know codes were set to missing; no other outlier removal or truncation was applied. Class balance (positive %): "
        f"Y_self {bal['discovery'].loc['Y_self','prevalence_pct']:.1f}% and Y_clin {bal['discovery'].loc['Y_clin140','prevalence_pct']:.1f}% "
        f"in 2011–2014; {bal['confirmation'].loc['Y_self','prevalence_pct']:.1f}% and {bal['confirmation'].loc['Y_clin140','prevalence_pct']:.1f}% "
        "in 2015–2018; no resampling or class weighting was used.*", ""]
print("\n".join(out))
