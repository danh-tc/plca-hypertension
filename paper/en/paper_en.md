# Attribution is not mitigation: a paired-label counterfactual audit of hypertension classification models

Cong-Danh Tran — [Affiliation, City, Vietnam] · [email] · ORCID [ORCID]

## Highlights

- Models trained on self-reported labels rely more on healthcare access features.
- Diagnosis-related features contribute to CF asymmetry in both NHANES periods.
- Ablation reduces asymmetry by 50–67%; feature locking by 9–27% (2015–2018).
- Guideline-based rules leave valid CFs for only 3–12% of queries (2015–2018).
- The reliance difference is not reproduced with BP-only labels in untreated adults.

## Abstract

**Background.** Counterfactual explanations (CFs) show which input changes would change a model's prediction. A hypertension label based on self-reported diagnosis reflects both the disease and whether it has been diagnosed. It is unclear how this affects CFs, and whether restricting CF changes removes the effect.

**Objective.** To test separately how much models rely on each feature group, how much a group contributes to the difference between two models' responses to the same CF, and whether locking that group in new CFs reduces this difference.

**Methods.** In NHANES, each adult has a self-reported label and an examination-based label (blood pressure ≥140/90 mmHg or treatment). XGBoost models differed only in their training label. We measured grouped permutation importance, generated CFs with DiCE, scored each CF with one evaluation model per label, reset diagnosis-related features in generated CFs (ablation), and generated new CFs with these features locked or under guideline-based rules. The procedure was developed on 2011–2014 data (n = 10,311) and applied to 2015–2018 data (n = 10,151) with retrained models.

**Results.** In 2015–2018, permuting access-to-care features reduced AUC more for the self-report model (difference 0.014 [0.008; 0.019]); this was not reproduced with a blood-pressure-only label in untreated adults. Diagnosis-related changes contributed 4.3 percentile points (lower bound 3.7) to the difference in score drops between the evaluation models, in all seeds and both periods. Ablation reduced this difference by 50–67%; locking reduced it by 9–27% and was unstable in 2011–2014. Under guideline-based rules, only 3–12% of individuals had a valid CF.

**Conclusion.** Knowing which features contribute to a difference does not show that locking them will reduce it.

**Keywords:** Counterfactual explanations; Explainable artificial intelligence; Clinical decision support; Label bias; Hypertension; Algorithmic recourse; NHANES

## 1. Introduction

Counterfactual explanations (CFs) describe small changes to a person's features that would change a model's prediction [1,2]. In clinical decision support [3], a CF may be presented as a suggestion, such as reducing waist circumference or becoming more physically active. However, a CF only tells us which input values would change the output of one specific model. It does not show that making the same change in real life would improve the person's health.

A model learns whatever its training label records. If the label reflects both the disease and the process of detecting the disease, the model can learn both. Hypertension is a clear example. Many people with hypertension have never been diagnosed [4,5], and self-reported hypertension misses part of the cases found by measurement [6]. Studies of proxy labels and under-testing show that the way an outcome is recorded can bias model predictions [7,8]. For a model trained on self-reported diagnosis, features such as health insurance or a usual place of care can be useful because they help to predict who has been diagnosed, not because they describe blood pressure. CFs from such a model may then suggest changing these features.

Three lines of work are relevant here: label bias, the stability of CFs across models, and the use of domain knowledge to restrict which changes a CF may contain. Thieu [9] proposed a directional taxonomy for diabetes CFs on BRFSS data and suggested that some implausible CFs may come from self-reported labels; however, the data had no measured label for comparison. Cerrato et al. [10] showed that changing the definition of an income label changes the resulting set of CFs. What is still missing is a way to test, on the same people, how much each feature group contributes to the difference between two clinical label definitions, and whether restricting that group reduces the difference.

This distinction matters because the usual response to an implausible CF is to stop the algorithm from changing the feature involved. When a feature is locked, however, the algorithm can find another combination of changes, and the new CFs may still affect the two models differently. Measuring how much a feature group contributes to existing CFs and testing what happens when the group is locked during CF generation are therefore two separate tasks.

We propose the Paired-Label Counterfactual Audit (PLCA), an audit procedure based on two label definitions recorded for the same people. PLCA is not a new CF algorithm. NHANES suits this design because participants report whether they have ever been told that they have hypertension, and their blood pressure is measured in the same survey. The models in this study are tools for the audit; they are not intended to replace blood pressure measurement or clinical diagnosis.

PLCA separates three questions:

1. **Reliance.** Does the model trained on self-reported labels need access-to-care features more than the model trained on examination-based labels?
2. **Contribution.** When the same CF is scored by two evaluation models, one for each label, how much do changes to diagnosis-related features contribute to the difference in score drops?
3. **Mitigation.** If these features are locked when new CFs are generated, does the difference become smaller? Under guideline-based rules, can valid CFs still be found?

This study makes three contributions. First, PLCA scores the CFs of each model with evaluation models for both labels, which gives four same-label and cross-label comparisons, and it adds a label-noise control model for feature importance. Second, it separates the contribution of a feature group in generated CFs (E2) from the effect of locking that group when new CFs are generated (E3). Third, on NHANES, it shows that diagnosis-related features contribute to the difference in both survey periods, that the effect of locking them is unstable, and that guideline-based rules leave valid CFs for very few people. PLCA does not propose a new CF algorithm or a new importance method; its contribution is the combination of these analyses on two clinical label definitions for the same people.
