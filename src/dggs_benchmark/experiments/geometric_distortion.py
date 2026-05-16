import math
import random
import numpy as np
import pandas as pd
import geopandas as gpd
import warnings
from pyproj import Geod
from typing import List, Tuple
import antimeridian
from shapely.geometry.polygon import orient
from shapely import segmentize
from ..grids.base import BaseGrid

class GeometricDistortionExperiment:
    """
    Experiment 1: Geometric Distortion (The "Planar Fallacy" Proof)
    
    Calculates the true geodetic area, Zone Standardized Compactness (ZSC), 
    and Angular Deviation of grid cells sampled across the globe
    using a Fibonacci sphere (golden angle method) to achieve quasi-uniform 
    coverage. This method is deterministic — the same N always produces the 
    same point positions, making the experiment inherently reproducible.
    The --seed parameter only controls the shuffle order of those points.
    """
    def __init__(self, grids: List[BaseGrid], samples: int = 10_000, seed: int = 42):
        self.grids = grids
        self.samples = samples
        self.seed = seed
        # WGS84 Geod for true area calculation
        self.geod = Geod(ellps="WGS84")

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
            
        # Shuffle deterministically to prevent latitude ordering bias in early stops
        random.seed(self.seed)
        random.shuffle(points)
        return points

    def run(self, resolutions: dict) -> gpd.GeoDataFrame:
        """
        Executes the benchmark across all provided grids.
        resolutions dict maps Grid Name -> Native Resolution Integer
        """
        print(f"--- Running Geometric Distortion Experiment ---")
        print(f"  Method: Fibonacci sphere ({self.samples} points, seed={self.seed} controls shuffle only)")
        points = self._generate_fibonacci_sphere()
        
        results = []
        
        for grid in self.grids:
            print(f"Processing Grid: {grid.name}...")
            # For each grid we track seen cell IDs so we don't recalculate
            seen_cells = set()
            resolution = resolutions.get(grid.name)
            
            if resolution is None:
                raise ValueError(f"Must provide a resolution mapping for {grid.name}")
                
            # Allow grid implementations to pre-calculate all points in a single vectorized/subprocess call
            if hasattr(grid, "prefetch_points"):
                grid.prefetch_points(points, resolution)
                
            for lat, lon in points:
                try:
                    cell_id = grid.encode_point(lat, lon, resolution)
                except Exception as e:
                    # Skip geometries that mathematically refuse to project bounds (e.g., UTM at poles)
                    continue
                
                if cell_id not in seen_cells:
                    raw_polygon = grid.get_cell_polygon(cell_id)
                    
                    try:
                        # Pre-orient the polygon (Counter-Clockwise) before sending it to antimeridian.
                        # This prevents CW-wound geometries (like rHEALPix) from being interpreted
                        # as polygons that cover the entire Earth with a small hole, which causes
                        # segmentize() to generate millions of vertices and trigger an OOM Kill.
                        # Fix wrap-around issues safely.
                        # We pre-orient to CCW (sign=1.0) because antimeridian treats CW as Earth-spanning holes.
                        oriented_poly = orient(raw_polygon, sign=1.0)
                        
                        # Only apply antimeridian correction if the polygon actually has edges
                        # crossing the 180° meridian. The antimeridian library can corrupt small
                        # polygons that are near but not crossing the date line (dropping vertices
                        # and shrinking measured area by up to 60%). Detect crossing by checking
                        # for consecutive vertex pairs with longitude jumps > 180°.
                        crosses_am = False
                        ext_coords = list(oriented_poly.exterior.coords)
                        for ci in range(len(ext_coords) - 1):
                            if abs(ext_coords[ci][0] - ext_coords[ci + 1][0]) > 180:
                                crosses_am = True
                                break
                        
                        if crosses_am:
                            with warnings.catch_warnings():
                                warnings.simplefilter("ignore", category=UserWarning) 
                                fixed_poly = antimeridian.fix_polygon(oriented_poly)
                                
                                # If a strictly polar geometry (e.g. North Pole) is passed CCW, antimeridian
                                # misinterprets it as covering everything SOUTH of the pole. The bounds balloon
                                # to (-180, -90, 180, 90). In this edge case, CW orientation correctly isolates the pole.
                                if fixed_poly.bounds[1] == -90.0 and fixed_poly.bounds[3] == 90.0:
                                    fixed_poly = antimeridian.fix_polygon(orient(raw_polygon, sign=-1.0))
                                    
                                    # If it STILL spans the Earth (unlikely), abort segmentization to avoid 40,000km perimeter explosion
                                    if fixed_poly.bounds[1] == -90.0 and fixed_poly.bounds[3] == 90.0:
                                        raise ValueError("Polarity unresolvable")
                        else:
                            fixed_poly = oriented_poly
                        
                        # Densify edges every ~500m (0.005 deg) to accurately trace parallels.
                        polygon = segmentize(fixed_poly, max_segment_length=0.005)
                    except Exception as e:
                        # If correction unequivocally fails, DO NOT Euclidean segmentize an un-fixed dateline jump.
                        polygon = raw_polygon

                    # geod geometry_area_perimeter returns (area, perimeter)
                    area, perimeter = self.geod.geometry_area_perimeter(polygon)
                    area = abs(area)
                    perimeter = abs(perimeter)
                    
                    # 1. Compactness Calculations
                    # Use the WGS84 Authalic Radius (radius of a sphere with equal surface area)
                    # This ensures the $2\pi R^2(1 - \cos\theta)$ spherical cap area perfectly matches geodetic area
                    R_q = 6371007.1809
                    cos_theta = max(-1.0, min(1.0, 1 - (area / (2 * math.pi * R_q**2))))
                    sin_theta = math.sqrt(max(0.0, 1 - cos_theta**2))
                    p_cap = 2 * math.pi * R_q * sin_theta
                    
                    # Zone Standardized Compactness (Linear) - Kimerling et al.
                    zsc = (p_cap / perimeter) if perimeter > 0 else 0.0
                    
                    # Isoperimetric Quotient (Squared) - Spherical Polsby-Popper
                    ipq = (p_cap ** 2) / (perimeter ** 2) if perimeter > 0 else 0.0
                    
                    # 2. Angular Deviation Calculation
                    # CRITICAL: We MUST use the raw, undensified polygon for angles. 
                    # Segmentizing introduces hundreds of collinear points, driving the angle to 180 and destroying variance.
                    coords = list(raw_polygon.exterior.coords)
                    num_vertices = len(coords) - 1
                    
                    if num_vertices > 2:
                        interior_angles = []
                        for i in range(num_vertices):
                            # In closed rings, coords[-1] is a duplicate of coords[0]
                            prev_idx = i - 1
                            if prev_idx < 0:
                                prev_idx = num_vertices - 1
                            
                            lon1, lat1 = coords[prev_idx]
                            lon2, lat2 = coords[i]
                            lon3, lat3 = coords[(i+1) % num_vertices]
                            
                            az21, _, _ = self.geod.inv(lon2, lat2, lon1, lat1)
                            az23, _, _ = self.geod.inv(lon2, lat2, lon3, lat3)
                            
                            angle = (az23 - az21) % 360
                            # Filter out 'flat' 180-degree angles introduced by intermediate 
                            # edge densification (e.g. ISEA3H pts_per_edge=3). We strictly measure 
                            # topological shear at true convex corners (~90 to ~140 degrees).
                            if not (179.0 <= angle <= 181.0):
                                interior_angles.append(angle)
                            
                        interior_angles = np.array(interior_angles)
                        # np.std with ddof=1 produces sample standard deviation equivalent to statistics.stdev
                        angular_deviation = np.std(interior_angles, ddof=1) if len(interior_angles) > 1 else 0.0
                    else:
                        angular_deviation = 0.0
                    
                    results.append({
                        "grid_name": grid.name,
                        "cell_id": cell_id,
                        "center_lat": lat,
                        "center_lon": lon,
                        "area_m2": area,
                        "zsc": zsc,
                        "ipq": ipq,
                        "angular_deviation": angular_deviation,
                        # Store the shapely geometry for GeoParquet layout
                        "geometry": polygon 
                    })
                    seen_cells.add(cell_id)
                    
        # Convert to GeoDataFrame
        df = pd.DataFrame(results)
        gdf = gpd.GeoDataFrame(df, geometry="geometry", crs="EPSG:4326")
        return gdf
