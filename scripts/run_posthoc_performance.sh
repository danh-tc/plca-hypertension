#!/usr/bin/env bash
# POST HOC reporting analysis (performance, calibration, data characteristics). Not an endpoint.
# Reads the frozen results/ folders only to check the refit; writes to outputs_posthoc/ only.
#   bash scripts/run_posthoc_performance.sh data/raw 2>&1 | tee outputs_posthoc_performance.log
set -euo pipefail
DATA=${1:-data/raw}
OUT=outputs_posthoc/performance
mkdir -p "$OUT"
git rev-parse HEAD > "$OUT/commit.txt" 2>/dev/null || echo unknown > "$OUT/commit.txt"
python -m pytest tests/test_posthoc_performance.py -q
for P in discovery confirmation; do
  python src/posthoc_performance.py --data-dir "$DATA" --period "$P" \
    --ref-dir "results/$P" --out-dir "$OUT/$P" --boot 1000
done
echo "Done: $OUT"
