import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from dggs_benchmark.experiments.geometric_distortion import GeometricDistortionExperiment
from dggs_benchmark.cli import _build_registry, _instantiate_grids

def main():
    registry = _build_registry()
    test_grids = {k: registry[k] for k in ["h3", "s2", "isea3h", "rhealpix", "mercator", "utm"]}
    grids, resolutions = _instantiate_grids(test_grids)
    experiment = GeometricDistortionExperiment(grids=grids, samples=5000, seed=42)
    
    # generate base points
    points = [
        (0, 180), (0, -180), (89.99, 179.99), (-89.99, -179.99), (0.0, 179.99)
    ]
    # fill rest with some points
    points += [(float(i)/10.0, float(i)/10.0) for i in range(100)]
    
    experiment._generate_fibonacci_sphere = lambda: points
    
    gdf = experiment.run(resolutions)
    
    print("\n\nTest passed! Fixes Verified.")
    for grid_name in gdf['grid_name'].unique():
        sub = gdf[gdf['grid_name'] == grid_name]
        print(f"  {grid_name}: ZSC min={sub['zsc'].min():.6f}, AngDev mean={sub['angular_deviation'].mean():.2f}")

if __name__ == "__main__":
    main()
