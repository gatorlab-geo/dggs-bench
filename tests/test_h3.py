import sys, os
import pandas as pd
import geopandas as gpd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from dggs_benchmark.experiments.geometric_distortion import GeometricDistortionExperiment
from dggs_benchmark.cli import _build_registry, _instantiate_grids

def main():
    registry = _build_registry()
    test_grids = {k: registry[k] for k in ["h3"]}
    grids, resolutions = _instantiate_grids(test_grids)
    experiment = GeometricDistortionExperiment(grids=grids, samples=100000, seed=42)
    gdf = experiment.run(resolutions)
    
    for row in gdf.itertuples():
        if row.zsc < 0.1:
            print(f"GRID: {row.grid_name}")
            print(f"ZSC: {row.zsc}")
            print(f"LAT: {row.center_lat}, LON: {row.center_lon}")
            print(f"GEOMETRY: {row.geometry}")

if __name__ == "__main__":
    main()
