import time
import math
import random
import statistics
import pandas as pd
import geopandas as gpd
from pyproj import Geod
from typing import List, Tuple
from ..grids.base import BaseGrid

class TopologicalResilienceExperiment:
    """
    Experiment 2: Topological Boundary Resilience (The "Cliff" Test)
    
    Proves the "Universality" and "Tractability" of the framework by exposing 
    the fragility of Euclidean operations at planetary boundaries.
    Executes k-Nearest Neighbor (1-ring) traversals targeting strategic edge cases
    (Poles, Equator, International Date Line) vs a Random Control group.
    
    Metrics:
      - Nearest Neighbor Stability (Query latency, success/crash rates)
      - Topological Adjacency Consistency (Neighbors count)
      - Centerpoint Spacing Variation (Geodetic distance variance to neighbors)
    """
    def __init__(self, grids: List[BaseGrid], samples: int = 1000, seed: int = 42):
        self.grids = grids
        self.samples = samples
        self.seed = seed
        self.geod = Geod(ellps="WGS84")

    def _generate_edge_case_points(self) -> List[Tuple[float, float, str]]:
        """Generates targeted lat/lon/type tuples."""
        points = []
        random.seed(self.seed)
        
        # We will divide the requested samples among the categories
        # roughly: 20% North Pole, 20% South Pole, 20% Equator, 20% Date Line, 20% Random Control
        per_category = max(1, self.samples // 5)
        
        # 1. North Pole (latids near 89.9 to 89.999)
        for _ in range(per_category):
            lat = random.uniform(89.0, 89.999)
            lon = random.uniform(-180, 180)
            points.append((lat, lon, "North_Pole"))
            
        # 2. South Pole
        for _ in range(per_category):
            lat = random.uniform(-89.999, -89.0)
            lon = random.uniform(-180, 180)
            points.append((lat, lon, "South_Pole"))
            
        # 3. Equator
        for _ in range(per_category):
            lat = random.uniform(-0.1, 0.1)
            lon = random.uniform(-180, 180)
            points.append((lat, lon, "Equator"))
            
        # 4. Antimeridian / Date Line
        for _ in range(per_category):
            lat = random.uniform(-80, 80)
            # Pick arbitrarily very close to 180 or -180
            lon = random.choice([random.uniform(179.9, 180.0), random.uniform(-180.0, -179.9)])
            points.append((lat, lon, "Date_Line"))
            
        # 5. Random Control
        for _ in range(per_category):
            # Uniform lat/lon distribution (biased to poles, but this is just a quick control)
            lat = random.uniform(-80, 80)
            lon = random.uniform(-170, 170)
            points.append((lat, lon, "Control"))
            
        return points

    def run(self, resolutions: dict) -> gpd.GeoDataFrame:
        print(f"--- Running Topological Resilience Experiment ---")
        points = self._generate_edge_case_points()
        print(f"  Targeting {len(points)} edge-case points.")
        
        results = []
        
        for grid in self.grids:
            print(f"Processing Grid: {grid.name}...")
            seen_cells = set()
            resolution = resolutions.get(grid.name)
            
            if resolution is None:
                raise ValueError(f"Must provide a resolution mapping for {grid.name}")
                
            for lat, lon, point_type in points:
                # 1. Encode Point
                try:
                    cell_id = grid.encode_point(lat, lon, resolution)
                except Exception as e:
                    # If encoding outright fails (e.g. UTM at pole)
                    results.append({
                        "grid_name": grid.name,
                        "point_type": point_type,
                        "cell_id": "ENCODE_FAIL",
                        "test_lat": lat,
                        "test_lon": lon,
                        "success": False,
                        "error": str(e),
                        "latency_sec": 0.0,
                        "neighbor_count": 0,
                        "spacing_mean_m": 0.0,
                        "spacing_std_m": 0.0,
                        "geometry": None
                    })
                    continue
                    
                if cell_id in seen_cells:
                    continue
                seen_cells.add(cell_id)
                
                # 2. Test k_ring Traversal & Measure Latency
                start_time = time.perf_counter()
                try:
                    neighbors = grid.get_k_ring(cell_id, k=1)
                    end_time = time.perf_counter()
                    success = True
                    error_msg = None
                    latency = end_time - start_time
                except Exception as e:
                    end_time = time.perf_counter()
                    success = False
                    error_msg = str(e)
                    latency = end_time - start_time
                    neighbors = []
                    
                neighbor_count = len(neighbors)
                
                # 3. Calculate Centerpoint Spacing if successful
                spacing_mean = 0.0
                spacing_std = 0.0
                poly = None
                
                if success and neighbor_count > 0:
                    try:
                        # Fixed: Use rigorous geodetic center to avoid Antimeridian planar fallacy
                        lat0, lon0 = grid.get_cell_center(cell_id)
                        poly = grid.get_cell_polygon(cell_id)
                        
                        distances = []
                        for n_id in neighbors:
                            if n_id == cell_id: 
                                continue # Some libs include center in k-ring, some don't
                            
                            # Fixed: Use rigorous geodetic center for neighbors as well
                            lat1, lon1 = grid.get_cell_center(n_id)
                            
                            # CATCH SILENT PLANAR FALLACIES (e.g. Web Mercator wrapping to lon=181 or lat=91)
                            if abs(lat1) > 90.0 or abs(lon1) > 180.0:
                                raise ValueError(f"Planar Fallacy: Grid successfully returned a neighbor out of mathematical bounds! ({lat1:.4f}, {lon1:.4f})")
                            
                            # pyproj geod.inv returns (az12, az21, dist)
                            _, _, dist = self.geod.inv(lon0, lat0, lon1, lat1)
                            distances.append(dist)
                            
                        if len(distances) > 0:
                            spacing_mean = statistics.mean(distances)
                            if len(distances) > 1:
                                spacing_std = statistics.stdev(distances)
                    except Exception as e:
                        success = False
                        error_msg = f"Spacing metric failed: {str(e)}"

                results.append({
                    "grid_name": grid.name,
                    "point_type": point_type,
                    "cell_id": str(cell_id),
                    "test_lat": lat,
                    "test_lon": lon,
                    "success": success,
                    "error": error_msg,
                    "latency_sec": latency,
                    "neighbor_count": neighbor_count,
                    "spacing_mean_m": spacing_mean,
                    "spacing_std_m": spacing_std,
                    "geometry": poly
                })
                
        df = pd.DataFrame(results)
        # Create GeoDataFrame, dropping None geometries to avoid errors
        # Some rows might have failed and have no geometry, so we must be careful.
        # It's better to use geo-dataframe on just the valid geometries, but we want all rows.
        # Geopandas handles None geometry gracefully.
        gdf = gpd.GeoDataFrame(df, geometry="geometry", crs="EPSG:4326")
        return gdf
