#!/bin/bash
# ==============================================================================
# XYZ Tile Catch-Up — Relational Throughput Only
# Runs only the XYZ grid to supplement final_results_2
# ==============================================================================
set -e

SEEDS=(42 43 44)
SCALES=("macro" "macro-10m" "macro-europe" "micro")

echo "============================================="
echo " XYZ TILE CATCH-UP (3 iterations × 4 scales)"
echo "============================================="

for iteration in 1 2 3; do
    SEED=${SEEDS[$((iteration-1))]}
    echo ""
    echo "--- ITERATION $iteration/3 (SEED: $SEED) ---"

    for SCALE in "${SCALES[@]}"; do
        echo "  -> Relational Throughput [SCALE: $SCALE]..."
        dggs-bench run relational-throughput \
            --grids xyz \
            --scale $SCALE \
            --point-distribution real \
            --seed $SEED \
            --output-dir data/final_results_2/iter_${iteration}/ \
            --max-covering-sec 1800
    done
done

echo ""
echo "============================================="
echo " XYZ CATCH-UP COMPLETE"
echo "============================================="
