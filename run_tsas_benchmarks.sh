#!/bin/bash
# ==============================================================================
# ACM TSAS 2026 - BENCHMARK SUITE FOR NEW GRIDS (ISEA4H + Geohash)
# 3 Iterations (Seeds 42/43/44) for statistical averaging
# ==============================================================================
# 
# PREREQUISITES:
#   1. conda activate dggs-bench-py312
#   2. Rebuild ISEA4H bridge on this machine:
#      bash src/dggs_benchmark/grids/dglib_bridge/build_isea4h.sh
#   3. Verify: dggs-bench list | grep -E "isea4h|geohash"
#
# OUTPUT: data/tsas_v1/iter_{1,2,3}/
#
# ESTIMATED RUNTIME: ~3-4 hours total (ISEA4H is slower due to dglib FFI)
# ==============================================================================

set -e

SEEDS=(42 43 44)
GRIDS="h3,s2,rhealpix,isea4h,geohash,xyz"
SCALES=("macro" "macro-10m" "macro-europe" "micro")
OUT_BASE="data/tsas_v1"

echo "=============================================================================="
echo " ACM TSAS 2026 — FINAL BENCHMARK (ISEA4H + Geohash)"
echo " 3 ITERATIONS × (1 COMP + 4 RELATIONAL SCALES)"
echo " DO NOT TOUCH MOUSE OR KEYBOARD"
echo "=============================================================================="

# --- Sanity check: can we import the grids? ---
echo ""
echo "[Pre-flight] Verifying grid availability..."
dggs-bench list | grep -E "isea4h|geohash"
echo "[Pre-flight] OK — both grids registered."
echo ""

for iteration in 1 2 3; do
    SEED=${SEEDS[$((iteration-1))]}
    OUTDIR="${OUT_BASE}/iter_${iteration}"
    mkdir -p "$OUTDIR"

    echo ""
    echo "=============================================================================="
    echo " ITERATION $iteration/3  (SEED: $SEED)  →  $OUTDIR"
    echo "=============================================================================="

    # --------------------------------------------------------------------------
    # EXPERIMENT 3: COMPUTATIONAL THROUGHPUT (1M points)
    # Measures: encode, decode, k-ring, parent latency + memory (RSS/peak)
    # --------------------------------------------------------------------------
    echo ""
    echo "--> [1/5] Computational Throughput (1M points)..."
    dggs-bench run computational-throughput \
        --grids $GRIDS \
        --samples 10000000 \
        --seed $SEED \
        --output-dir "$OUTDIR" \
        --output-format csv

    # --------------------------------------------------------------------------
    # EXPERIMENT 4: RELATIONAL THROUGHPUT (4 scales)
    # Measures: vector_join_sec (ST_Intersects baseline), ingestion_sec,
    #           covering_sec, join_sec, accuracy_pct per resolution sweep
    # --------------------------------------------------------------------------
    scale_count=2
    for SCALE in "${SCALES[@]}"; do
        echo ""
        echo "--> [$scale_count/5] Relational Throughput [SCALE: $SCALE]..."
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
echo " TSAS BENCHMARK SUITE COMPLETE"
echo ""
echo " Results: ${OUT_BASE}/iter_{1,2,3}/"
echo ""
echo " Output columns (Exp 3 — computational_throughput_*.csv):"
echo "   grid_name, encode_sec, decode_sec, kring_sec, parent_sec,"
echo "   throughput_p_sec, success_rate,"
echo "   rss_before_mb, rss_after_encode_mb, rss_after_all_mb, rss_peak_mb"
echo ""
echo " Output columns (Exp 4 — relational_throughput_*.csv):"
echo "   grid_name, resolution, ingestion_sec, covering_sec, join_sec,"
echo "   vector_join_sec, count, vector_count, accuracy_pct"
echo "=============================================================================="
