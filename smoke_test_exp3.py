from dggs_benchmark.experiments.relational_throughput import RelationalThroughputExperiment
from dggs_benchmark.grids.h3_grid import H3Grid
from dggs_benchmark.grids.s2_grid import S2Grid
import pandas as pd

# Test with scale sweep: e.g. H3 from level 2 (coarse) to level 6 (dense)
grids = [H3Grid(), S2Grid()]
resolutions = {
    "H3 (Uber)": [2, 4, 6],
    "S2 Geometry (Google)": [5, 9, 13]
}

experiment = RelationalThroughputExperiment(grids=grids, samples=50000)
results = experiment.run(resolutions)

print("\n==== RELATIONAL THROUGHPUT SWEEP ====")
pd.set_option('display.max_columns', None)
print(results)
