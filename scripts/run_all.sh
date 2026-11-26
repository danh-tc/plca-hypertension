#!/usr/bin/env bash
# Full PLCA pipeline: discovery (2011-2014) and confirmation (2015-2018).
# Run from the repo root on one machine:
#   bash scripts/run_all.sh data/raw 2>&1 | tee outputs_all.log
# Every number in the manuscript is taken from results/discovery and results/confirmation.
set -euo pipefail
DATA=${1:-data/raw}
OUT=outputs_all
mkdir -p "$OUT"
git rev-parse HEAD > "$OUT/commit.txt" 2>/dev/null || echo unknown > "$OUT/commit.txt"
python scripts/record_environment.py "$DATA" "$OUT/environment.json"
pip freeze > "$OUT/pip_freeze.txt"

python -m pytest tests -q

# ---------------- discovery (2011-2014) ----------------
D=$OUT/discovery
python src/run_checks.py --data-dir "$DATA" --out-root "$D/model_level" --boot 100 --cycles discovery --only baseline
python src/run_phase1_seeds.py --data-dir "$DATA" --out-root "$D/cf_primary" --seeds 42 43 44 \
  --n-queries 200 -- --cycles discovery --modes M0_global M1_taxonomy M2_locked

# ---------------- confirmation (2015-2018) ----------------
C=$OUT/confirmation
python src/table1_demographics.py --data-dir "$DATA" --cycles confirmation --out-dir "$C/table1"
python src/design_se.py --data-dir "$DATA" --out-dir "$C/design_se" --cycles confirmation

# E1 (primary) + model-level sensitivity analyses: two-level bootstrap B = 100, seed 42
python src/run_checks.py --data-dir "$DATA" --out-root "$C/model_level" --boot 100 --cycles confirmation \
  --only baseline chol_reconstructed self2 clin130 bp140_unmedicated logreg \
         exclude_G01_train randdrop_G01_train exclude_G10_train randdrop_G10_train
# per-cycle sensitivity: E1 (model level) and E5 (coverage only)
for CY in I J; do
  python src/run_checks.py --data-dir "$DATA" --out-root "$C/model_level_cycle_$CY" --boot 100 --cycles $CY --only baseline
  python src/phase1_cf_audit.py --data-dir "$DATA" --out-dir "$C/coverage_cycle_$CY" --cycles $CY --seed 42 --coverage-only
done
python src/coef_signs.py --data-dir "$DATA" --out-dir "$C/coef_signs" --cycles confirmation --boot 200

# E3 (primary), E4 (descriptive), E5, E6: XGBoost, 200 queries, seeds 42 (primary), 43, 44
python src/run_phase1_seeds.py --data-dir "$DATA" --out-root "$C/cf_primary" --seeds 42 43 44 \
  --n-queries 200 -- --cycles confirmation --modes M0_global M1_taxonomy M2_locked

# CF sensitivity analyses (seed 42)
python src/phase1_cf_audit.py --data-dir "$DATA" --out-dir "$C/cf_M2phys" --cycles confirmation --seed 42 \
  --n-queries 200 --modes M0_global M2_locked M2_phys
python src/phase1_cf_audit.py --data-dir "$DATA" --out-dir "$C/cf_logreg" --cycles confirmation --seed 42 \
  --n-queries 200 --model logreg --modes M0_global M2_locked
python src/phase1_cf_audit.py --data-dir "$DATA" --out-dir "$C/cf_clinpos" --cycles confirmation --seed 42 \
  --n-queries 200 --query-pool clinpos_unmedicated --modes M0_global M1_taxonomy M2_locked
python src/phase1_cf_audit.py --data-dir "$DATA" --out-dir "$C/cf_M3" --cycles confirmation --seed 42 \
  --n-queries 200 --modes M0_global M3_evidence
python src/phase1_cf_audit.py --data-dir "$DATA" --out-dir "$C/cf_genetic" --cycles confirmation --seed 42 \
  --n-queries 200 --dice-method genetic --modes M0_global M2_locked

python src/collect_results.py --outputs "$D" --tag discovery
python src/collect_results.py --outputs "$C" --tag confirmation
cp "$C/table1/"*.csv results/confirmation/ 2>/dev/null || true
cp "$OUT/commit.txt" "$OUT/environment.json" "$OUT/pip_freeze.txt" results/
echo "done; results in results/discovery and results/confirmation"
