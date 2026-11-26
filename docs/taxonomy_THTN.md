# T-HTN — Hypertension guideline-informed directional taxonomy

Implemented in `src/phase1_cf_audit.py` (`THTN`, `thtn_range`, modes `M1_taxonomy` and `M3_evidence`);
tested in `tests/test_taxonomy.py`.

**Status.** Author-specified from published guidelines; not reviewed by a clinical expert panel.

Rule provenance codes: **G** direct guideline recommendation; **P** recommendation operationalised on an
NHANES proxy; **S** data-semantics constraint; **D** study design assumption; **I** immutable.

## A. Features allowed to change (8)

| # | Feature (NHANES) | Rule | Code | Basis |
|---|---|---|---|---|
| 1 | Health insurance (HIQ011) | up only, 0 → 1 | D/P | AHA/ACC 2025: team-based care addressing structural barriers (take-home message 3; team-based care Class 1/A) |
| 2 | Routine place of care (HUQ030) | up only, 0 → 1 | D/P | as above |
| 3 | Current smoking (SMQ020/SMQ040) | down only, 1 → 0 | G/P | ACC/AHA 2026 dyslipidemia guideline (avoid tobacco). Not a lifestyle recommendation in AHA/ACC 2025 §5.1 |
| 4 | Drinks per drinking day (ALQ130) | x > 1: [1, x]; x ≤ 1: frozen | G/S | AHA/ACC 2025 §5.1 rec. 6 (Class 1/A). Floor 1 because ALQ130 counts drinks on drinking days; the value 0 in the PLCA feature comes from preprocessing and is not interpreted as abstinence |
| 5 | Moderate recreational activity (PAQ665) | up only, 0 → 1 | G/P | AHA/ACC 2025 §5.1 rec. 7 (Class 1/A); WHO 2020 |
| 6 | Vigorous recreational activity (PAQ650) | up only, 0 → 1 | G/P | as above. Binary indicator; 0 → 1 does not imply meeting the recommended dose |
| 7 | BMI (BMXBMI) | x > T: [T, x]; else frozen. T = 23 for Non-Hispanic Asian (RIDRETH3 = 6), 25 otherwise | G/P | AHA/ACC 2025 §5.1 rec. 1 (Class 1/A) and its supportive text (overweight BMI 25.0–29.9 non-Asian, 23.0–27.4 Asian heritage). Using the class boundary as the CF lower bound is an operational choice. RIDRETH3 is a survey category, not ancestry |
| 8 | Waist circumference (BMXWAIST) | x > T: [T, x]; else frozen. T = 102 cm men, 88 cm women | P | Grundy et al. 2005; Alberti et al. 2009 (US cut-offs). Identifies abdominal obesity; not a treatment target |

## B. Frozen

Age, sex, race/ethnicity (I); education, income-to-poverty ratio (D); visits in past year (D/S; HUQ051 is a
banded code, not a count); diagnosed diabetes, diagnosed high cholesterol (S; ever-told history); total
cholesterol, HbA1c (D; no individual target derivable from the data); self-rated health (S/D; not an
intervention target).

**Imputed values:** any feature missing before median imputation is frozen for that query, in M1 and M3 only
(M0 and M2 unaffected). E4 therefore reflects the whole taxonomy, including the missing-value rule, not
directionality alone.

## C. M3 — guideline-informed magnitude-bounded scenario

Inherits M1. BMI: [max(T, 0.95x), x]; waist: [max(T, 0.95x), x]. The 5% BMI cap uses the guideline's minimum
weight-loss goal as a scenario; the 5% waist cap is a study assumption. Not described as clinically feasible
bounds.

## D. Notes

- BMI thresholds follow population-specific guideline classes, whereas the waist cut-off is the single US
  cut-off; the two come from different sources and purposes and are operational bounds, not treatment goals.
- All ranges are additionally clipped to the training-set range; rounding is applied after generation and
  the post-processing constraint check re-verifies each CF against these ranges.
- Not represented (absent from the feature set): sodium reduction, potassium, DASH eating pattern, stress
  management (AHA/ACC 2025 §5.1 recs. 2–5, 8–9).

## E. Edge cases (tested)

| Case | M1 | M3 |
|---|---|---|
| Asian, BMI 22 / 23 | frozen | frozen |
| Asian, BMI 24 | [23, 24] | [23, 24] |
| Asian, BMI 30 | [23, 30] | [28.5, 30] |
| Non-Asian, BMI 24 | frozen | frozen |
| Non-Asian, BMI 30 | [25, 30] | [28.5, 30] |
| Man, waist 100 | frozen | frozen |
| Man, waist 110 | [102, 110] | [104.5, 110] |
| Woman, waist 90 | [88, 90] | [88, 90] |
| BMI or waist imputed | frozen | frozen |

## F. References

- Jones DW et al. 2025 AHA/ACC/AANP/AAPA/ABC/ACCP/ACPM/AGS/AMA/ASPC/NMA/PCNA/SGIM Guideline for the
  Prevention, Detection, Evaluation and Management of High Blood Pressure in Adults. Circulation
  2025;152:e114–e218. doi:10.1161/CIR.0000000000001356
- Blumenthal RS et al. 2026 ACC/AHA/AACVPR/ABC/ACPM/ADA/AGS/APhA/ASPC/NLA/PCNA Guideline on the Management of
  Dyslipidemia. J Am Coll Cardiol, doi:10.1016/j.jacc.2025.11.016; Circulation, doi:10.1161/CIR.0000000000001423
- Grundy SM et al. Diagnosis and management of the metabolic syndrome: an AHA/NHLBI scientific statement.
  Circulation 2005. doi:10.1161/CIRCULATIONAHA.105.169404
- Alberti KGMM et al. Harmonizing the metabolic syndrome. Circulation 2009;120:1640–1645
- Bull FC et al. WHO 2020 guidelines on physical activity and sedentary behaviour. Br J Sports Med
  2020;54:1451–1462. doi:10.1136/bjsports-2020-102955
- Thieu V. Int J Med Inform 2026;219:106555
