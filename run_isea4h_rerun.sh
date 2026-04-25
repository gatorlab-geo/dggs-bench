#!/bin/bash
# ==============================================================================
# ISEA4H COVERING FIX — RE-RUN (Experiment 4 Only)
# 
# After applying the centroid-inside-polygon post-filter to get_covering(),
# re-run relational throughput for ISEA4H only across all 4 scales × 3 seeds.
#
# The other 5 grids (H3, S2, rHEALPix, XYZ, Geohash) are UNCHANGED — their
# results in final_results_3/ remain valid.
#
# PREREQUISITES:
#   1. git pull  (to get the isea4h_grid.py fix)
#   2. conda activate dggs-bench-py312
#   3. Verify bridge: dggs-bench list | grep isea4h
#
# OUTPUT: data/tsas_v1/final_results_4/iter_{1,2,3}/
# ESTIMATED RUNTIME: ~4-8 hours total
# ==============================================================================

set -e

SEEDS=(42 43 44)
GRIDS="isea4h"
SCALES=("macro" "macro-10m" "macro-europe" "micro")
OUT_BASE="data/tsas_v1/final_results_4"

echo "=============================================================================="
echo " ISEA4H COVERING FIX — RE-RUN (Relational Throughput Only)"
echo " 3 ITERATIONS × 4 SCALES = 12 runs"
echo " DO NOT TOUCH MOUSE OR KEYBOARD"
echo "=============================================================================="

echo ""
echo "[Pre-flight] Verifying ISEA4H availability..."
dggs-bench list | grep isea4h
echo "[Pre-flight] OK"
echo ""

for iteration in 1 2 3; do
    SEED=${SEEDS[$((iteration-1))]}
    OUTDIR="${OUT_BASE}/iter_${iteration}"
    mkdir -p "$OUTDIR"

    echo ""
    echo "=============================================================================="
    echo " ITERATION $iteration/3  (SEED: $SEED)  →  $OUTDIR"
    echo "=============================================================================="

    scale_count=1
    for SCALE in "${SCALES[@]}"; do
        echo ""
        echo "--> [$scale_count/4] Relational Throughput [SCALE: $SCALE]..."
        dggs-bench run relational-throughput \
            --grids $GRIDS \
            --scale $SCALE \
            --point-distribution real \
            --seed $SEED \
            --output-dir "$OUTDIR" \
            --max-covering-sec 1800
        scale_count=$((scale_count + 1))
    done
done

echo ""
echo "=============================================================================="
echo " ISEA4H RE-RUN COMPLETE"
echo ""
echo " Results: ${OUT_BASE}/iter_{1,2,3}/"
echo " Merge these ISEA4H rows with final_results_3 for the analysis notebook."
echo "=============================================================================="
