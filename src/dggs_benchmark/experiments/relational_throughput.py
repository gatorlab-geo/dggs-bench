import time
import math
import random
import pandas as pd
import geopandas as gpd
import duckdb
import numpy as np
from typing import List, Tuple, Dict
from shapely.geometry import Point, Polygon, MultiPolygon
from ..grids.base import BaseGrid

class RelationalThroughputExperiment:
    """
    Experiment 4: Relational Database Throughput & ROI ("The Resolution Edge")
    
    Benchmarks the performance of DGGS-ID joins versus traditional Vector Spatial 
    Joins (ST_Intersects) in DuckDB using Natural Earth countries. Sweeps across
    multiple DGGS resolutions to identify the exact ROI Break-Even point.
    """
    def __init__(self, grids: List[BaseGrid], samples: int = 100000, seed: int = 42, scale: str = "macro", save_geometries: bool = False, output_dir: str = "data/processed", distribution: str = "real"):
        self.grids = grids
        self.samples = samples
        self.seed = seed
        self.scale = scale
        self.save_geometries = save_geometries
        self.output_dir = output_dir
        self.distribution = distribution
        self.con = duckdb.connect(database=':memory:')
        self.con.execute("INSTALL spatial; LOAD spatial;")

    def _generate_points(self) -> pd.DataFrame:
        if self.distribution == "uniform":
            return self._generate_fibonacci_sphere()
        elif self.distribution == "urban_synthetic":
            return self._generate_urban_synthetic()
        else:
            return self._load_overture_buildings()

    def _generate_urban_synthetic(self) -> pd.DataFrame:
        print(f"  Generating {self.samples} massively clustered 'real-world' urban points (Synthetic Gaussian)...")
        # 10 Major Global Hubs (Lat, Lon)
        hubs = [
            (40.7128, -74.0060),  # North America: NYC
            (51.5074, -0.1278),   # Europe: London
            (48.8566, 2.3522),    # Europe: Paris
            (35.6762, 139.6503),  # Asia: Tokyo
            (19.0760, 72.8777),   # Asia: Mumbai
            (39.9042, 116.4074),  # Asia: Beijing
            (-23.5505, -46.6333), # South America: Sao Paulo
            (-26.2041, 28.0473),  # Africa: Johannesburg
            (6.5244, 3.3792),     # Africa: Lagos
            (-33.8688, 151.2093)  # Oceania: Sydney
        ]
        
        points = []
        np.random.seed(self.seed)
        points_per_hub = self.samples // len(hubs)
        remainder = self.samples % len(hubs)
        
        for i, (hub_lat, hub_lon) in enumerate(hubs):
            # Assign remainder points to the first hub
            n_points = points_per_hub + (remainder if i == 0 else 0)
            
            # Gaussian mathematical spread: standard deviation of 2.5 degrees roughly maps to a 250km sprawl cluster
            lats = np.random.normal(hub_lat, 2.5, n_points)
            lons = np.random.normal(hub_lon, 2.5, n_points)
            
            # Clamp geometrically out-of-bounds anomalies falling off the 90th parallels or 180 anti-meridian
            lats = np.clip(lats, -90.0, 90.0)
            lons = np.clip(lons, -180.0, 180.0)
            
            cluster_df = pd.DataFrame({'lat': lats, 'lon': lons})
            points.append(cluster_df)
            
        df = pd.concat(points, ignore_index=True)
        # Sequential IDs required for correct Relational JOINs across frameworks
        df['id'] = df.index
        return df

    def _generate_fibonacci_sphere(self) -> pd.DataFrame:
        print(f"  Generating {self.samples} Fibonacci points uniformly across the globe...")
        points = []
        phi = math.pi * (3. - math.sqrt(5.))
        for i in range(self.samples):
            y = 1 - (i / float(self.samples - 1)) * 2
            radius = math.sqrt(1 - y * y)
            theta = phi * i
            lat = math.degrees(math.asin(y))
            lon = math.degrees(math.atan2(math.sin(theta) * radius, math.cos(theta) * radius))
            points.append({'id': i, 'lat': lat, 'lon': lon})
        df = pd.DataFrame(points)
        return df

    def _load_overture_buildings(self) -> pd.DataFrame:
        from pathlib import Path
        project_root = Path(__file__).resolve().parents[3]
        data_dir = project_root / 'data' / 'overture'
        data_dir.mkdir(parents=True, exist_ok=True)
        
        overture_path = data_dir / f'overture_buildings_{self.samples}.parquet'
        
        print(f"  Loading {self.samples} Real-world Overture Building Centroids...")
        if not overture_path.exists():
            print("  Downloading Overture Maps Buildings directly from Amazon S3 (this happens once)...")
            self.con.execute("INSTALL httpfs; LOAD httpfs;")
            self.con.execute("SET s3_region = 'us-west-2';")
            
            # Divide the massive global download request into 5 tiny independent S3 streams
            # This completely destroys DuckDB's 40GB+ memory spike caused by global sorting operations.
            bboxes = [
                "bbox.ymin > 35 AND bbox.ymax < 60 AND bbox.xmin > -10 AND bbox.xmax < 30", # Europe
                "bbox.ymin > -35 AND bbox.ymax < 5 AND bbox.xmin > -80 AND bbox.xmax < -35", # South America
                "bbox.ymin > -35 AND bbox.ymax < 0 AND bbox.xmin > 10 AND bbox.xmax < 40", # Africa
                "bbox.ymin > -40 AND bbox.ymax < -10 AND bbox.xmin > 110 AND bbox.xmax < 155", # Australia
                "bbox.ymin > 5 AND bbox.ymax < 35 AND bbox.xmin > 65 AND bbox.xmax < 95" # Asia
            ]
            
            sub_limit = self.samples // len(bboxes)
            dfs = []
            
            for i, bbox in enumerate(bboxes):
                print(f"    -> Querying Amazon bucket for Region {i+1}...")
                query = f"""
                    SELECT 
                        CAST(ST_Y(ST_Centroid(geometry)) AS DOUBLE) AS lat, 
                        CAST(ST_X(ST_Centroid(geometry)) AS DOUBLE) AS lon, 
                        sources[1].dataset AS source_dataset
                    FROM read_parquet('s3://overturemaps-us-west-2/release/2026-03-18.0/theme=buildings/type=building/*', filename=true) 
                    WHERE {bbox}
                    LIMIT {sub_limit}
                """
                # Instantly dumps the stream to pandas, freeing the database RAM immediately
                hub_df = self.con.execute(query).df()
                dfs.append(hub_df)
                
            print("    -> S3 Downloads complete. Shuffling real-world global geometries into final index...")
            merged_df = pd.concat(dfs, ignore_index=True)
            # Shuffle strictly in python (Memory efficient) and assign IDs
            merged_df = merged_df.sample(frac=1, random_state=self.seed).reset_index(drop=True)
            merged_df['id'] = merged_df.index
            
            merged_df.to_parquet(overture_path)
            
        points_df = pd.read_parquet(overture_path)
        print(f"  Data Source Distribution:")
        print(points_df['source_dataset'].value_counts())
        return points_df


    def _load_study_areas(self) -> gpd.GeoDataFrame:
        import os
        import urllib.request
        import zipfile
        from pathlib import Path
        
        # Resolve project root dynamically (from src/dggs_benchmark/experiments/...)
        project_root = Path(__file__).resolve().parents[3]
        data_dir = project_root / 'data' / 'natural_earth'
        
        if self.scale == "micro":
            print("  Loading Local Natural Earth Urban Areas...")
            urban_dir = data_dir / 'urban'
            shpfilename = urban_dir / 'ne_10m_urban_areas.shp'
            
            if not shpfilename.exists():
                print("  Downloading Natural Earth 10m Urban Areas...")
                urban_dir.mkdir(parents=True, exist_ok=True)
                zip_path = urban_dir / 'ne_10m_urban_areas.zip'
                url = "https://naciscdn.org/naturalearth/10m/cultural/ne_10m_urban_areas.zip"
                urllib.request.urlretrieve(url, zip_path)
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(urban_dir)
                    
            world = gpd.read_file(shpfilename)
            # Find largest global urban extents by raw polygon area
            world['temp_area'] = world.geometry.area
            target_areas = world.sort_values(by='temp_area', ascending=False).head(5)
            target_areas['name'] = [f"Megacity_Zone_{i+1}" for i in range(5)]
            return target_areas
        elif self.scale == "macro-europe":
            print("  Loading Local Natural Earth Country Boundaries (EUROPE)...")
            shpfilename = data_dir / 'ne_50m_admin_0_countries.shp'
            
            if not shpfilename.exists():
                print("  Downloading Natural Earth 50m Admin Boundaries...")
                data_dir.mkdir(parents=True, exist_ok=True)
                zip_path = data_dir / 'ne_50m_admin_0_countries.zip'
                url = "https://naciscdn.org/naturalearth/50m/cultural/ne_50m_admin_0_countries.zip"
                urllib.request.urlretrieve(url, zip_path)
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(data_dir)
                    
            world = gpd.read_file(shpfilename)
            # Find dense overlapping R-Tree regions
            target_countries = world[world['ADMIN'].isin(['Germany', 'France', 'Italy', 'Spain', 'Poland', 'United Kingdom', 'Romania', 'Netherlands', 'Belgium', 'Czechia', 'Greece', 'Portugal', 'Sweden', 'Austria', 'Switzerland'])]
            target_countries = target_countries.rename(columns={'ADMIN': 'name'})
            return target_countries

        elif self.scale == "macro-10m":
            print("  Loading HIGH-RES Natural Earth 10m Country Boundaries...")
            highres_dir = data_dir / 'ne_10m'
            shpfilename = highres_dir / 'ne_10m_admin_0_countries.shp'
            if not shpfilename.exists():
                print("  Downloading Natural Earth 10m Admin Boundaries...")
                highres_dir.mkdir(parents=True, exist_ok=True)
                zip_path = highres_dir / 'ne_10m_admin_0_countries.zip'
                url = "https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_0_countries.zip"
                urllib.request.urlretrieve(url, zip_path)
                import zipfile
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(highres_dir)
            world = gpd.read_file(shpfilename)
            # Use same 5 target countries as macro, but with incredibly complex coastline vertices
            target_countries = world[world['ADMIN'].isin(['France', 'Brazil', 'South Africa', 'Australia', 'India'])]
            target_countries = target_countries.rename(columns={'ADMIN': 'name'})
            return target_countries

        else: # "macro"
            print("  Loading Local Natural Earth Country Boundaries...")
            shpfilename = data_dir / 'ne_50m_admin_0_countries.shp'
            
            if not shpfilename.exists():
                print("  Downloading Natural Earth 50m Admin Boundaries...")
                data_dir.mkdir(parents=True, exist_ok=True)
                zip_path = data_dir / 'ne_50m_admin_0_countries.zip'
                url = "https://naciscdn.org/naturalearth/50m/cultural/ne_50m_admin_0_countries.zip"
                urllib.request.urlretrieve(url, zip_path)
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(data_dir)
                    
            world = gpd.read_file(shpfilename)
            target_countries = world[world['ADMIN'].isin(['France', 'Brazil', 'South Africa', 'Australia', 'India'])]
            target_countries = target_countries.rename(columns={'ADMIN': 'name'})
            return target_countries

    def _fallback_polygon_covering(self, grid: BaseGrid, polygon: Polygon, res: int) -> List[str]:
        """
        A pure Python mathematically dense boundary tracer and interior rasterizer.
        Automatically tightens the sampling grid based on the DGGS Resolution level.
        """
        # 1. Heuristic resolution step (higher res = tighter mesh)
        # E.g., Res 2 => ~6 degrees apart. Res 6 => ~0.4 degrees apart.
        step_degrees = max(0.01, 15.0 / (1.6 ** res)) 
        
        cells = set()
        
        # 2. Perfect Boundary Tracing (Segmentize ensures no gaps along the coast)
        dense_poly = polygon.segmentize(step_degrees)
        for pt in dense_poly.exterior.coords:
            cells.add(grid.encode_point(pt[1], pt[0], res)) # (lat, lon)
            
        for interior in dense_poly.interiors:
            for pt in interior.coords:
                cells.add(grid.encode_point(pt[1], pt[0], res))
        
        # 3. Dense Interior Rasterization
        bounds = polygon.bounds
        lons = np.arange(bounds[0], bounds[2] + step_degrees, step_degrees)
        lats = np.arange(bounds[1], bounds[3] + step_degrees, step_degrees)
        if len(lons) > 1 and len(lats) > 1:
            lon_grid, lat_grid = np.meshgrid(lons, lats)
            pts = gpd.GeoSeries(gpd.points_from_xy(lon_grid.flatten(), lat_grid.flatten()))
            # Strict spatial filter to keep only points inside the country
            pts_inside = pts[pts.within(polygon)]
            
            for pt in pts_inside:
                cells.add(grid.encode_point(pt.y, pt.x, res))
                
        return list(cells)

    def run(self, resolutions_dict: Dict[str, List[int]]) -> pd.DataFrame:
        print(f"--- Running Relational Throughput Experiment ({self.samples} pts) [{self.scale.upper()} SCALE] ---")
        points_df = self._generate_points()
        countries = self._load_study_areas()
        
        # --- PHASE 0: VECTOR BASELINE ---
        print("\n  [Phase 0] Benchmarking Vector Baseline (ST_Intersects)...")
        self.con.execute("CREATE TABLE points AS SELECT * FROM points_df")
        self.con.execute("ALTER TABLE points ADD COLUMN geom GEOMETRY")
        self.con.execute("UPDATE points SET geom = ST_Point(lon, lat)")
        
        self.con.execute("CREATE TABLE study_area (name VARCHAR, geom GEOMETRY)")
        for _, row in countries.iterrows():
            geom = row.geometry
            if geom.is_empty: continue
            self.con.execute(f"INSERT INTO study_area VALUES (?, ST_GeomFromText(?))", 
                             [row['name'], geom.wkt])
        
        t0 = time.perf_counter()
        count_vec = self.con.execute("""
            SELECT count(*) 
            FROM points p, study_area s 
            WHERE ST_Intersects(p.geom, s.geom)
        """).fetchone()[0]
        vector_join_sec = time.perf_counter() - t0
        print(f"    Vector Join Speed: {vector_join_sec:.4f}s (Count: {count_vec})")

        results = []

        # --- PHASE 1: DGGS RESOLUTION SWEEP ---
        print("\n  [Phase 1] Benchmarking DGGS Scale Sweep...")
        for grid in self.grids:
            res_list = resolutions_dict.get(grid.name, [])
            for res in res_list:
                print(f"  -> Grid: {grid.name} | Resolution: {res}")
                
                # 1. Ingestion Tax (Encoding the Globe)
                t0 = time.perf_counter()
                try:
                    point_ids = points_df.apply(lambda row: grid.encode_point(row['lat'], row['lon'], res), axis=1).tolist()
                    ingestion_sec = time.perf_counter() - t0
                except Exception as e:
                    print(f"    [Error] Encoding failed: {e}")
                    continue
                
                # 2. Covering Speed (Chopping the Countries)
                t0 = time.perf_counter()
                try:
                    all_covering_cells = []
                    for _, row in countries.iterrows():
                        geom = row.geometry
                        polys = [geom] if type(geom) == Polygon else list(geom.geoms)
                        for poly in polys:
                            try:
                                cells = grid.get_covering(poly, res)
                                if len(cells) <= 1:
                                    cells = self._fallback_polygon_covering(grid, poly, res)
                            except Exception:
                                cells = self._fallback_polygon_covering(grid, poly, res)
                            
                            for c in set(cells):
                                all_covering_cells.append({'name': row['name'], 'cell_id': c})
                    covering_sec = time.perf_counter() - t0
                except Exception as e:
                    print(f"    [Warning] Covering failed: {e}")
                    continue
                
                # 3. Relational Reward (DuckDB Join)
                clean_name = grid.name.replace(' ', '_').replace('(', '').replace(')', '').replace(':', '_')
                try:
                    test_val = point_ids[0]
                    sql_type = "UBIGINT" if isinstance(test_val, int) else "VARCHAR"
                    
                    ids_df = pd.DataFrame({'id': points_df['id'], 'cell_id': point_ids})
                    self.con.execute(f"CREATE OR REPLACE TABLE p_{clean_name}_{res} AS SELECT id, CAST(cell_id AS {sql_type}) AS cell_id FROM ids_df")
                    
                    cov_df = pd.DataFrame(all_covering_cells)
                    if len(cov_df) == 0:
                        raise Exception("Covering generated 0 cells.")
                    self.con.execute(f"CREATE OR REPLACE TABLE c_{clean_name}_{res} AS SELECT name, CAST(cell_id AS {sql_type}) AS cell_id FROM cov_df")
                    
                    t0 = time.perf_counter()
                    count_dggs = self.con.execute(f"""
                        SELECT count(DISTINCT p.id) 
                        FROM p_{clean_name}_{res} p
                        JOIN c_{clean_name}_{res} c ON p.cell_id = c.cell_id
                    """).fetchone()[0]
                    join_sec = time.perf_counter() - t0
                    
                    print(f"    Encoding: {ingestion_sec:.4f}s | Covering: {covering_sec:.4f}s | Join: {join_sec:.4f}s")
                    print(f"    Matches: {count_dggs} (Accuracy vs Vector: {(count_dggs/max(1, count_vec))*100:.2f}%)")
                    
                    results.append({
                        "grid_name": grid.name,
                        "resolution": res,
                        "data_type": sql_type,
                        "ingestion_sec": ingestion_sec,
                        "covering_sec": covering_sec,
                        "join_sec": join_sec,
                        "total_sec": ingestion_sec + join_sec,
                        "count": count_dggs,
                        "vector_count": count_vec,
                        "accuracy_pct": (count_dggs / max(1, count_vec)) * 100
                    })
                    
                    if self.save_geometries:
                        import os
                        os.makedirs(self.output_dir, exist_ok=True)
                        gpkg_path = os.path.join(self.output_dir, f"visual_{clean_name}_{self.scale}_res{res}.gpkg")
                        print(f"    [Visuals] Exporting geometries to {gpkg_path}...")
                        
                        unique_cells = set(c['cell_id'] for c in all_covering_cells)
                        cell_polys = []
                        for cid in unique_cells:
                            try:
                                poly = grid.get_cell_polygon(cid)
                                if not poly.is_empty:
                                    cell_polys.append({'cell_id': str(cid), 'geometry': poly})
                            except Exception:
                                pass
                        
                        if cell_polys:
                            gpd.GeoDataFrame(cell_polys, geometry='geometry', crs="EPSG:4326").to_file(gpkg_path, layer="dggs_covering", driver="GPKG")
                        
                        pts_df = self.con.execute(f"""
                            SELECT DISTINCT p_df.id, p_df.lon, p_df.lat
                            FROM p_{clean_name}_{res} p
                            JOIN c_{clean_name}_{res} c ON p.cell_id = c.cell_id
                            JOIN points p_df ON p_df.id = p.id
                        """).df()
                        
                        if not pts_df.empty:
                            gpd.GeoDataFrame(pts_df, geometry=gpd.points_from_xy(pts_df.lon, pts_df.lat), crs="EPSG:4326").to_file(gpkg_path, layer="matched_points", driver="GPKG")
                            
                    # CRITICAL: Flush DuckDB memory pool to prevent 40GB+ RAM OOM errors!
                    self.con.execute(f"DROP TABLE p_{clean_name}_{res}")
                    self.con.execute(f"DROP TABLE c_{clean_name}_{res}")
                    import gc
                    gc.collect()
                            
                except Exception as e:
                    print(f"    [Error] Join failed: {e}")

        df_res = pd.DataFrame(results)
        return df_res
