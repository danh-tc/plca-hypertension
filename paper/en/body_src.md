# 1. Introduction

Counterfactual explanations (CFs) describe small changes to a person's features that would change a model's prediction [1,2]. In clinical decision support [3], a CF may be shown as a suggestion, such as reducing waist circumference, although it only shows what would change one model's output, not what would improve health [14,15].

A model learns whatever its training label records. Many people with hypertension are undiagnosed [4,5], so self-report misses cases found by measurement [6]. The way an outcome is recorded can bias predictions [7,8,11]. For a model trained on self-reported diagnosis, insurance or a usual place of care can predict who has been diagnosed rather than blood pressure, and its CFs may then suggest changing them.

Thieu [9] proposed a directional taxonomy that restricts how each feature may change in diabetes CFs, and suggested that some implausible CFs may come from self-reported labels; the data had no measured label for comparison. Changing a label definition changes the resulting CFs [10], as does changing among models of similar accuracy [16,18]. What is still missing is a test, on the same people, of how much a feature group contributes to the difference between two clinical label definitions, and whether restricting that group reduces it. This matters because the usual response to an implausible CF is to lock the feature involved [9,20,21].

We propose the Paired-Label Counterfactual Audit (PLCA), an audit procedure based on two label definitions recorded for the same people. The National Health and Nutrition Examination Survey (NHANES) suits this design because participants report whether they have ever been told that they have hypertension, and their blood pressure is measured in the same survey. PLCA asks three questions: (1) *reliance*: does the self-report model need access-to-care features more? (2) *contribution*: how much do diagnosis-related changes contribute to the difference between the two models' responses to the same CF? (3) *mitigation*: does locking these features reduce the difference, and can valid CFs still be found under guideline-based rules?

PLCA separates the contribution of a feature group in generated CFs (E2) from the effect of locking it in new CFs (E3). It is not a new CF algorithm or importance method; it combines existing analyses on two clinical labels for the same people.

# 2. Methods

## 2.1. Data and labels

We used public NHANES data [28,29]. The procedure was developed on 2011–2014 data (n = 10,311) and applied to 2015–2018 data (n = 10,151) with all models retrained. We included non-pregnant adults aged ≥20 years with valid blood pressure readings, an answer to BPQ020, and known treatment status.

Each person had two labels. *Y_self* was 1 if the person had ever been told by a doctor or other health professional that they had hypertension. *Y_clin*, the examination-based label, was 1 if systolic pressure was ≥140 mmHg (18.7 kPa), diastolic pressure was ≥90 mmHg (12.0 kPa), or the person was taking blood pressure medication. The 130/80 mmHg (17.3/10.7 kPa) threshold [4] was a sensitivity analysis. People without a reported diagnosis are not asked about treatment and were coded as untreated. Y_clin is a phenotype, not ground truth, and its treatment component still depends on past diagnosis. Pairs (Y_self, Y_clin) define four groups: G00, G01 (examination-positive only), G10 (self-report-positive only) and G11. Fig. 1 summarizes the design.

![Fig. 1. Design of PLCA. The models differ only in the training label. At the CF level, each CF is scored by both evaluation models, which gives a 2 × 2 same-label and cross-label matrix (dark cells: same label). E2 analyses generated CFs; E3 generates new CFs with the group locked.](fig1.pdf){width=100%}

## 2.2. Features and preprocessing

Models used six feature groups: demographics and socioeconomic status; access to care (insurance, usual place of care, health care visits); other diagnoses (diabetes, high cholesterol); lifestyle (smoking, drinks per drinking day, moderate and vigorous recreational activity); physiology (body mass index (BMI), waist, total cholesterol, HbA1c); and self-rated health. Sex was the sex recorded by NHANES; gender was not available. Blood pressure measurements and blood pressure questions were not inputs. "Cholesterol ever checked" (BPQ060) was excluded because its missingness depends on Y_self through skip patterns (57.8% vs 26.0%). We call access to care, other diagnoses and self-rated health together the *diagnosis-related features*. Data were split before preprocessing. For E1, XGBoost handled missing values natively; for CF analyses, missing values were filled with the training-split median. The feature dictionary, distributions and missingness are given in the supplementary material (Appendix A).

## 2.3. Reliance (E1)

XGBoost [30] models (300 trees, depth 4, learning rate 0.05, row and column subsampling 0.8; fixed in advance, not tuned) were trained on a 70/30 split stratified by Y_clin. *f_self* learned Y_self and *f_clin* learned Y_clin. A label-noise control, *f_placebo*, learned Y_clin after random flips whose rates depended only on the Y_clin class and matched the observed disagreement in the training data. Grouped permutation importance [31,32,23] permuted all features in a group together on the test set and recorded the AUC (area under the receiver operating characteristic curve) drop (mean of three permutations). Shares divided each group's positive importance by the sum over groups. A two-level bootstrap (B = 100) resampled both the training set (models retrained) and the test set [33]. E1 required the 2.5th percentile of the AUC-drop difference f_self − f_clin for access to care to be above 0, and a positive mean difference in importance share between f_self and f_placebo; the share contrast was interpretable only if the share was defined in at least 80% of bootstrap draws.

## 2.4. Counterfactuals and evaluation models

We selected up to 200 untreated test-set people whom both f_self and f_clin predicted as positive (probability ≥0.5), ranked by the mean percentile score of the two models. DiCE 0.12 [2] (random search) was asked for up to five CFs per person in each constraint mode (Table 1). A CF was *valid* if it obeyed the rules of its mode and changed the prediction of the model that generated it from positive to negative. *Valid-CF coverage* was the share of selected people with at least one valid CF.

**Table 1.** Constraint modes used to generate CFs.

| Mode | What DiCE may change | Purpose |
|------------|------------------------------------|------------------------|
| M0, baseline | Everything except age, sex and race/ethnicity | Reference |
| M1, guideline-based rules | Eight features, only in the guideline direction (Appendix Table A.4); everything else fixed | Can valid CFs be found under clinically motivated rules? |
| M2, locking | As M0, with access to care, other diagnoses and self-rated health fixed | Does locking diagnosis-related features reduce the difference? |

Under M1, BMI and waist may fall only to their thresholds (25 kg/m², or 23 for non-Hispanic Asian people; 102 cm for men, 88 cm for women) [34–36,39,40]; imputed values are fixed (Appendix Table A.4).

We trained one *evaluation model* per label, g_self and g_clin, on the same bootstrap sample of the training set, and scored every CF with both. Because the two models have different score distributions, scores were converted to percentiles: p_m(x) is the share of test-set people whose g_m score is not higher than that of x. The *score drop* of a CF x′ for person x is

$$\Delta_m(x') = p_m(x) - p_m(x').$$

Let R_sm be the mean drop on evaluation model m for CFs generated by model s (first averaged over the CFs of each person, then over people). We define

$$\mathrm{ECD}_{self} = R_{ss} - R_{sc}, \qquad \mathrm{ECD}_{clin} = R_{cc} - R_{cs},$$

$$A = \mathrm{ECD}_{self} - \mathrm{ECD}_{clin} = (R_{ss}+R_{cs}) - (R_{sc}+R_{cc}).$$

*A/2 is the difference between the mean score drops of g_self and g_clin*, with both CF sources weighted equally; A > 0 means that g_self drops more. These quantities say nothing about real hypertension risk.

## 2.5. Contribution (E2) and locking (E3)

*E2* uses the valid CFs generated under M0. For each CF x′, we built x′_abl by resetting all diagnosis-related features to the person's original values, keeping every other change (*ablation*). The score recovered on model m is C_m = p_m(x′_abl) − p_m(x′), and

$$\mathrm{E2} = \overline{C_{self} - C_{clin}} = \tfrac{1}{2}\left[A(\mathrm{M0}) - A_{abl}\right],$$

averaged per person, with equal weight for the two CF sources; the ablated CF need not stay valid. E2 was computed on S0, the people with at least one valid CF from both models under M0.

*E3* asks DiCE for new CFs under M2. On S02, the people in S0 who also had valid CFs from both models under M2, E3 required

$$A(\mathrm{M0}) > 0 \quad \text{and} \quad |A(\mathrm{M2})| < |A(\mathrm{M0})|.$$

A change of sign with a larger size does not count. When A(M0) > 0, this is equivalent to A(M0) − A(M2) > 0 and A(M0) + A(M2) > 0. For a descriptive comparison, A_abl was also computed on S02, and the reduction in |A| was 100·(|A(M0)| − |A_after|)/|A(M0)|.

*E4* reported valid-CF coverage under M1 and the change in ECD_self from M0 to M1, the latter only when at least 40 people had valid CFs from f_self in both modes.

## 2.6. Statistical analysis

E3 used a participant-level bootstrap (B = 5,000); each inequality was tested with the one-sided 2.5th percentile, and all had to hold (intersection–union test). E2 was secondary and used the same bootstrap. No correction for multiple endpoints was applied. Analyses required at least 80 eligible people and 40 people in the analysis set. CF analyses were run with seeds 42 (primary), 43 and 44; for E2 and E3, seed 42 decided and the other seeds had to give point estimates in the same direction. Seeds are not independent replications. The bootstrap intervals are conditional on the trained models and on the people with valid CFs. *E5*, a secondary screening analysis, compared the share of G01 people in the top 30% of scores of each model with an exact McNemar test [37]. Table 2 used survey weights and Taylor linearization [29]; the models did not use weights. As a post hoc reporting analysis, we refitted the audited models and report test-set discrimination, threshold metrics at 0.5 and calibration (Appendix A). The study was not registered and follows TRIPOD+AI [38].

## 2.7. Sensitivity analyses and reproducibility

Sensitivity analyses (seed 42) changed the label definitions, the cycle, the model, the CF search and the selected people (Table 5). M2-phys locked physiology instead of diagnosis-related features, and M3 added a maximum 5% reduction in BMI and waist to M1. All results come from one run of `scripts/run_all.sh` (software and hardware: Appendix A).

# 3. Results

## 3.1. Sample

In 2015–2018, the two labels disagreed for a survey-weighted 12.9% [11.8; 13.9] of adults (23.1% [21.8; 24.3] with 130/80 mmHg). Compared with G11, G01 people were less likely to have a usual place of care or a visit in the past year (Table 2). The models used for CFs had test AUROC 0.810 (f_self) and 0.836 (f_clin) in 2015–2018, with balanced accuracy 0.726 and 0.752 at threshold 0.5 and calibration slopes 0.82 and 0.86 (Appendix Table A.7).

**Table 2.** Characteristics of the 2015–2018 sample by label pair (140/90 mmHg).

| Characteristic | All | G00 | G01 | G10 | G11 |
|------------------|--------|-----------|-----------|-----------|-----------|
| People (unweighted) | 10,151 | 5,533 | 785 | 562 | 3,271 |
| Age, years, mean (SD) | 48.4 (17.2) | 42.1 (15.6) | 56.4 (15.3) | 44.5 (15.5) | 61.2 (13.0) |
| Women, % | 51.1 | 52.3 | 45.3 | 41.7 | 51.9 |
| Non-Hispanic Black, % | 11.3 | 9.7 | 12.1 | 10.9 | 14.7 |
| College graduate or above, % | 31.6 | 35.4 | 30.3 | 28.4 | 24.3 |
| Income-to-poverty ratio < 1.3, % | 20.3 | 19.8 | 20.5 | 25.5 | 20.1 |
| Insured, % | 86.5 | 84.0 [81.2; 86.8] | 88.8 [85.2; 92.5] | 82.4 [77.2; 87.6] | 92.5 [90.4; 94.5] |
| Usual place of care, % | 82.6 | 78.0 [75.8; 80.1] | 81.8 [77.9; 85.7] | 78.7 [72.5; 84.8] | 93.9 [92.6; 95.2] |
| Visit in past year, % | 83.9 | 79.1 [77.5; 80.7] | 78.8 [74.5; 83.0] | 82.2 [78.4; 86.0] | 96.2 [95.3; 97.0] |
| BMI, kg/m², mean (SD) | 29.6 (7.1) | 28.3 (6.7) | 30.3 (7.3) | 30.9 (7.4) | 32.0 (7.2) |
| Systolic BP, mmHg, mean (SD) | 123.7 (17.7) | 115.8 (10.8) | 148.2 (13.1) | 122.0 (9.7) | 135.3 (20.0) |
| On BP medication, % | 24.1 | 0 | 0 | 0 | 89.2 |

*G00: both labels 0; G01: Y_clin = 1, Y_self = 0; G10: Y_self = 1, Y_clin = 0; G11: both 1. Survey-weighted (WTMEC2YR divided by the number of cycles); 95% confidence intervals for access-to-care rows by Taylor linearization. Medication is 0 outside G11 by label definition and skip pattern. Full table: Appendix Table A.6.*

## 3.2. Reliance (E1)

Test-set AUC (mean over bootstrap refits) was 0.806 for f_self and 0.831 for f_clin. Permuting access-to-care features reduced the AUC of f_self more than that of f_clin by 0.014 [0.008; 0.019] (Fig. 2). The importance share of access to care was 9.8% in f_self and 2.8% in f_placebo (difference 7.0 percentage points [2.4; 11.0]), so class-wise random label noise did not reproduce this reliance. The result was similar in 2011–2014 (0.015 [0.009; 0.022]). Removing G01 people from training reduced it to 0.005 [0.000; 0.010] (random removal: 0.014).

An important limit: in untreated people, compared with a blood-pressure-only label, the difference was −0.003 [−0.017; 0.011]. E1 therefore depends on the phenotype definition and the population.

![Fig. 2. AUC drop when each feature group is permuted, for the three models (NHANES 2015–2018, seed 42, two-level bootstrap B = 100). Dots are estimates and lines are 95% intervals. Demographics are not shown (f_self 0.103; f_clin 0.211).](fig2.pdf){width=82%}

## 3.3. Contribution (E2)

Resetting diagnosis-related features in M0 CFs raised the percentile score of g_self more than that of g_clin by 4.3 percentile points (E2 = 0.043; lower bound 0.037; n = 187). E2 was 0.044 (0.037) and 0.058 (0.049) in seeds 43 and 44, and positive in all three seeds of 2011–2014 (Appendix Table A.5). It was positive for CFs from both f_self (0.057) and f_clin (0.030). Between 49% and 65% of valid M0 CFs changed at least one diagnosis-related feature. Access to care, other diagnoses and self-rated health each contributed, but their order changed between seeds (Table 4).

## 3.4. Locking (E3)

In seed 42, 172 people formed S02. A(M0) was 0.120 (lower bound 0.097). With diagnosis-related features locked, A(M2) was 0.087; A(M0) − A(M2) was 0.033 (0.012) and A(M0) + A(M2) had a lower bound of 0.160, so E3 was met (Table 3). In seeds 43 and 44, all point estimates were positive, but the lower bound of A(M0) − A(M2) was negative (−0.009 and −0.004). When all returned CFs were used, including invalid ones, E3 was not met in any seed. In 2011–2014, E3 was not met: A changed sign under M2 in seeds 42 and 43, and the change in |A| ranged from a 51% fall to a 26% rise (Appendix Table A.5).

On the same S02 sets in 2015–2018, ablation reduced |A| by 64%, 67% and 50%, while locking reduced it by 27%, 24% and 9% (Fig. 3). This is descriptive: ablation edits existing CFs, whereas locking generates new ones.

![Fig. 3. A under M0, after ablation and under M2 (locking), on the same people (S02) in each seed, NHANES 2015–2018. Reductions are in |A|. In seed 43, A changes sign after ablation.](fig3.pdf){width=82%}

**Table 3.** Main results, NHANES 2015–2018. Lower bounds (2.5th percentile, participant-level bootstrap, B = 5,000) in parentheses; 95% intervals (two-level bootstrap, B = 100) in brackets.

| Endpoint | Quantity | Seed 42 | Seed 43 | Seed 44 | Conclusion |
|--------|------------|--------------|--------------|--------------|---------|
| E1 (primary) | Access-to-care AUC drop, f_self − f_clin | 0.014 [0.008; 0.019] | — | — | Met |
| E2 (secondary) | Contribution of diagnosis-related features, S0 | 0.043 (0.037); n = 187 | 0.044 (0.037); n = 184 | 0.058 (0.049); n = 197 | Met in all seeds |
| E3 (primary) | A(M0); A(M0) − A(M2); A(M0) + A(M2), S02 | 0.120 (0.097); 0.033 (0.012); 0.208 (0.160); n = 172 | 0.058 (0.028); 0.014 (−0.009); 0.103 (0.042); n = 168 | 0.181 (0.156); 0.016 (−0.004); 0.346 (0.300); n = 175 | Met in seed 42; same direction in 43, 44 |
| E4 (descriptive) | Valid-CF coverage from f_self, M1 vs M0 | 9.0% vs 100%; 18 common | 12.0% vs 99.5%; 24 common | 10.5% vs 99.5%; 21 common | ECD not interpretable (n < 40) |
| E5 (secondary) | G01 share in top 30%, f_self vs f_clin | 27.8% vs 33.3%; p = 0.029 | — | — | Met pooled; not met per cycle |

**Table 4.** Contribution of each diagnosis-related group when reset alone, seed 42.

| Group | Contribution |
|---|---|
| Access to care | 0.020 |
| Other diagnoses | 0.017 |
| Self-rated health | 0.007 |

*Values do not add up to E2 because features can interact. The largest group was self-rated health in seed 43 (0.022) and other diagnoses in seed 44 (0.031).*

## 3.5. Guideline-based rules (E4)

Under M1, DiCE found a valid CF for 9.0–12.0% of people with f_self and 3.0–7.5% with f_clin, compared with 92–100% under M0 and 86–99% under M2 (Fig. 4). In 88–97% of failures DiCE returned no CF. Only 18–24 people had valid f_self CFs in both M0 and M1 (threshold 40), so we draw no conclusion on whether the rules reduce the difference. All valid M1 CFs lowered BMI or waist, often by a large amount: the mean relative BMI reduction was 26–37%, and 74–94% of valid CFs reduced BMI by more than 10%. No valid M1 CF in 2015–2018 changed access to care, although the rules allowed it. Coverage was also low in 2011–2014 (8.5–18.0% with f_self). When BMI and waist reductions were limited to 5% (M3), coverage fell to 0.5% (f_self) and 0% (f_clin).

![Fig. 4. Share of the 200 selected people with at least one valid CF under M0 (baseline), M2 (diagnosis-related group locked) and M1 (guideline-based rules), by CF model and seed (NHANES 2015–2018).](fig4.pdf){width=82%}

## 3.6. Screening (E5) and sensitivity analyses

In the top 30% of scores, f_self selected 27.8% of G01 people and f_clin 33.3% (11 vs 25 discordant people; exact McNemar p = 0.029), but not significantly within each cycle (p = 0.21 and 0.115). Because G01 is partly defined by Y_clin, E5 shows different selections, not clinical benefit.

E1 was met in all sensitivity analyses except the blood-pressure-only label in untreated people, and E3 was met at seed 42 in all three CF sensitivity analyses (Table 5). With DiCE genetic, A fell from 0.242 to 0.169 (about 30%), so the size of A depends on the CF algorithm. Locking physiology instead (M2-phys) increased A from 0.137 to 0.191 on 89 common people, whereas M2 reduced it on the same people (A(M0) − A(M2) = 0.032 [0.003; 0.062]).

**Table 5.** Sensitivity analyses, NHANES 2015–2018, seed 42.

| Change | E1 | E2 | E3 |
|------------------------|------------|------------|------------|
| 130/80 mmHg threshold | 0.019; met | — | — |
| Self-report told ≥2 times | 0.017; met | — | — |
| Reconstructed cholesterol-check variable | 0.016; met | — | — |
| Cycle 2015–2016 / 2017–2018 | 0.011 / 0.015; met | — | — |
| f_self vs blood-pressure-only label, untreated | −0.003; not met | — | — |
| Logistic regression | 0.008; met | 0.085 (n = 191) | Met (n = 88) |
| DiCE genetic | — | 0.105 (n = 192) | Met (n = 177) |
| Y_clin = 1 people only | — | 0.033 (n = 109) | Met (n = 104) |
| All returned CFs | — | — | Not met |

# 4. Discussion

## 4.1. Main findings

First, reliance (E1) and contribution (E2) are different estimands; both pointed in the same direction, but E1 was not reproduced with a blood-pressure-only label.

Second, knowing the contribution of a group does not tell us what happens when the group is locked. In 2015–2018, ablation reduced |A| by 50–67% and locking by only 9–27%; in 2011–2014, the effect of locking was unstable in both size and sign. One possible explanation, which we did not test, is that DiCE replaces the locked features with other changes that still affect the two models differently. The practical lesson is to measure the result of constrained CF generation directly, instead of inferring it from attribution.

Third, following clinical directions does not guarantee that valid CFs can be found. The guideline-based rules left valid CFs for about one in ten selected people, and the remaining CFs often required large BMI reductions. A rule on direction does not limit the size of a change, and adding a size limit (M3) left almost no CFs. Finding no CF does not prove that none exists; coverage depends on the algorithm, search budget and models.

## 4.2. Implications and clinical translation roadmap

Before CFs are shown to clinicians or patients, developers should check whether the label also records access to diagnosis, report valid-CF coverage for each constraint setting, and test constraints directly. Changing a recorded diagnosis or self-rated health in a CF is not an intervention.

PLCA could serve as a pre-deployment audit step, not a clinical tool: its intended users are developers and governance teams validating a CF-based decision support model before release. It is a proof of concept on survey data (self-assessed technology readiness level 3–4 [41]). A proposed path is: (i) rerun PLCA on electronic health record data where a diagnosis code and measured blood pressure exist for the same patients; (ii) have clinicians review the constraint rules and a sample of CFs; (iii) repeat the audit when the model or data change. Whether this improves clinical decisions or patient outcomes has not been studied (Appendix A).

## 4.3. Relation to previous work

Thieu [9] designed rules for how CFs may change and suggested, without a measured comparison label, that self-reported labels may cause implausible CFs. PLCA addresses a different question: it uses two labels for the same people to measure how the label definition affects CF behavior and whether locking features removes this effect. Our results are consistent with that suggestion in another disease, but we did not test the original diabetes taxonomy. Attribution and CFs are known to disagree [24].

## 4.4. Limitations

NHANES is cross-sectional, and the labels differ in timing as well as recording, so not every disagreement reflects access to care. Results cover one condition, one country and one CF framework (DiCE, mainly random search), with one evaluation model per label; other equivalent models could give different results. The two periods test whether the procedure can be repeated with retrained models; they are not an external validation of the classifiers. The CF bootstrap does not include variation from retraining or CF search. E3 was met only in 2015–2018, and E5 only in pooled data. Because the self-report label partly reflects access to diagnosis, models trained on it may be less accurate for groups with less access to care; we did not evaluate performance by sex or race/ethnicity. The guideline-based rules were not reviewed by clinicians and cannot represent sodium, potassium, the DASH diet or stress management. E2 was added during the development phase after E3 failed in a trial analysis; its definition and role were fixed before it was computed on 2015–2018 data. E4 is descriptive.

# 5. Conclusion

In NHANES, models trained on two hypertension labels for the same people relied on different features and responded differently to the same CFs. Diagnosis-related features contributed to this difference in both survey periods, but locking them in new CFs did not reduce it consistently, and guideline-based rules left valid CFs for very few people. Knowing which features contribute to a difference does not show that restricting them will fix it. CFs are not treatment advice.
