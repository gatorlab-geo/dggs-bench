#!/usr/bin/env bash
# ISEA4H Relational Throughput Re-run (post raster-floor fix b31223b)
# Run inside tmux on the other machine after: git pull
set -euo pipefail

OUT="data/tsas_v1/final_results_5"

for SCALE in macro macro-10m macro-europe micro; do
    echo "===== ISEA4H | ${SCALE} | $(date) ====="
    dggs-bench run relational-throughput \
        --grids isea4h \
        --scale "$SCALE" \
        --output-dir "$OUT"
done

echo "===== ALL DONE | $(date) ====="
