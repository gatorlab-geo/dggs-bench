import sys, os, resource, math, random
from shapely.geometry.polygon import orient
from shapely import segmentize
import antimeridian

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from dggs_benchmark.grids.rhealpix_grid import RHEALPixGrid

def _generate_fibonacci_sphere(samples, seed=42):
    points = []
    phi = math.pi * (3. - math.sqrt(5.))
    for i in range(samples):
        y = 1 - (i / float(samples - 1)) * 2
        radius = math.sqrt(1 - y * y)
        theta = phi * i
        lat = math.degrees(math.asin(y))
        lon = math.degrees(math.atan2(math.sin(theta)*radius, math.cos(theta)*radius))
        points.append((lat, lon))
    return points

def main():
    points = _generate_fibonacci_sphere(100000)
    grid = RHEALPixGrid()
    seen_cells = set()
    
    n_processed = 0
    max_memory = 0
    print("Starting profiling ...")
    for lat, lon in points:
        cell_id = grid.encode_point(lat, lon, 9)
        if cell_id not in seen_cells:
            raw_polygon = grid.get_cell_polygon(cell_id)
            try:
                oriented_poly = orient(raw_polygon, sign=1.0)
                fixed_poly = antimeridian.fix_polygon(oriented_poly)
                polygon = segmentize(fixed_poly, max_segment_length=0.005)
            except Exception:
                polygon = segmentize(raw_polygon, max_segment_length=0.005)
            seen_cells.add(cell_id)
            if len(seen_cells) % 5000 == 0:
                mem_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
                print(f"Unique: {len(seen_cells)}, Mem: {mem_mb:.1f} MB")
                if mem_mb > max_memory: max_memory = mem_mb
    print(f"Done. Max mem: {max_memory:.1f} MB")

if __name__ == "__main__":
    main()
