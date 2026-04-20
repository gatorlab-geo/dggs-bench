import time
import math
import random
import pandas as pd
import geopandas as gpd
import psutil
import os
import resource
from typing import List, Tuple
from ..grids.base import BaseGrid

def _get_rss_mb() -> float:
    """Return current process Resident Set Size in MB."""
    return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)

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
    def __init__(self, grids: List[BaseGrid], samples: int = 10000, seed: int = 42, save_geometries: bool = False):
        self.grids = grids
        self.samples = samples
        self.seed = seed
        self.save_geometries = save_geometries

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
            
            # --- MACRO AGGREGATION MODE (>100k points) ---
            # Prevents OOM-Killer by avoiding 60 Million instantiated Python Dictionaries and Shapely Points
            if self.samples >= 100000:
                success_count = 0
                rss_before = _get_rss_mb()
                peak_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024  # KB → MB on Linux
                
                # 1. Encoding Latency (Tight Loop)
                t0 = time.perf_counter()
                encoded_ids = []
                for lat, lon in points:
                    try:
                        encoded_ids.append(grid.encode_point(lat, lon, resolution))
                        success_count += 1
                    except Exception:
                        encoded_ids.append("FAIL")
                encode_total = time.perf_counter() - t0
                rss_after_encode = _get_rss_mb()
                
                # 2. Decoding Latency
                t0 = time.perf_counter()
                for cid in encoded_ids:
                    if cid != "FAIL":
                        try:
                            grid.get_cell_polygon(cid)
                        except Exception:
                            pass
                decode_total = time.perf_counter() - t0
                
                # 3. Traversal (k-ring) Latency
                t0 = time.perf_counter()
                for cid in encoded_ids:
                    if cid != "FAIL":
                        try:
                            grid.get_k_ring(cid, k=1)
                        except Exception:
                            pass
                kring_total = time.perf_counter() - t0
                
                # 4. Hierarchical (Parent) Latency
                t0 = time.perf_counter()
                for cid in encoded_ids:
                    if cid != "FAIL":
                        try:
                            grid.get_parent(cid)
                        except NotImplementedError:
                            pass
                        except Exception:
                            pass
                parent_total = time.perf_counter() - t0
                rss_after_all = _get_rss_mb()
                peak_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
                rss_peak_mb = peak_after  # kernel high-water mark
                
                print(f"  Memory: {rss_before:.1f} → {rss_after_encode:.1f} → {rss_after_all:.1f} MB (before/encode/all), peak={rss_peak_mb:.1f} MB")
                
                results.append({
                    "grid_name": grid.name,
                    "resolution": resolution,
                    "samples": self.samples,
                    "encode_sec": encode_total,
                    "decode_sec": decode_total,
                    "kring_sec": kring_total,
                    "parent_sec": parent_total,
                    "throughput_p_sec": self.samples / max(0.001, encode_total),
                    "success_rate": (success_count / self.samples) * 100,
                    "rss_before_mb": rss_before,
                    "rss_after_encode_mb": rss_after_encode,
                    "rss_after_all_mb": rss_after_all,
                    "rss_peak_mb": rss_peak_mb,
                })

            else:
                # --- MICRO-PROFILING MODE (<100k points) ---
                # Retains exact point-by-point variances for standard deviation boxplots
                rss_before = _get_rss_mb()
                peak_before_micro = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
                for index, (lat, lon) in enumerate(points):
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
                        t0 = time.perf_counter()
                        try:
                            poly = grid.get_cell_polygon(cell_id)
                            decode_t = time.perf_counter() - t0
                        except Exception:
                            decode_t = time.perf_counter() - t0
                            
                        t0 = time.perf_counter()
                        try:
                            _ = grid.get_k_ring(cell_id, k=1)
                            kring_t = time.perf_counter() - t0
                        except Exception:
                            kring_t = time.perf_counter() - t0
                            
                        t0 = time.perf_counter()
                        try:
                            parent_id = grid.get_parent(cell_id)
                            parent_t = time.perf_counter() - t0
                        except NotImplementedError:
                            parent_t = 0.0 
                            parent_id = "NOT_HIERARCHICAL"
                        except Exception:
                            parent_t = time.perf_counter() - t0
                            parent_id = "FAIL"
    
                    record = {
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
                        "success": success
                    }
                    
                    if self.save_geometries and poly is not None:
                        record["geometry"] = poly
                        
                    results.append(record)
                
                # Record memory snapshot after all points for this grid
                rss_after_all = _get_rss_mb()
                rss_peak_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
                print(f"  Memory: {rss_before:.1f} → {rss_after_all:.1f} MB, peak={rss_peak_mb:.1f} MB")
                # Inject memory into the last record for this grid
                if results:
                    results[-1]['rss_before_mb'] = rss_before
                    results[-1]['rss_after_all_mb'] = rss_after_all
                    results[-1]['rss_peak_mb'] = rss_peak_mb
                
        df = pd.DataFrame(results)
        
        # Only inject Geopandas spatial wrapper if we actually saved per-point properties
        if self.samples < 100000:
            if self.save_geometries and "geometry" in df.columns:
                return gpd.GeoDataFrame(df, geometry="geometry", crs="EPSG:4326")
            else:
                return gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.target_lon, df.target_lat), crs="EPSG:4326")
        
        return df
