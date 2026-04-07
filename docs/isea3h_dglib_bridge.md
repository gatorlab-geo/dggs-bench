# ISEA3H dglib Bridge: Direct C++ Library Integration

## Overview

This document describes the `dglib_bridge` — a thin C++/Python shim that
calls DGGRID's internal `dglib` C++ library **in-process**, completely
bypassing the `dggrid` CLI and all file I/O.

**Location**: `dggs-bench/src/dggs_benchmark/grids/dglib_bridge/`

---

## Motivation: Why Not the CLI? Why Not vgrid?

| Approach | Problem |
|---|---|
| `dggrid` CLI + subprocess batching | `GENERATE_GRID` with `INPUT_ADDRESS_TYPE` is unreliable at Res 16/1M scale. Fallback triggers 1M individual subprocesses (death-loop). |
| `vgrid` / OpenEAGGR `libdggs.so` | (1) PROJ 4 vs PROJ 9 deadlock — compiled 2015. (2) Python 3.14 free-threading GIL deadlock. Recompile of OpenEAGGR source also failed with deeper issues. |
| **`dglib` direct (this approach)** | In-process. No GDAL/PROJ 9 dependencies — dglib bundles its own `proj4lib`. No temp files. No subprocesses. |

---

## Architecture

```
Python (isea3h_native.py)
    |  ctypes
    v
isea3h_bridge.so  (C ABI)
    |  C++ calls
    v
libdglib.a + libdgaplib.a + libproj4lib.a + libshapelib.a
    (all from DGGRID v8.43 source: /tmp/DGGRID_src)
```

The `.so` exposes three C functions:

```c
int  encode_points_batch(double* lats, double* lons, int n,
                         int resolution, char** out_ids);
int  get_cell_polygon(const char* cell_id, int resolution,
                      double* out_lons, double* out_lats,
                      int* out_n_verts, int pts_per_edge);
int  get_k_ring(const char* cell_id, int resolution, int k,
                char** out_ids, int* out_count, int max_out);
void free_string_array(char** ids, int n);
void reset_grid_state();
```

### Address System
- Uses `DgIDGGS3H::makeRF()` → `DgIDGG` at the target resolution
- Cell IDs are **Z3_STRING** format via `Dg2WayZ3StringConverter` (Q2DI ↔ DgZ3StringRF)
- Z3 IDs at Res 16 are exactly 18 characters long (2-digit face quad + 16 trit digits)
- IDs are globally unique and match the Z3_STRING produced by the `dggrid` CLI

---

## Build Instructions

### Prerequisites
- DGGRID v8.43 source cloned and **built with `-fPIC`** at `/tmp/DGGRID_src/build_pic`
- GCC / G++ with C++14 support

```bash
# One-time: rebuild dglib with -fPIC (required for shared lib)
cd /tmp/DGGRID_src
mkdir -p build_pic && cd build_pic
cmake -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_CXX_FLAGS="-fPIC" \
      -DCMAKE_C_FLAGS="-fPIC" \
      -DWITH_GDAL=OFF ..
make -j$(nproc) dglib dgaplib proj4lib shapelib

# Build the bridge (requires libgdal-dev)
cd /path/to/dggs-bench/src/dggs_benchmark/grids/dglib_bridge/
bash build.sh
```

The result is `isea3h_bridge.so` (≈2.4 MB, statically linked against all four dglib sub-libraries).

> [!NOTE]
> The pre-built `.so` in the repo was compiled on the development machine. If you move
> to a different OS/glibc, you must rebuild. The `build.sh` script is fully reproducible.

---

## Python Usage

```python
from dggs_benchmark.grids.dglib_bridge.isea3h_native import ISEA3HNative

grid = ISEA3HNative(resolution=16, pts_per_edge=1)

# Batch encode — ~19s for 1M points (extrapolated from 0.019s/1k benchmark)
ids = grid.encode_points([(lat1, lon1), (lat2, lon2), ...])

# Get polygon boundary for a cell
verts = grid.get_cell_polygon(ids[0])  # -> list of (lon, lat)

# Topological traversal (k-ring)
neighbors = grid.get_k_ring(ids[0], k=1) # -> list of 6-7 neighbor IDs
```

---

## Verification Results (Smoke Test — 2026-03-25)

| Test | Result |
|---|---|
| Equator/Prime Meridian | `030011111102020000` ✅ |
| North Pole | `012222222222222222` ✅ (12 vertices returned) |
| South Pole | `080101010101010112` ✅ |
| IDL seamlessness | `(0, 180)` and `(0, -180)` → same cell ID ✅ |
| Z3 ID length at Res 16 | Always 18 chars ✅ |
| 1000-point batch encode latency | **0.019s** |
| Extrapolated 1M encode | **~19s** |
| Unique cells from 1000 Fibonacci pts | 1000/1000 (100%) ✅ |
| **Topological Adjacency (k-ring)** | **Implemented (k=1)** ✅ (2026-03-26) |
| **Execution Environment** | **Conda dggs-bench-py312** ✅ (Stable) |

---

## Integration with `dggs-bench`

The `ISEA3HGrid` wrapper in `grids/isea3h_grid.py` should be rewritten to use
`ISEA3HNative` as its backend, replacing the current `dggrid4py`-subprocess approach.

Key changes needed in `isea3h_grid.py`:
1. Import `ISEA3HNative` from `dglib_bridge/isea3h_native.py`
2. Replace `prefetch_points` → `grid.encode_points(points)` (batch, in-process)
3. Replace `get_cell_polygon` → `grid.get_cell_polygon(cell_id)` (in-process, returns vertex list)
4. Construct a Shapely `Polygon` from the returned `(lon, lat)` tuples

---

## Known Limitations

- **Machine-specific build**: The `.so` must be compiled on the target machine.
  The `build.sh` script handles this reproducibly.
- **Singleton grid state**: The C++ layer caches one `DgRFNetwork` per resolution.
  If multiple Python threads call with different resolutions simultaneously, a mutex
  should be added. For single-threaded `prefetch_points` usage this is not an issue.
- **No parallelism in encoding**: The batch encode loop is single-threaded C++.
  For 1M points this is still ~19s which is acceptable. Can be parallelized later if needed.
