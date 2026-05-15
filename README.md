# dggs-bench

**A reproducible benchmarking framework for Discrete Global Grid Systems (DGGS)**

`dggs-bench` evaluates and compares the geometric properties of spherical grid systems — H3, S2, rHEALPix, A5, QTM, and standard map projections (UTM, Web Mercator, XYZ/WMTS) — using scientifically rigorous, ellipsoid-aware metrics.

Built at [GATOR Lab, University of Florida](https://gatorlab.io) to support the research paper:

> **How Do Discrete Global Grid Systems Actually Perform? A Systematic Benchmark Across Geometry, Computation and Relational Joins**  
> Submitted to *ACM Transactions in Spatial Algorithms and Systems (TSAS)*.  
> Preprint available on EarthArXiv: [https://doi.org/10.31223/X5B47J](https://doi.org/10.31223/X5B47J)

---

## Background

Discrete Global Grid Systems (DGGS) offer an alternative to traditional planar map projections by tessellating the Earth's surface into a hierarchy of cells. However, the theoretical benefits of DGGS are often offset by practical implementation trade-offs. Different grid systems—such as those based on icosahedrons, dodecahedrons, or quadtrees—exhibit varying levels of metric distortion, computational overhead, and topological anomalies near poles or boundaries. 

`dggs-bench` provides the experimental infrastructure to quantify these characteristics precisely — comparing the geodetic area variance, shape compactness, topological resilience, and relational throughput of each grid system systematically at scale.

---

## Installation

Requires Python ≥ 3.9.

```bash
pip install dggs-bench
```

**Dependencies**: `h3`, `s2sphere`, `geopandas`, `shapely`, `pyproj`, `pyarrow`, `mercantile`, `a5`, `vgrid`

> **Note**: `vgrid` must currently be installed from source. See [vgrid installation](https://github.com/thangqd/vgrid).

---

## Quick Start

```bash
# See all available grid systems
dggs-bench list

# Run the Geometric Distortion experiment on all 8 grids (10,000 sample points)
dggs-bench run geometric-distortion

# Run on a specific subset (e.g. H3, S2, and Web Mercator XYZ)
dggs-bench run geometric-distortion --grids h3,s2,xyz

# Control sample size, output location, and file formats (parquet, gpkg, csv)
dggs-bench run geometric-distortion --samples 50000 --output-dir results/ --output-format parquet,gpkg

# Pre-cache global testing datasets for standalone execution (Natural Earth + Overture Maps)
# Note: The 10M point Foursquare OS Places dataset is hosted on OSF.io (https://osf.io/bzkx6/) 
# and will be downloaded automatically.
dggs-bench download-data --samples 10000000
```

Output is written to `data/processed/` (or `--output-dir`) as:
- `geometric_distortion_<timestamp>.<format>` — Dataframes with geometry and precision metrics.
- `metadata_exp_1_<timestamp>.json` — Provenance record (seed, samples, grids, resolutions)

---

## Supported Grid Systems

| Alias | System | Cell Shape | Equal-Area | Benchmark Resolution |
|---|---|---|---|---|
| `h3` | H3 (Uber) | Hexagon | No | Level 8 (~0.74 km²) |
| `s2` | S2 Geometry (Google) | Square | No | Level 13 (~1.27 km²) |
| `rhealpix` | rHEALPix | Square | **Yes** | Level 9 |
| `a5` | A5 / Dodecahedron | Pentagon | No | Level 15 |
| `qtm` | QTM | Triangle | No | Level 15 |
| `isea3h` | ISEA3H | Hexagon | **Yes** | Level 12 |
| `mercator` | Web Mercator (EPSG:3857) | Square | No | 1000 m edge |
| `utm` | UTM (EPSG:326xx) | Square | No | 1000 m edge |
| `xyz` | XYZ Tiles / WMTS | Square | No | Zoom 13 |

All resolutions are calibrated to approximately 1 km² nominal cell area at mid-latitudes, isolating grid geometry as the independent variable.

---

## Output Formats & Schemas

`dggs-bench` outputs data dynamically via the `--output-format` flag, supporting three distinct container types perfectly suited for big spatial data:
1. **GeoParquet (`.parquet`)**: Default. Lightning-fast column store containing WKB geometries. Best for Pandas/Polars.
2. **GeoPackage (`.gpkg`)**: Best for dragging directly into QGIS/ArcGIS or handing off to reviewers via SQLite.
3. **CSV (`.csv`)**: Best for extremely old legacy systems (Note: Geometries are serialized as WKT strings).

Each of the three experiments produces a distinct DataFrame schema. Every row represents a single tested coordinate against a single grid.

### 1. Geometric Distortion Dataset (`geometric_distortion_*.parquet`)

| Column | Type | Description |
|---|---|---|
| `grid_name` | string | Full name of the grid system |
| `cell_id` | string | Native string identifier for the cell |
| `center_lat` / `lon` | float | Latitude/Longitude of the test point |
| `area_m2` | float | True WGS84 ellipsoid geodetic area in m² |
| `zsc` | float | Zone Standardized Compactness (Spherical shape variance factor) |
| `angular_deviation` | float | Variance of internal cell angles vs geodetic meridians |
| `geometry` | Polygon | Cell boundary in WGS84 (EPSG:4326), lon/lat order |

### 2. Topological Resilience Dataset (`topological_resilience_*.parquet`)

| Column | Type | Description |
|---|---|---|
| `point_type` | string | Category of extreme edge case (`North_Pole`, `Equator`, `Date_Line`, `Control`) |
| `success` | boolean | Did the projection crash/fail at this coordinate singularity? |
| `error` | string | Stack trace or exception message if `success` is False |
| `latency_sec` | float | CPU time taken specifically to find neighbor adjacency |
| `neighbor_count` | int | Quantity of adjacent neighbors found in the 1-ring traversal |
| `spacing_mean_m` | float | Mean geodetic distance from center point to all neighbors |
| `spacing_std_m` | float | Standard deviation of distances (Proves non-uniform spacing at boundaries) |

### 3. Computational Throughput Dataset (`computational_throughput_*.parquet`)

| Column | Type | Description |
|---|---|---|
| `point_id` | int | Unique numerical ID of the Fibonacci sample point |
| `parent_id` | string | Pre-calculated parent grouping ID (`NOT_HIERARCHICAL` if planar grid) |
| `encode_sec` | float | Micro-latency to convert WGS84 coordinate → String ID |
| `decode_sec` | float | Micro-latency to convert String ID → Polygons |
| `kring_sec` | float | Micro-latency for deep graph traversal (Generating adjacency arrays) |
| `parent_sec` | float | Micro-latency for hierarchical aperture scaling (Child → Parent) |

### 4. Relational Throughput Dataset (`relational_throughput_*.csv`)

| Column | Type | Description |
|---|---|---|
| `grid_name` | string | Grid alias (e.g., H3, S2) |
| `resolution` | int | Resolution scaled for the experiment |
| `ingestion_sec` | float | Time to encode millions of coordinates to Grid ID arrays |
| `covering_sec` | float | Time to polyfill country geometry bounds into Grid cell regions |
| `join_sec` | float | Exact time taken for DuckDB Relational Index `p.id = c.id` Join |
| `count` | int | True Positives dynamically matched by the Relational Database |
| `accuracy_pct` | float | % coverage ratio vs standard Vector `ST_Intersects` Baseline |

```python
import geopandas as gpd

# Example: Analyzing CPU latency for H3 vs UTM
gdf = gpd.read_parquet("data/processed/computational_throughput_20260324.parquet")
print(gdf.groupby("grid_name")["encode_sec"].mean())
```

---

## Sampling Methodology

Points are generated using the **Fibonacci sphere (golden angle method)** — a deterministic, quasi-uniform distribution across all latitudes with no random component in point positions. The `--seed` parameter only controls the post-generation shuffle order (not which points exist), making every run intrinsically reproducible.

```
--samples N   →  same N always generates the same N global coordinates
--seed S      →  controls iteration order only
```

### Exporting Sample Points
To visualize or analyze the pure WGS84 coordinate distributions without intersecting them against a grid, you can export the generated points directly into any format:

```bash
dggs-bench generate-points --samples 10000 --output-dir data/ --output-format parquet,gpkg
```

---

## Extending the Framework

Because `dggs-bench` was designed as a unified mathematical instrument, extending it for your own research is highly encouraged. 

- **Adding a New Grid System**: Follow the [Custom Grid Developer Guide](https://github.com/gatorlab-geo/dggs-bench/blob/main/docs/custom_grids.md) to wrap your projection into the standardized `BaseGrid` API.
- **Adding a New Experiment**: Follow the [Custom Experiment Developer Guide](https://github.com/gatorlab-geo/dggs-bench/blob/main/docs/custom_experiments.md) to write a new scientific Python engine evaluating multi-resolution topology, containment, or other novel metrics.

---

## Scientific Experiments (ACM TSAS)

The framework ships with three peer-reviewed computational instruments:

| CMD | Name | Description |
|---|---|---|
| `geometric-distortion` | **1. Geometric Distortion** | Proves the "Planar Fallacy". Calculates True Geodetic Area, Zone Standardized Compactness (ZSC), and Angular Deviation for 1M global coordinates. |
| `topological-resilience` | **2. Topological Boundaries** | The "Cliff" Test. Probes coordinate singularities (Poles, Date Line) measuring k-NN failure rates, adjacency counts, and centroid variance. |
| `computational-throughput` | **3. Computational Throughput** | Algorithmic benchmarker testing hardware efficiency. Captures raw library latencies for string encoding, spatial decoding, deep graph traversal, and hierarchical scaling. |
| `relational-throughput` | **4. Relational Database ROI** | Tests standard Vector Math (`ST_Intersects`) vs string Joins on massive point clouds inside DuckDB across multiple grid scales. Supports geographic `--scale` parameters (`macro`, `macro-10m`, `macro-europe`, `micro`) and real-world Overture Maps distribution profiling `--point-distribution real`. |

---

## Reproducibility

Every run writes a provenance JSON alongside the data:

```json
{
    "experiment": "Computational Throughput",
    "samples": 10000,
    "seed": 42,
    "grids_tested": ["H3 (Uber)", "S2 Geometry (Google)", "XYZ Tiles (WMTS / Slippy Map)"],
    "resolutions": {"H3 (Uber)": 8, "S2 Geometry (Google)": 13, "XYZ Tiles (WMTS / Slippy Map)": 13},
    "timestamp": "20260323_141955",
    "output_file": "data/processed/computational_throughput_20260323_141955.parquet"
}
```

---

## Citation

If you use `dggs-bench` in your research, please cite the framework and the accompanying paper:

```bibtex
@article{juhasz2026dggsbench_paper,
  author  = {Juhász, Levente},
  title   = {How Do Discrete Global Grid Systems Actually Perform? A Systematic Benchmark Across Geometry, Computation and Relational Joins},
  journal = {EarthArXiv},
  year    = {2026},
  doi     = {10.31223/X5B47J},
  url     = {https://doi.org/10.31223/X5B47J}
}

@software{juhasz2026dggsbench_software,
  author  = {Juhász, Levente},
  title   = {dggs-bench: A Reproducible Benchmarking Framework for Discrete Global Grid Systems},
  year    = {2026},
  url     = {https://github.com/gatorlab-geo/dggs-bench},
  institution = {GATOR Lab, University of Florida}
}
```

---

## License

MIT License. See `LICENSE`.
