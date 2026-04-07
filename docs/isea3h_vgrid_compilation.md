# Compiling OpenEAGGR (vgrid / ISEA3H) for Modern Linux

This document details the issues and solutions required to run the `vgrid` (ISEA3H) PIP package on modern Linux systems (Ubuntu 22.04+).

### The Root Causes of Failure

The default `vgrid` PyPI package contains a bundled `libdggs.so` library that is functionally broken on modern OS configurations due to two distinct deadlocks:

1. **PROJ 4 vs PROJ 9 Database Format Deadlock**: The binary was statically compiled in 2015 against **PROJ 4 / GDAL 2.0**. Modern Linux systems utilize **PROJ 9+**, which replaces the legacy projection format with an SQLite-based database. When `libdggs.so` is loaded into memory, its C++ static initializers attempt to parse the PROJ 9 database using PROJ 4 parsers, resulting in an infinite deadlock regardless of environment variables (like `PROJ_DATA`).
2. **Python 3.14 Free-Threading (No GIL) Deadlock**: In Python 3.14, the Global Interpreter Lock (GIL) is disabled (free-threading). However, GDAL's internal C++ static global initializers heavily rely on `pthread_mutex_lock` behaviors that historically assumed Python's GIL would guarantee orderly initialization across `ctypes.CDLL` barriers. Loading `libdggs.so` in Python 3.14 results in a silent thread deadlock.

### Solution Architecture

To resolve this, the OpenEAGGR `libdggs.so` library must be recompiled from the original [Riskaware-ltd/open-eaggr](https://github.com/riskaware-ltd/open-eaggr) source, patched to use modern GDAL 3 / PROJ 9 APIs, and loaded into a Python 3.12 environment (which retains the standard GIL).

#### Step 1: Source Patches for PROJ 9 and GDAL 3
The OpenEAGGR C++ source code requires the following patches before it will compile against modern system libraries:
*   **CoordinateConverter (PROJ 4 to PROJ 9)**: The deprecated `pj_init_plus`, `pj_transform`, and `projPJ` methods must be completely rewritten using the PROJ 9 C API (`proj_context_create`, `proj_create_crs_to_crs`, and `proj_trans`).
*   **GeoJsonImporter (GDAL 2 to GDAL 3)**: The internal `OGRGeoJSONReader` class was removed from the public GDAL 3 API. It must be replaced with the public `OGRGeometryFactory::createFromGeoJson()` method.
*   **KmlExporter**: C++14 strict compilation under GCC 13+ requires replacing `constexpr pow(...)` with static literal floating points (e.g. `5e-8`), as `pow` is not a `constexpr` function.

#### Step 2: Python 3.12 Environment Integration
Due to the Python 3.14 GIL deadlock, the benchmarking suite **must** be executed in a Python 3.11 or 3.12 environment. 

#### Step 3: Patching `vgrid/dggs/eaggr/eaggr.py`
The Python wrapper logic within the `vgrid` package must be patched to skip the bundled library loads. The following modifications are required in `_open_dlls()`:
1.  **Skip Bundled Libs**: Hardcode the Linux code path to jump straight to loading `libdggs.so`, skipping the defunct bundled `libproj.so` and `libgdal.so`.
2.  **Delay Import / Pre-initialize**: GDAL must be loaded into the Python process memory *before* `libdggs.so` is loaded via `ctypes.CDLL` by using `import osgeo.gdal`. This allows Python's native bindings to safely negotiate the thread locks before the C++ GDAL static initializers in `libdggs.so` execute.

*This documentation ensures the ISEA3H integration remains reproducible without relying entirely on upstream maintainers updating their 2015 binaries.*
