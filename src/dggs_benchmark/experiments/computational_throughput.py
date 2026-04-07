import time
import math
import random
import pandas as pd
import geopandas as gpd
from typing import List, Tuple
from ..grids.base import BaseGrid

class ComputationalThroughputExperiment:
    """
    Experiment 3: Computational Throughput ("Tractability" & "Scalability")
    
    Benchmarks the pure Inter-DGGS efficiency and system scalability:
      - Encoding Latency
      - Decoding Latency
      - Traversal Speed (k-ring)
      - Aperture Benchmark (Parent partitioning latency)
      
    Generates samples and collects exact micro-measurements per grid to prove
    framework linearity out to 1M samples. Output is flushed to GeoParquet 
    to demonstrate out-of-core scalability constraints.
    """
    def __init__(self, grids: List[BaseGrid], samples: int = 10000, seed: int = 42):
        self.grids = grids
        self.samples = samples
        self.seed = seed

    def _generate_fibonacci_sphere(self) -> List[Tuple[float, float]]:
        """Generates an evenly distributed set of lat/lon points on a sphere."""
        points = []
        phi = math.pi * (3. - math.sqrt(5.))
        for i in range(self.samples):
            y = 1 - (i / float(self.samples - 1)) * 2
            radius = math.sqrt(1 - y * y)
            theta = phi * i
            
            x = math.cos(theta) * radius
            z = math.sin(theta) * radius
            
            lat = math.degrees(math.asin(y))
            lon = math.degrees(math.atan2(z, x))
            points.append((lat, lon))
            
        random.seed(self.seed)
        random.shuffle(points)
        return points

    def run(self, resolutions: dict) -> gpd.GeoDataFrame:
        print(f"--- Running Computational Throughput Experiment ---")
        points = self._generate_fibonacci_sphere()
        print(f"  Targeting {self.samples} points for throughput load testing.")
        
        results = []
        
        for grid in self.grids:
            print(f"Processing Grid: {grid.name}...")
            resolution = resolutions.get(grid.name)
            if resolution is None:
                raise ValueError(f"Must provide a resolution mapping for {grid.name}")
            
            # To ensure fairness, we can track total time over the loop
            # and average it out, rather than storing noisy perf_counter per-point,
            # but storing per-point proves full scalability. We'll store per-point.
            
            for index, (lat, lon) in enumerate(points):
                # 1. Encoding Latency
                t0 = time.perf_counter()
                try:
                    cell_id = grid.encode_point(lat, lon, resolution)
                    encode_t = time.perf_counter() - t0
                    success = True
                except Exception as e:
                    encode_t = time.perf_counter() - t0
                    success = False
                    cell_id = "FAIL"
                    
                decode_t = 0.0
                kring_t = 0.0
                parent_t = 0.0
                poly = None
                parent_id = None
                
                if success:
                    # 2. Decoding Latency
                    t0 = time.perf_counter()
                    try:
                        poly = grid.get_cell_polygon(cell_id)
                        decode_t = time.perf_counter() - t0
                    except Exception:
                        decode_t = time.perf_counter() - t0
                        
                    # 3. Traversal Latency (k=1)
                    t0 = time.perf_counter()
                    try:
                        _ = grid.get_k_ring(cell_id, k=1)
                        kring_t = time.perf_counter() - t0
                    except Exception:
                        kring_t = time.perf_counter() - t0
                        
                    # 4. Parent / Aperture Aggregation Latency
                    t0 = time.perf_counter()
                    try:
                        parent_id = grid.get_parent(cell_id)
                        parent_t = time.perf_counter() - t0
                    except NotImplementedError:
                        parent_t = 0.0 # Grid naturally lacks hierarchical aggregation
                        parent_id = "NOT_HIERARCHICAL"
                    except Exception:
                        parent_t = time.perf_counter() - t0
                        parent_id = "FAIL"

                results.append({
                    "grid_name": grid.name,
                    "point_id": index,
                    "target_lat": lat,
                    "target_lon": lon,
                    "cell_id": str(cell_id),
                    "parent_id": str(parent_id) if parent_id is not None else None,
                    "encode_sec": encode_t,
                    "decode_sec": decode_t,
                    "kring_sec": kring_t,
                    "parent_sec": parent_t,
                    "success": success,
                    "geometry": poly
                })
                
        df = pd.DataFrame(results)
        gdf = gpd.GeoDataFrame(df, geometry="geometry", crs="EPSG:4326")
        return gdf
