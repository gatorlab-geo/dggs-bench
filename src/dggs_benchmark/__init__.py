# dggs_benchmark — Reproducible DGGS benchmarking framework
import os

# Fix for Conda vs User site-packages PROJ database missing path
if "PROJ_DATA" not in os.environ and "PROJ_LIB" not in os.environ:
    if "CONDA_PREFIX" in os.environ:
        proj_path = os.path.join(os.environ["CONDA_PREFIX"], "share", "proj")
        if os.path.exists(proj_path):
            os.environ["PROJ_DATA"] = proj_path
            os.environ["PROJ_LIB"] = proj_path

__version__ = "0.1.0"
