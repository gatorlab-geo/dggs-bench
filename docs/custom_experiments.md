# Implementing Custom Experiments in dggs-bench

While `dggs-bench` ships with three core ACM SIGSPATIAL experiments, adding a custom benchmark to measure a new geographic property (e.g., cell edge lengths, intersection throughput, or multi-resolution containment) is straightforward.

## 1. The Experiment Engine

Experiments in `dggs-bench` are standard Python classes. They accept a list of instantiated grid objects, generate a sample set of coordinates, iterate over the grids, and return a `geopandas.GeoDataFrame` containing the metrics.

To create a new experiment, create a file in `src/dggs_benchmark/experiments/my_experiment.py`:

```python
import pandas as pd
import geopandas as gpd
from typing import List
from ..grids.base import BaseGrid

class MyCustomExperiment:
    """
    Experiment: Multi-Resolution Containment
    Objective: Measures how accurately child cells are contained by parents.
    """
    def __init__(self, grids: List[BaseGrid], samples: int = 1000, seed: int = 42):
        self.grids = grids
        self.samples = samples
        self.seed = seed

    def _generate_points(self):
        # Implement your sampling strategy (Fibonacci sphere, random, or targeted)
        # return [(lat, lon), ...]
        pass

    def run(self, resolutions: dict) -> gpd.GeoDataFrame:
        points = self._generate_points()
        results = []
        
        for grid in self.grids:
            print(f"Running on {grid.name}...")
            resolution = resolutions.get(grid.name)
            
            for lat, lon in points:
                # 1. Hit the grid API
                cell_id = grid.encode_point(lat, lon, resolution)
                poly = grid.get_cell_polygon(cell_id)
                
                # 2. Calculate your custom metric
                # custom_metric = calculate_foo(poly)
                
                # 3. Log results
                results.append({
                    "grid_name": grid.name,
                    "cell_id": cell_id,
                    "target_lat": lat,
                    "target_lon": lon,
                    "custom_metric": 42.0, # Replace with real calculation
                    "geometry": poly       # Required for GeoDataFrame
                })
                
        # Return as GeoParquet-compatible GeoDataFrame
        df = pd.DataFrame(results)
        return gpd.GeoDataFrame(df, geometry="geometry", crs="EPSG:4326")
```

## 2. Registering the Experiment

Once your engine is written, expose it to the `dggs-bench` CLI.

### Step A: Export it from the Module
Open `src/dggs_benchmark/experiments/__init__.py`:

```python
from .my_experiment import MyCustomExperiment

__all__ = [
    # ... other experiments ...
    "MyCustomExperiment"
]
```

### Step B: Wire it into the CLI
Open `src/dggs_benchmark/cli.py` and create a runner function that handles the argparse IO, just like the existing experiments:

```python
def run_my_custom_experiment(args):
    from dggs_benchmark.experiments.my_experiment import MyCustomExperiment
    
    # 1. Build Grid Registry based on --grids argument
    # ... (Copy the registry builder from run_geometric_distortion) ...
    
    # 2. Instantiate Experiment
    experiment = MyCustomExperiment(grids=grids, samples=args.samples, seed=args.seed)
    gdf = experiment.run(resolutions=resolutions)
    
    # 3. Save GeoParquet and JSON Metadata
    # ... (Copy the file saving logic from run_geometric_distortion) ...
```

Finally, add the command to the `argparse` choices at the bottom of `cli.py`:

```python
    run_parser.add_argument(
        "experiment", 
        choices=[
            "geometric-distortion", 
            "topological-resilience", 
            "computational-throughput",
            "my-custom-experiment" # <-- Add here
        ], 
        help="The experiment to execute"
    )

    # In the execution block:
    if args.experiment == "my-custom-experiment":
        run_my_custom_experiment(args)
```

## 3. Best Practices

- **Deterministic Sampling**: Always seed your coordinate generators. This allows reviewers to reproduce your exact geographic edge cases.
- **Error Handling**: Use `try/except` blocks around grid methods. Standard map projections (like Web Mercator and UTM) will mathematically crash at the poles. Your experiment loop should catch these errors, log `"success": False`, and continue execution rather than halting the script. 
- **Geodetic Math**: Only use WGS84 coordinates. For true area/distance calculations on the ellipsoid, use `pyproj.Geod(ellps="WGS84")` rather than Cartesian math on polynomials.
