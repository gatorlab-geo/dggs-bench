import argparse
import os
import sys

# Aggressive fix for PyProj Conda disconnect (Issue #CRSError)
if "CONDA_PREFIX" in os.environ:
    _proj_path = os.path.join(os.environ["CONDA_PREFIX"], "share", "proj")
    if os.path.exists(_proj_path):
        os.environ["PROJ_DATA"] = _proj_path
        os.environ["PROJ_LIB"] = _proj_path
        os.environ["PROJ_DEBUG"] = "3" # Optional: provides more logs to user if it fails still.
        try:
            import pyproj
            pyproj.datadir.set_data_dir(_proj_path)
            # Suppress the UserWarning since we just manually enforced the path
            import warnings
            warnings.filterwarnings("ignore", "pyproj unable to set PROJ database path")
        except Exception:
            pass

import datetime
import json
import math
import random
import pandas as pd
import geopandas as gpd

# ---------------------------------------------------------------------------
# Grid Registry

# ---------------------------------------------------------------------------
# Maps short CLI alias → (factory_callable, resolution)
# Using callables (lambdas) instead of pre-built instances so imports are
# deferred — only the selected grids are ever imported and instantiated.
#
# Resolution semantics per grid type:
#   Hierarchical DGGS  → integer level (H3, S2, A5, QTM, rHEALPix, XYZ)
#   Planar projections → edge length in metres (Mercator, UTM)
# ---------------------------------------------------------------------------

def _build_registry():
    from dggs_benchmark.grids.h3_grid import H3Grid
    from dggs_benchmark.grids.s2_grid import S2Grid
    from dggs_benchmark.grids.mercator_grid import MercatorGrid
    from dggs_benchmark.grids.a5_grid import A5Grid
    from dggs_benchmark.grids.qtm_grid import QTMGrid
    from dggs_benchmark.grids.isea3h_grid import ISEA3HGrid
    from dggs_benchmark.grids.rhealpix_grid import RHEALPixGrid
    from dggs_benchmark.grids.utm_grid import UTMGrid
    from dggs_benchmark.grids.xyz_tile_grid import XYZTileGrid
    from dggs_benchmark.grids.geohash_grid import GeohashGrid

    return {
        "h3":       (H3Grid,        8),    # Mean cell ≈ 0.74 km²
        "s2":       (S2Grid,       13),    # Mean cell ≈ 1.27 km²
        "mercator": (MercatorGrid, 1000),  # 1 km × 1 km squares in EPSG:3857
        "utm":      (UTMGrid,      1000),  # 1 km × 1 km squares per UTM zone
        "a5":       (A5Grid,       15),    # Pentagon, approx 1 km²
        "qtm":      (QTMGrid,      15),    # Triangle, approx 1 km²
        "isea3h":   (ISEA3HGrid,   16),    # Hexagon, approx 1.18 km²
        "rhealpix": (RHEALPixGrid,  9),    # Equal-area squares
        "xyz":      (XYZTileGrid,  13),    # Zoom 13 ≈ 4.8 km equatorial edge
        "geohash":  (GeohashGrid,   6),    # Level 6 ≈ 1.2 km x 0.6 km
    }

def _instantiate_grids(selected):
    grids = []
    resolutions = {}
    for alias, (cls, res) in selected.items():
        try:
            grid = cls()
            grids.append(grid)
            resolutions[grid.name] = res
        except RuntimeError as e:
            print(f"[Warning] Skipping grid '{alias}': {e}", file=sys.stderr)
    return grids, resolutions

def run_geometric_distortion(args):
    from dggs_benchmark.experiments.geometric_distortion import GeometricDistortionExperiment

    registry = _build_registry()

    # ---- resolve --grids filter ----
    if args.grids:
        requested = [alias.strip().lower() for alias in args.grids.split(",")]
        unknown = [a for a in requested if a not in registry]
        if unknown:
            valid_list = ", ".join(sorted(registry))
            print(
                f"[Error] Unknown grid alias(es): {', '.join(unknown)}\n"
                f"  Valid aliases: {valid_list}",
                file=sys.stderr,
            )
            sys.exit(1)
        # Preserve registry insertion order within the requested subset
        selected = {alias: registry[alias] for alias in registry if alias in requested}
    else:
        selected = registry   # all grids

    grids, resolutions = _instantiate_grids(selected)
    if not grids:
        print("[Error] No valid grids could be instantiated. Exiting.", file=sys.stderr)
        sys.exit(1)

    print("--- Initializing Geometric Distortion Benchmark ---")
    print(f"  Grids selected: {', '.join(selected)}")
    experiment = GeometricDistortionExperiment(grids=grids, samples=args.samples, seed=args.seed)

    print(f"Executing over {len(grids)} grids with {args.samples} samples...")
    gdf = experiment.run(resolutions=resolutions)

    # Output
    os.makedirs(args.output_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    formats = [f.strip().lower() for f in args.output_format.split(",")]
    for fmt in formats:
        if fmt == "parquet":
            out_file = os.path.join(args.output_dir, f"geometric_distortion_{timestamp}.parquet")
            gdf.to_parquet(out_file)
            print(f"\n[Success] GeoParquet saved to: {out_file}")
        elif fmt == "gpkg":
            out_file = os.path.join(args.output_dir, f"geometric_distortion_{timestamp}.gpkg")
            gdf.to_file(out_file, driver="GPKG")
            print(f"\n[Success] GeoPackage saved to: {out_file}")
        elif fmt == "csv":
            out_file = os.path.join(args.output_dir, f"geometric_distortion_{timestamp}.csv")
            gdf.to_csv(out_file, index=False)
            print(f"\n[Success] CSV saved to: {out_file}")
        else:
            print(f"[Warning] Unknown output format: {fmt}", file=sys.stderr)

    # Save provenance metadata  (only the grids that actually ran)
    metadata = {
        "experiment": "Geometric Distortion",
        "samples": args.samples,
        "seed": args.seed,
        "grids_tested": list(resolutions.keys()),
        "resolutions": resolutions,
        "timestamp": timestamp,
        "output_file": out_file,
    }
    meta_file = os.path.join(args.output_dir, f"metadata_exp_1_{timestamp}.json")
    with open(meta_file, "w") as f:
        json.dump(metadata, f, indent=4)
    print(f"[Success] Provenance Metadata saved to: {meta_file}")

def run_relational_throughput(args):
    from dggs_benchmark.experiments.relational_throughput import RelationalThroughputExperiment

    registry = _build_registry()

    if args.grids:
        requested = [alias.strip().lower() for alias in args.grids.split(",")]
        selected = {alias: registry[alias] for alias in registry if alias in requested}
    else:
        selected = registry

    grids, resolutions = _instantiate_grids(selected)
    
    print(f"--- Initializing Relational Throughput Benchmark (ID-Joins) [{args.scale.upper()} SCALE] ---")
    experiment = RelationalThroughputExperiment(
        grids=grids, 
        samples=args.samples, 
        seed=args.seed, 
        scale=args.scale, 
        save_geometries=args.save_geometries, 
        output_dir=args.output_dir, 
        distribution=args.point_distribution,
        max_covering_sec=args.max_covering_sec
    )

    print(f"Executing over {len(grids)} grids with {args.samples} samples...")
    # Define the ROI Sweep resolutions for the paper (Dense Sweep for smooth plotting)
    sweep_resolutions = {}
    for grid in grids:
        if args.scale == "micro":
            if "H3" in grid.name:
                sweep_resolutions[grid.name] = [8, 9, 10]
            elif "S2" in grid.name:
                sweep_resolutions[grid.name] = [13, 14, 15, 16]
            elif "rHEALPix" in grid.name:
                sweep_resolutions[grid.name] = [8, 9, 10]
            elif "ISEA3H" in grid.name:
                sweep_resolutions[grid.name] = [16, 17, 18, 19, 20]
            elif "Geohash" in grid.name:
                sweep_resolutions[grid.name] = [6, 7]
            elif "XYZ" in grid.name:
                sweep_resolutions[grid.name] = [13, 14, 15, 16, 17]
            else:
                sweep_resolutions[grid.name] = [resolutions[grid.name]]
        else: # "macro", "macro-10m", "macro-europe"
            if "H3" in grid.name:
                sweep_resolutions[grid.name] = [4, 5, 6, 7, 8]
            elif "S2" in grid.name:
                sweep_resolutions[grid.name] = [8, 9, 10, 11, 12, 13]
            elif "rHEALPix" in grid.name:
                sweep_resolutions[grid.name] = [5, 6, 7, 8]
            elif "ISEA3H" in grid.name:
                sweep_resolutions[grid.name] = [10, 11, 12, 13, 14, 15, 16]
            elif "Geohash" in grid.name:
                sweep_resolutions[grid.name] = [4, 5, 6]
            elif "XYZ" in grid.name:
                sweep_resolutions[grid.name] = [8, 9, 10, 11, 12]
            else:
                sweep_resolutions[grid.name] = [resolutions[grid.name]]

    # ROI: 1M points recommended for systems paper
    df = experiment.run(resolutions_dict=sweep_resolutions)

    # Output
    os.makedirs(args.output_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = os.path.join(args.output_dir, f"relational_throughput_{args.scale}_{timestamp}.csv")
    df.to_csv(out_file, index=False)
    print(f"\n[Success] Throughput results saved to: {out_file}")

    # Save provenance metadata
    metadata = {
        "experiment": "Relational Throughput",
        "scale": args.scale,
        "samples": args.samples,
        "seed": args.seed,
        "timestamp": timestamp,
        "output_file": out_file,
    }
    meta_file = os.path.join(args.output_dir, f"metadata_roi_{args.scale}_{timestamp}.json")
    with open(meta_file, "w") as f:
        json.dump(metadata, f, indent=4)
    print(f"[Success] Provenance Metadata saved to: {meta_file}")

def run_download_data(args):
    """
    Stand-alone fetcher to pre-cache NE Boundaries and Overture data to local disk.
    """
    from dggs_benchmark.experiments.relational_throughput import RelationalThroughputExperiment
    print("--- Pre-caching Core Datasets for Offline Execution ---")
    
    experiment = RelationalThroughputExperiment(grids=[], samples=args.samples)
    
    print("\n[1/4] Downloading Natural Earth 50m (Macro Scale)...")
    experiment.scale = "macro"
    experiment._load_study_areas()
    
    print("\n[2/4] Downloading Natural Earth 10m (Macro High-Res Scale)...")
    experiment.scale = "macro-10m"
    experiment._load_study_areas()
    
    print("\n[3/4] Downloading Natural Earth 10m Urban Areas (Micro Scale)...")
    experiment.scale = "micro"
    experiment._load_study_areas()
    
    print(f"\n[4/4] Downloading Foursquare OS Places ({args.samples} Points)...")
    experiment.distribution = "real"
    experiment.samples = args.samples
    experiment._load_foursquare_places()
    
    print("\n[Success] All testing datasets successfully cached to project data/ directory!")

def run_topological_resilience(args):
    from dggs_benchmark.experiments.topological_resilience import TopologicalResilienceExperiment

    registry = _build_registry()

    if args.grids:
        requested = [alias.strip().lower() for alias in args.grids.split(",")]
        unknown = [a for a in requested if a not in registry]
        if unknown:
            valid_list = ", ".join(sorted(registry))
            print(
                f"[Error] Unknown grid alias(es): {', '.join(unknown)}\n"
                f"  Valid aliases: {valid_list}",
                file=sys.stderr,
            )
            sys.exit(1)
        selected = {alias: registry[alias] for alias in registry if alias in requested}
    else:
        selected = registry

    grids, resolutions = _instantiate_grids(selected)
    if not grids:
        print("[Error] No valid grids could be instantiated. Exiting.", file=sys.stderr)
        sys.exit(1)

    print("--- Initializing Topological Resilience Benchmark ---")
    print(f"  Grids selected: {', '.join(selected)}")
    experiment = TopologicalResilienceExperiment(grids=grids, samples=args.samples, seed=args.seed)

    print(f"Executing over {len(grids)} grids with {args.samples} samples...")
    gdf = experiment.run(resolutions=resolutions)

    os.makedirs(args.output_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    formats = [f.strip().lower() for f in args.output_format.split(",")]
    for fmt in formats:
        if fmt == "parquet":
            out_file = os.path.join(args.output_dir, f"topological_resilience_{timestamp}.parquet")
            gdf.to_parquet(out_file)
            print(f"\n[Success] GeoParquet saved to: {out_file}")
        elif fmt == "gpkg":
            out_file = os.path.join(args.output_dir, f"topological_resilience_{timestamp}.gpkg")
            gdf.to_file(out_file, driver="GPKG")
            print(f"\n[Success] GeoPackage saved to: {out_file}")
        elif fmt == "csv":
            out_file = os.path.join(args.output_dir, f"topological_resilience_{timestamp}.csv")
            gdf.to_csv(out_file, index=False)
            print(f"\n[Success] CSV saved to: {out_file}")
        else:
            print(f"[Warning] Unknown output format: {fmt}", file=sys.stderr)

    metadata = {
        "experiment": "Topological Resilience",
        "samples": args.samples,
        "seed": args.seed,
        "grids_tested": list(resolutions.keys()),
        "resolutions": resolutions,
        "timestamp": timestamp,
        "output_file": out_file,
    }
    meta_file = os.path.join(args.output_dir, f"metadata_exp_2_{timestamp}.json")
    with open(meta_file, "w") as f:
        json.dump(metadata, f, indent=4)
    print(f"[Success] Provenance Metadata saved to: {meta_file}")

def run_computational_throughput(args):
    from dggs_benchmark.experiments.computational_throughput import ComputationalThroughputExperiment

    registry = _build_registry()

    if args.grids:
        requested = [alias.strip().lower() for alias in args.grids.split(",")]
        unknown = [a for a in requested if a not in registry]
        if unknown:
            valid_list = ", ".join(sorted(registry))
            print(
                f"[Error] Unknown grid alias(es): {', '.join(unknown)}\n"
                f"  Valid aliases: {valid_list}",
                file=sys.stderr,
            )
            sys.exit(1)
        selected = {alias: registry[alias] for alias in registry if alias in requested}
    else:
        selected = registry

    grids, resolutions = _instantiate_grids(selected)
    if not grids:
        print("[Error] No valid grids could be instantiated. Exiting.", file=sys.stderr)
        sys.exit(1)

    print("--- Initializing Computational Throughput Benchmark ---")
    print(f"  Grids selected: {', '.join(selected)}")
    experiment = ComputationalThroughputExperiment(grids=grids, samples=args.samples, seed=args.seed, save_geometries=args.save_geometries)

    print(f"Executing over {len(grids)} grids with {args.samples} samples...")
    gdf = experiment.run(resolutions=resolutions)

    os.makedirs(args.output_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    formats = [f.strip().lower() for f in args.output_format.split(",")]
    for fmt in formats:
        if fmt == "parquet":
            out_file = os.path.join(args.output_dir, f"computational_throughput_{timestamp}.parquet")
            gdf.to_parquet(out_file)
            print(f"\n[Success] GeoParquet saved to: {out_file}")
        elif fmt == "gpkg":
            out_file = os.path.join(args.output_dir, f"computational_throughput_{timestamp}.gpkg")
            gdf.to_file(out_file, driver="GPKG")
            print(f"\n[Success] GeoPackage saved to: {out_file}")
        elif fmt == "csv":
            out_file = os.path.join(args.output_dir, f"computational_throughput_{timestamp}.csv")
            gdf.to_csv(out_file, index=False)
            print(f"\n[Success] CSV saved to: {out_file}")
        else:
            print(f"[Warning] Unknown output format: {fmt}", file=sys.stderr)

    metadata = {
        "experiment": "Computational Throughput",
        "samples": args.samples,
        "seed": args.seed,
        "grids_tested": list(resolutions.keys()),
        "resolutions": resolutions,
        "timestamp": timestamp,
        "output_file": out_file,
    }
    meta_file = os.path.join(args.output_dir, f"metadata_exp_3_{timestamp}.json")
    with open(meta_file, "w") as f:
        json.dump(metadata, f, indent=4)
    print(f"[Success] Provenance Metadata saved to: {meta_file}")

def run_generate_points(args):
    print(f"--- Generating {args.samples} Fibonacci Sphere Points ---")
    points = []
    phi = math.pi * (3. - math.sqrt(5.))
    for i in range(args.samples):
        y = 1 - (i / float(args.samples - 1)) * 2
        radius = math.sqrt(1 - y * y)
        theta = phi * i
        
        x = math.cos(theta) * radius
        z = math.sin(theta) * radius
        
        lat = math.degrees(math.asin(y))
        lon = math.degrees(math.atan2(z, x))
        points.append((lat, lon))
        
    random.seed(args.seed)
    random.shuffle(points)
    
    df = pd.DataFrame(points, columns=["lat", "lon"])
    gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.lon, df.lat), crs="EPSG:4326")
    
    os.makedirs(args.output_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    formats = [f.strip().lower() for f in args.output_format.split(",")]
    for fmt in formats:
        if fmt == "parquet":
            out_file = os.path.join(args.output_dir, f"fibonacci_points_{timestamp}.parquet")
            gdf.to_parquet(out_file)
            print(f"\n[Success] GeoParquet saved to: {out_file}")
        elif fmt == "gpkg":
            out_file = os.path.join(args.output_dir, f"fibonacci_points_{timestamp}.gpkg")
            gdf.to_file(out_file, driver="GPKG")
            print(f"\n[Success] GeoPackage saved to: {out_file}")
        elif fmt == "csv":
            out_file = os.path.join(args.output_dir, f"fibonacci_points_{timestamp}.csv")
            gdf.to_csv(out_file, index=False)
            print(f"\n[Success] CSV saved to: {out_file}")
        else:
            print(f"[Warning] Unknown output format: {fmt}", file=sys.stderr)

def cmd_list(_args):
    """Print all available grid aliases and their long names."""
    registry = _build_registry()
    print("Available grids (use alias with --grids):\n")
    for alias, (cls, res) in registry.items():
        instance = cls()
        eq = "equal-area" if instance.is_equal_area else "not equal-area"
        print(f"  {alias:<10}  resolution={res:<6}  [{eq}]  {instance.name}")


def main():
    parser = argparse.ArgumentParser(
        description="DGGS Benchmark Framework (SIGSPATIAL)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Point Generation:
  Points are generated using a Fibonacci sphere (golden angle method), which
  produces a deterministic, quasi-uniform distribution across the globe.
  Each run with the same N produces identical point coordinates.
  The --seed only controls the post-generation shuffle order.

Grid Selection:
  Use --grids to run a subset of grids (comma-separated aliases).
  Run `dggs-bench list` to see all available aliases.
  Example: dggs-bench run geometric-distortion --grids h3,s2,xyz
""",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # -- run ----------------------------------------------------------------
    run_parser = subparsers.add_parser("run", help="Run a benchmark experiment")
    run_parser.add_argument(
        "experiment", choices=["geometric-distortion", "topological-resilience", "computational-throughput", "relational-throughput"], help="The experiment to execute"
    )
    run_parser.add_argument(
        "--samples", type=int, default=None,
        help="Number of points. Defaults to dynamically matching the full local Parquet cache if available, or 10000 if generating synthetically."
    )
    run_parser.add_argument(
        "--seed", type=int, default=42,
        help="Seed for deterministic shuffle of Fibonacci points (does NOT affect point positions)"
    )
    run_parser.add_argument(
        "--output-dir", type=str, default="data/processed",
        help="Directory to save GeoParquet output (default: data/processed)"
    )
    run_parser.add_argument(
        "--grids", type=str, default=None,
        metavar="ALIASES",
        help=(
            "Comma-separated list of grid aliases to include "
            "(e.g. h3,s2,xyz). Omit to run all grids. "
            "Run `dggs-bench list` to see valid aliases."
        ),
    )
    run_parser.add_argument(
        "--output-format", type=str, default="parquet",
        help="Comma-separated list of formats (parquet,gpkg,csv). Default: parquet"
    )
    run_parser.add_argument(
        "--scale", type=str, choices=["macro", "macro-10m", "macro-europe", "micro"], default="macro",
        help="Scale boundary type. macro: 5 global countries (50m). macro-10m: High-res coastline penalty (10m). macro-europe: Dense continent overlapping (50m)."
    )
    run_parser.add_argument(
        "--save-geometries", action="store_true",
        help="Export actual GeoPackage geometries (Cells and Points) during Exp 3 runs for visual debugging."
    )
    run_parser.add_argument(
        "--point-distribution", type=str, choices=["uniform", "real", "urban_synthetic"], default="real",
        help="Use 'uniform' for Fibonacci sphere. Use 'real' for Foursquare OS Places Iceberg. Use 'urban_synthetic' for 0.05sec clustered mega-city models."
    )
    run_parser.add_argument(
        "--max-covering-sec", type=int, default=1800,
        help="Timeout heuristic (seconds) for the Covering Phase. If an execution exceeds this, deeper resolutions are skipped dynamically. (default: 1800)"
    )

    # -- generate-points ----------------------------------------------------
    points_parser = subparsers.add_parser("generate-points", help="Export the raw Fibonacci sphere sample points")
    points_parser.add_argument("--samples", type=int, default=10000, help="Number of points to generate")
    points_parser.add_argument("--seed", type=int, default=42, help="Random seed for shuffling")
    points_parser.add_argument("--output-dir", type=str, default="data/processed", help="Output directory")
    points_parser.add_argument("--output-format", type=str, default="parquet", help="Comma-separated list of formats (parquet,gpkg,csv)")

    # -- download-data ------------------------------------------------------
    download_parser = subparsers.add_parser("download-data", help="Pre-download mapping data for offline/standalone execution.")
    download_parser.add_argument("--samples", type=int, default=10000000, help="Number of Foursquare OS Places records to cache.")

    # -- list ---------------------------------------------------------------
    subparsers.add_parser("list", help="List all available grid aliases")

    args = parser.parse_args()

    if args.command == "run":
        if args.samples is None:
            # Automatically default to 10000 if not using dynamic sizing over real-world data caches
            if args.experiment != "relational-throughput" or getattr(args, "point_distribution", "") != "real":
                args.samples = 10000

        if args.experiment == "geometric-distortion":
            run_geometric_distortion(args)
        elif args.experiment == "topological-resilience":
            run_topological_resilience(args)
        elif args.experiment == "computational-throughput":
            run_computational_throughput(args)
        elif args.experiment == "relational-throughput":
            run_relational_throughput(args)
    elif args.command == "generate-points":
        run_generate_points(args)
    elif args.command == "download-data":
        run_download_data(args)
    elif args.command == "list":
        cmd_list(args)


if __name__ == "__main__":
    main()

