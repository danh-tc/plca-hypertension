# plca-hypertension

Paired-Label Counterfactual Audit (PLCA): does the *source* of a hypertension label
(self-reported diagnosis vs examination-informed phenotype) change what ML models rely on and
what counterfactual explanations (CFs) recommend? NHANES 2011–2014 (discovery) and 2015–2018
(confirmation).

Builds on Thieu (2026), *Knowledge-guided counterfactual explanations for diabetes risk decision
support*, Int J Med Inform.

## Run

```bash
git clone https://github.com/danh-tc/plca-hypertension.git && cd plca-hypertension
pip install -r requirements.txt pytest
python src/download_nhanes.py                       # NHANES XPT files -> data/raw/
bash scripts/run_all.sh data/raw 2>&1 | tee outputs_all.log
python scripts/paper_numbers.py results/confirmation
python scripts/make_figures.py results/confirmation paper/vi
```

`run_all.sh` runs the unit tests, the discovery analysis (2011–2014) and the confirmation analysis
(2015–2018), and copies summary CSVs to `results/discovery/` and `results/confirmation/`. The commit,
environment (`environment.json`, `pip_freeze.txt`) and SHA-256 checksums of the raw files are written to
`results/`. Raw data and per-CF files are not committed.

## Labels

| Label | Definition |
|---|---|
| `Y_self` | BPQ020 = 1 (ever told high BP) |
| `Y_self2` | told ≥ 2 times (BPQ030); unknown → excluded |
| `Y_clin140` | SBP ≥ 140 or DBP ≥ 90 or on BP medication (primary) |
| `Y_clin130` | 130/80 (sensitivity) |

Medication status is tri-state (yes / no incl. structural skips / unknown → excluded).
`Y_clin` is an *examination-informed phenotype*, not ground truth.

## Endpoints

| | Question | Role |
|---|---|---|
| E1 | Do the two models rely differently on access-to-care features? | primary |
| E2 | Contribution of diagnosis-related features in generated CFs (paired ablation); named `E6` in code and result files | secondary |
| E3 | Does locking diagnosis-related features (M2) reduce the response gap? | primary |
| E4 | Can valid CFs still be found under the guideline-based rules (M1, code name T-HTN)? Coverage M1 vs M0; ECD_self(M0) − ECD_self(M1) when ≥ 40 common patients | descriptive |
| E5 | Screening consequence (top-30% McNemar) | secondary |

Naming: `S0` (paper) = `S_M0` (code), `S02` (paper) = `S_star` (code); the paper calls T-HTN the "guideline-based rules" (mode M1).

## Constraint modes

- `M0_global`: everything mutable except age, sex, race/ethnicity.
- `M1_taxonomy`: T-HTN, hypertension guideline-informed directional taxonomy (`docs/taxonomy_THTN.md`).
- `M2_locked`: M0 with access, other diagnoses and self-rated health locked.
- `M2_phys`: M0 with physiology locked (alternative restriction).
- `M3_evidence`: M1 with BMI and waist reduced by at most 5%.

## Key design choices

- `chol_checked` (BPQ060) dropped by default: structural skip after BPQ080 = 1. Sensitivity:
  raw (`--drop-features`) and reconstructed (`--drop-features --chol-reconstruct`).
- Model level: placebo transition rates from the training split; leave-group-out removes a group from
  the training set only (common test set) with a random-drop control of equal size.
- CF level: per-query generation status (`success`, `no_cf_found`, `exception`,
  `no_actionable_features`); rounding only on varied features; post-processing constraint check;
  **valid recourse** = constraint-valid and flips the source model; ECD is patient-level with
  symmetric bootstrap-trained evaluators; coverage at threshold 0.5 and matched screening budgets.

## License

Code: MIT (see `LICENSE`). NHANES data: CDC/NCHS terms.
