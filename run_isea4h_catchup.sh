#!/usr/bin/env bash
# ISEA4H Relational Throughput Re-run (post raster-floor fix b31223b)
# 3 iterations (seeds 42/43/44) matching the original final_results_3 methodology
# Run inside tmux on the other machine after: git pull
set -euo pipefail

SEEDS=(42 43 44)
SCALES=("macro" "macro-10m" "macro-europe" "micro")
OUT_BASE="data/tsas_v1/final_results_5"

echo "======================================================================"
echo " ISEA4H CATCHUP — POST RASTER-FLOOR FIX"
echo " 3 ITERATIONS × 4 SCALES"
echo "======================================================================"

for iteration in 1 2 3; do
    SEED=${SEEDS[$((iteration-1))]}
    OUTDIR="${OUT_BASE}/iter_${iteration}"
    mkdir -p "$OUTDIR"

    echo ""
    echo "======================================================================"
    echo " ITERATION ${iteration}/3  (SEED: ${SEED})  →  ${OUTDIR}"
    echo "======================================================================"

    for SCALE in "${SCALES[@]}"; do
        echo ""
        echo "----> ISEA4H | ${SCALE} | $(date)"
        dggs-bench run relational-throughput \
            --grids isea4h \
            --scale "$SCALE" \
            --point-distribution real \
            --seed "$SEED" \
            --output-dir "$OUTDIR" \
            --max-covering-sec 1800
    done
done

echo ""
echo "======================================================================"
echo " ISEA4H CATCHUP COMPLETE | $(date)"
echo " Results: ${OUT_BASE}/iter_{1,2,3}/"
echo "======================================================================"
