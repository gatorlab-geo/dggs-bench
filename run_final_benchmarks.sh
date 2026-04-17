#!/bin/bash
# ==============================================================================
# ACM SIGSPATIAL 2026 - FINAL EXPERIMENTAL BENCHMARK SUITE
# Orchestrates 3 Full Iterations of Computational & Relational Throughputs
# ==============================================================================

# Halt on any extreme internal failure
set -e

# Target geometry limits (3 Runs = Seed 42, 43, 44)
SEEDS=(42 43 44)
GRIDS="h3,s2,rhealpix,xyz"
SCALES=("macro" "macro-10m" "macro-europe" "micro")

echo "=============================================================================="
echo " INITIALIZING FINAL BENCHMARK SUITE (3 ITERATIONS)"
echo " DO NOT TOUCH MOUSE OR KEYBOARD"
echo "=============================================================================="

for iteration in 1 2 3; do
    SEED=${SEEDS[$((iteration-1))]}
    echo ""
    echo "=============================================================================="
    echo " STARTING ITERATION $iteration/3 (SEED: $SEED)"
    echo "=============================================================================="
    
    # --------------------------------------------------------------------------
    # EXPERIMENT 3: COMPUTATIONAL THROUGHPUT
    # --------------------------------------------------------------------------
    echo "--> [1/5] Running Computational Throughput..."
    dggs-bench run computational-throughput \
        --grids $GRIDS \
        --samples 10000000 \
        --seed $SEED \
        --output-dir data/final_results/iter_${iteration}/

    # --------------------------------------------------------------------------
    # EXPERIMENT 4: RELATIONAL THROUGHPUT (4 SCALES)
    # --------------------------------------------------------------------------
    scale_count=2
    for SCALE in "${SCALES[@]}"; do
        echo "--> [$scale_count/5] Running Relational Throughput [SCALE: $SCALE]..."
        dggs-bench run relational-throughput \
            --grids $GRIDS \
            --scale $SCALE \
            --point-distribution real \
            --seed $SEED \
            --output-dir data/final_results/iter_${iteration}/ \
            --max-covering-sec 1800
        scale_count=$((scale_count + 1))
    done
done

echo ""
echo "=============================================================================="
echo " SCIENTIFIC BENCHMARK SUITE COMPLETELY FINISHED"
echo " You may now re-enable Wi-Fi and review the output in data/final_results/"
echo "=============================================================================="
