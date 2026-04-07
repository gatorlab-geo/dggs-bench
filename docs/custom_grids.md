# Implementing Custom Grids in dggs-bench

`dggs-bench` was designed to be easily extensible. If you are developing a new Discrete Global Grid System (DGGS) or want to benchmark a projection not currently included, you can add it to the suite by creating a single Python wrapper class.

## 1. The `BaseGrid` Interface

Every grid system in the framework inherits from `BaseGrid` (located in `src/dggs_benchmark/grids/base.py`). This abstract base class enforces a uniform API so that experiments can evaluate any grid without knowing its underlying mathematics.

To add your grid, create a new file in `src/dggs_benchmark/grids/my_custom_grid.py` and implement the following interface:

```python
from typing import List
from shapely.geometry import Polygon
from .base import BaseGrid
# Import your grid's mathematical library here

class MyCustomGrid(BaseGrid):
    
    @property
    def name(self) -> str:
        """Returns the human-readable name of the grid for charts and logs."""
        return "My Custom Grid (MCG)"

    @property
    def is_equal_area(self) -> bool:
        """Does your grid mathematically guarantee equal area cells?"""
        return True # or False

    def encode_point(self, lat: float, lon: float, resolution: int) -> str:
        """
        Takes a WGS84 coordinate (latitude, longitude in degrees) and a 
        resolution level, returning the cell's unique String ID.
        """
        # Example using a hypothetical library:
        # cell_id = my_lib.geo_to_cell(lat, lon, resolution)
        # return str(cell_id)
        pass

    def get_cell_polygon(self, cell_id: str) -> Polygon:
        """
        Takes a cell ID and returns its WGS84 boundary as a Shapely Polygon.
        WARNING: Shapely expects coordinates in (longitude, latitude) order!
        """
        # Example:
        # coords = my_lib.get_boundary(cell_id)
        # lon_lat_coords = [(lon, lat) for lat, lon in coords]
        # return Polygon(lon_lat_coords)
        pass

    def get_k_ring(self, cell_id: str, k: int) -> List[str]:
        """
        Returns a list of cell IDs (as strings) that form the k-ring neighbors
        around the target cell. k=1 means immediate touching neighbors.
        """
        pass
        
    def get_parent(self, cell_id: str) -> str:
        """
        Returns the Parent Cell ID at the next coarsest resolution level.
        If your grid is not hierarchical, raise a NotImplementedError.
        """
        pass
```

## 2. Registering the Grid

Once your class is written, you need to expose it to the `dggs-bench` Command Line Interface (CLI). 

### Step A: Export it from the Module
Open `src/dggs_benchmark/grids/__init__.py` and add your grid:

```python
from .my_custom_grid import MyCustomGrid

__all__ = [
    # ... existing grids ...
    "MyCustomGrid"
]
```

### Step B: Add it to the CLI Registry
Open `src/dggs_benchmark/cli.py` and locate the `_build_registry()` function. Add your grid an alias and a default benchmark resolution. 

*Note: The resolution parameter should be calibrated so the cell area is roughly ~1 km² at the equator, ensuring fair apples-to-apples geometric benchmarking against H3 Level 8.*

```python
def _build_registry():
    from dggs_benchmark.grids import (
        # ... imported grids ...
        MyCustomGrid
    )
    
    return {
        # "alias": (GridClass, Default_Resolution_For_1km2)
        "h3": (H3Grid, 8),
        "mygrid": (MyCustomGrid, 12), # <-- Add your grid here
    }
```

## 3. Testing Your Grid

You can immediately test your new grid against all existing benchmark experiments via the CLI:

```bash
# Verify it appears in the list
dggs-bench list

# Run the Geometric Distortion experiment targeting only your grid
dggs-bench run geometric-distortion --grids mygrid --samples 100
```
