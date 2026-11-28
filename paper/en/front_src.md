## Highlights

- Self-report models relied more on healthcare access under the primary labels.
- Diagnosis-related features contribute to CF asymmetry in both NHANES periods.
- Ablation reduces asymmetry by 50–67%; feature locking by 9–27% (2015–2018).
- Guideline-based rules leave valid CFs for only 3–12% of queries (2015–2018).
- The reliance difference is not reproduced with BP-only labels in untreated adults.

## Abstract

**Background.** Counterfactual explanations (CFs) show which input changes would change a model's prediction. A hypertension label based on self-reported diagnosis reflects both the disease and whether it has been diagnosed. It is unclear how this affects CFs, and whether restricting CF changes removes the effect.

**Objective.** To test separately how much models rely on each feature group, how much a group contributes to the difference between two models' responses to the same CF, and whether locking that group in new CFs reduces this difference.

**Methods.** In the National Health and Nutrition Examination Survey (NHANES), each adult has a self-reported label and an examination-based label (blood pressure ≥140/90 mmHg [18.7/12.0 kPa] or treatment). XGBoost models differed only in their training label. We measured grouped permutation importance, generated CFs with DiCE, scored each CF with one evaluation model per label, reset diagnosis-related features in generated CFs (ablation), and generated new CFs with these features locked or under guideline-based rules. The procedure was developed on 2011–2014 data (n = 10,311) and applied to 2015–2018 data (n = 10,151) with retrained models.

**Results.** In 2015–2018, permuting access-to-care features reduced the area under the receiver operating characteristic curve (AUC) more for the self-report model (difference 0.014 [0.008; 0.019]); this was not reproduced with a blood-pressure-only label in untreated adults. Diagnosis-related changes contributed 4.3 percentile points (lower bound 3.7; 2015–2018, primary seed) to the difference in score drops between the evaluation models; this contribution was positive in all seeds and both periods. Ablation reduced this difference by 50–67%; locking reduced it by 9–27% and was unstable in 2011–2014. Under guideline-based rules, only 3–12% of individuals had a valid CF.

**Conclusion.** Knowing which features contribute to a difference does not show that locking them will reduce it.

**Keywords:** Counterfactual explanations; Explainable artificial intelligence; Clinical decision support; Label bias; Hypertension; NHANES

## Summary table

**What was already known on the topic**

- Self-reported hypertension misses undiagnosed cases, so a model trained on it can learn who has been diagnosed as well as who has the disease.
- Implausible counterfactual suggestions are usually handled by locking features or by applying domain-knowledge rules.

**What this study added to our knowledge**

- With two labels for the same NHANES adults, diagnosis-related features contributed to how differently two models responded to the same counterfactual in both survey periods.
- Locking these features did not reduce the difference consistently, and guideline-based rules left valid counterfactuals for only 3–12% of people, so constraints should be tested directly before counterfactuals are used in decision support.
