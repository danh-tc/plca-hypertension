# Appendix A. Supplementary material

**Table A1.** Scope of the conclusions.

| Supported by the results | Not shown by this study |
|--------------------|--------------------|
| In the main setting, the self-report model relies more on access-to-care features than the examination-based model. | Access to care causes hypertension, or the model is wrong in a causal sense. |
| Class-wise random label noise does not reproduce the reliance of f_self on access to care. | All label-noise mechanisms are ruled out. |
| In generated CFs, diagnosis-related changes contribute to the difference in score drops between the evaluation models. | E2 measures a causal effect or the exact share of shortcut use. |
| Locking the group when new CFs are generated has an unstable effect on \|A\|; in 2015–2018 it reduced the difference only partly. | The result holds for every CF algorithm or data set. |
| Under the guideline-based rules, DiCE found valid CFs for very few people in the tested setting. | No other valid CF exists, or the rules are clinically validated. |
| A paired-label audit can be run on public NHANES data. | CFs are treatment advice or have been reviewed by clinicians. |

**Table A2.** Components of A and I on the same people (S02), NHANES 2015–2018.

| Seed | Mode | n | ECD_self | ECD_clin | A | I |
|---|---|---|---|---|---|---|
| 42 | M0 | 172 | 0.089 | −0.031 | 0.120 | 0.058 |
| 42 | M2 | 172 | 0.070 | −0.018 | 0.087 | 0.052 |
| 43 | M0 | 168 | 0.073 | 0.015 | 0.058 | 0.088 |
| 43 | M2 | 168 | 0.079 | 0.035 | 0.044 | 0.114 |
| 44 | M0 | 175 | 0.125 | −0.055 | 0.181 | 0.070 |
| 44 | M2 | 175 | 0.154 | −0.010 | 0.165 | 0.144 |

*I = ECD_self + ECD_clin; I/2 is the mean difference between the score drop on the same-label and the cross-label evaluation model, with both CF sources weighted equally. I is descriptive and has no interval. Locking reduced A but did not consistently reduce I. Source: `results/confirmation/cf_primary/C6_all_seeds.csv`.*

**Table A3.** Mean score drop per CF, by CF model and mode, seed 42.

| CF model | Mode | Valid CFs | Drop on g_self | Drop on g_clin | Same-label − cross-label |
|------|------|------|-------|-------|--------|
| f_self | M0 | 775 | 0.241 | 0.152 | 0.089 |
| f_self | M1 | 80 | 0.178 | 0.164 | 0.014 |
| f_self | M2 | 927 | 0.209 | 0.141 | 0.068 |
| f_clin | M0 | 781 | 0.261 | 0.225 | −0.036 |
| f_clin | M1 | 27 | 0.126 | 0.256 | 0.130 |
| f_clin | M2 | 851 | 0.221 | 0.205 | −0.016 |

*Averaged directly over valid CFs, not per person first, and not restricted to S02; not a replacement for E3. M1 rows are based on very few CFs. Source: `results/confirmation/cf_primary/seed42/C7_transfer_by_channel.csv`.*

**Table A4.** Guideline-based rules (mode M1): allowed changes and basis.

| Feature (NHANES) | Allowed change | Code | Basis |
|--------------|----------------|----|-------------|
| Insurance (HIQ011), usual place of care (HUQ030) | Only no → yes | D/P | Team-based care and removing access barriers [34] |
| Current smoking (SMQ020/SMQ040) | Only yes → no | G/P | Avoid tobacco [39] |
| Drinks per drinking day (ALQ130) | If x > 1, down within [1, x]; otherwise fixed | G/S | [34], recommendation 6 (Class 1/A); the floor of one follows the meaning of ALQ130 |
| Moderate (PAQ665) and vigorous (PAQ650) recreational activity | Only no → yes | G/P | [34], recommendation 7 (Class 1/A); [40] |
| BMI (BMXBMI) | If x > T, down within [T, x]; otherwise fixed. T = 23 for non-Hispanic Asian (RIDRETH3 = 6), 25 otherwise | G/P | [34], recommendation 1 (Class 1/A), and BMI categories |
| Waist (BMXWAIST) | If x > T, down within [T, x]; otherwise fixed. T = 102 cm (men), 88 cm (women) | P | Abdominal obesity thresholds [35,36] |
| Age, sex, race/ethnicity | Fixed | I | Immutable |
| All other features (education, income, visits, diagnoses, cholesterol, HbA1c, self-rated health) | Fixed | S/D | Not a direct change target, or no general directional rule |

*Codes describe where a rule comes from, not the level of clinical evidence: G, guideline recommendation; P, recommendation or threshold translated to an NHANES variable; S, limit from the meaning of the data; D, design decision; I, immutable. All ranges are also limited to the training-data range, and imputed values are fixed in M1 and M3. M3 adds a maximum 5% reduction in BMI and waist (lower bound max(T, 0.95x)); 5% for BMI follows the minimum weight-loss target in [34], and 5% for waist is a design assumption. Limits: the BMI thresholds are category boundaries, not treatment targets; RIDRETH3 is a survey category; the US waist thresholds are applied to all groups; the ALQ130 rule does not model stopping alcohol; the activity variables are yes/no and do not show that recommended amounts are reached; BMI and waist change independently; family history, sodium, potassium, the DASH diet and stress management are not in the data. The rules have not been reviewed by clinicians.*

**Table A5.** Main results in both NHANES periods (same code, same run).

| Endpoint | 2011–2014 (n = 10,311) | 2015–2018 (n = 10,151) |
|------------|------------|------------|
| E1: access-to-care AUC drop, f_self − f_clin | 0.015 [0.009; 0.022]; met | 0.014 [0.008; 0.019]; met |
| E2 (lower bound), seeds 42/43/44 | 0.042 (0.035) / 0.036 (0.031) / 0.035 (0.027); met | 0.043 (0.037) / 0.044 (0.037) / 0.058 (0.049); met |
| E3, seed 42: A(M0); A(M2); lower bound of A(M0) + A(M2) | 0.040; −0.032; −0.028; not met | 0.120; 0.087; 0.160; met |
| E3, seeds 43 and 44: A(M2) | −0.037; 0.045 | 0.044; 0.165 |
| E4: valid-CF coverage under M1, f_self (seeds 42/43/44) | 18.0 / 8.5 / 12.5%; common n 36 / 17 / 25 | 9.0 / 12.0 / 10.5%; common n 18 / 24 / 21 |
| E4: ECD_self(M0) − ECD_self(M1) | Not interpretable (n < 40) | Not interpretable (n < 40); raw values 0.025 / 0.029 / 0.008 |

*The 2011–2014 data were used to develop the procedure, including E2, so results there are not an independent evaluation. E2 and E3 use different people (S0 and S02), so their stability can only be compared descriptively. Sources: `results/discovery` and `results/confirmation`.*

**Table A6.** Full characteristics of the 2015–2018 sample by label pair (140/90 mmHg).

| Characteristic | All | G00 | G01 | G10 | G11 |
|------------------|--------|-----------|-----------|-----------|-----------|
| People (unweighted) | 10,151 | 5,533 | 785 | 562 | 3,271 |
| Age, years, mean (SD) | 48.4 (17.2) | 42.1 (15.6) | 56.4 (15.3) | 44.5 (15.5) | 61.2 (13.0) |
| Age 20–39, % | 35.2 | 49.0 | 16.6 | 46.0 | 6.9 |
| Age 40–59, % | 35.8 | 35.4 | 40.5 | 34.3 | 35.8 |
| Age ≥60, % | 29.0 | 15.6 | 42.9 | 19.7 | 57.3 |
| Women, % | 51.1 | 52.3 | 45.3 | 41.7 | 51.9 |
| Mexican American, % | 8.7 | 10.2 | 9.1 | 8.8 | 5.3 |
| Other Hispanic, % | 6.5 | 7.2 | 6.0 | 6.8 | 5.1 |
| Non-Hispanic White, % | 63.7 | 62.7 | 63.7 | 63.8 | 65.8 |
| Non-Hispanic Black, % | 11.3 | 9.7 | 12.1 | 10.9 | 14.7 |
| Non-Hispanic Asian, % | 5.7 | 6.3 | 5.7 | 3.8 | 4.7 |
| Other or multiracial, % | 4.2 | 4.0 | 3.4 | 6.0 | 4.5 |
| Less than high school, % | 12.5 | 11.5 | 13.6 | 12.2 | 14.6 |
| High school or GED, % | 24.2 | 22.6 | 28.0 | 24.3 | 26.8 |
| Some college, % | 31.7 | 30.6 | 28.1 | 35.1 | 34.3 |
| College graduate or above, % | 31.6 | 35.4 | 30.3 | 28.4 | 24.3 |
| Income-to-poverty ratio < 1.3, % | 20.3 | 19.8 | 20.5 | 25.5 | 20.1 |
| Insured, % | 86.5 | 84.0 [81.2; 86.8] | 88.8 [85.2; 92.5] | 82.4 [77.2; 87.6] | 92.5 [90.4; 94.5] |
| Usual place of care, % | 82.6 | 78.0 [75.8; 80.1] | 81.8 [77.9; 85.7] | 78.7 [72.5; 84.8] | 93.9 [92.6; 95.2] |
| Visit in past year, % | 83.9 | 79.1 [77.5; 80.7] | 78.8 [74.5; 83.0] | 82.2 [78.4; 86.0] | 96.2 [95.3; 97.0] |
| BMI, kg/m², mean (SD) | 29.6 (7.1) | 28.3 (6.7) | 30.3 (7.3) | 30.9 (7.4) | 32.0 (7.2) |
| Systolic BP, mmHg, mean (SD) | 123.7 (17.7) | 115.8 (10.8) | 148.2 (13.1) | 122.0 (9.7) | 135.3 (20.0) |
| Diastolic BP, mmHg, mean (SD) | 71.7 (11.4) | 69.7 (9.1) | 82.3 (13.1) | 72.5 (10.0) | 73.2 (13.7) |
| On BP medication, % | 24.1 | 0 | 0 | 0 | 89.2 |

*Survey-weighted (WTMEC2YR divided by the number of cycles); 95% confidence intervals for access-to-care rows by Taylor linearisation with the survey design (30 strata, 60 primary sampling units). One G00 person lacks usual-place and visit data. Source: `results/confirmation/T1c_demographics_confirmation.csv` and `results/confirmation/design_se`.*

**Detailed formulas.** Let S be the analysis set, $K_{i,s}$ the number of valid CFs from model s for person i, and $x'_{ij}$ the j-th CF. Then

$$\mathrm{ECD}_s = \frac{1}{|S|}\sum_{i \in S}\frac{1}{K_{i,s}}\sum_{j=1}^{K_{i,s}}\left[\Delta_s(x'_{ij}) - \Delta_{\bar s}(x'_{ij})\right],$$

where $\bar s$ is the other label. For E2,

$$C_m = p_m(x'_{abl}) - p_m(x') = \Delta_m(x') - \Delta_m(x'_{abl}), \qquad D_i^{(s)} = \frac{1}{K_{i,s}}\sum_{j=1}^{K_{i,s}}\left(C_{self} - C_{clin}\right),$$

$$\mathrm{E2} = \frac{1}{2|S_0|}\sum_{i \in S_0}\left(D_i^{(self)} + D_i^{(clin)}\right).$$

Hence $A(\mathrm{M0}) - A_{abl} = 2\,\mathrm{E2}$ when both sides use the same people, CFs and averaging; this does not hold directly for E2 on S0 compared with A(M0) on S02.

**Naming in the code.** E2 is `E6`, S0 is `S_M0`, S02 is `S_star`, and the guideline-based rules are `T-HTN` (`docs/taxonomy_THTN.md`).
