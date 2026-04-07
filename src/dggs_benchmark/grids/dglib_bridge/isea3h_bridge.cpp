/*
 * isea3h_bridge.cpp
 *
 * A thin C-ABI shared library wrapping DGGRID's dglib for ISEA3H operations.
 * Exposes only two operations needed for dggs-bench Experiment 1:
 *   1. encode_points()  — batch GEO → Z3_STRING (via Q2DI → DgZ3StringRF)
 *   2. get_polygon()    — cell_id → WGS84 vertex list
 *
 * Build: see build.sh in this directory
 * Link:  libdglib.a, libdgaplib.a, libproj4lib.a, libshapelib.a (all static, from DGGRID build)
 * Note:  No GDAL or system PROJ needed — dglib bundles its own proj4lib.
 */

#include <string>
#include <vector>
#include <cstring>
#include <cstdlib>
#include <stdexcept>

// --- dglib headers ---
#include <dglib/DgRFNetwork.h>
#include <dglib/DgGeoSphRF.h>
#include <dglib/DgIDGGS3H.h>
#include <dglib/DgIDGG.h>
#include <dglib/DgLocation.h>
#include <dglib/DgPolygon.h>
#include <dglib/DgZ3StringRF.h>
#include <dglib/DgConverter.h>

// ============================================================
// Module-level state (singleton per resolution)
// ============================================================

struct GridState {
    int resolution;
    DgRFNetwork*    net;
    const DgGeoSphRF*  geoRF;
    const DgIDGGS3H*   idggs;
    const DgIDGG*      dgg;
    DgZ3StringRF*      z3rf;
    // Converter: Q2DI -> Z3String is registered on the network automatically
    // We use dgg->convert() to get Q2DI, then network converts to z3rf

    GridState()
        : resolution(-1), net(nullptr), geoRF(nullptr),
          idggs(nullptr), dgg(nullptr), z3rf(nullptr) {}

    ~GridState() {
        // DgRFNetwork owns all RFs — deleting net cleans up everything
        delete net;
    }
};

static GridState* g_state = nullptr;

static GridState* get_or_create_state(int resolution) {
    if (g_state && g_state->resolution == resolution) {
        return g_state;
    }
    delete g_state;
    g_state = nullptr;

    GridState* s = new GridState();
    s->resolution = resolution;

    // Standard ISEA3H icosahedron placement (same as DGGRID default)
    DgGeoCoord vert0(11.25L, 58.28252559L, false); // lon, lat, isRadians=false
    long double azimuth = 0.0L;

    s->net   = new DgRFNetwork();
    s->geoRF = DgGeoSphRF::makeRF(*s->net, "GS0");

    // Create ISEA3H DGGS up to resolution+1 levels
    s->idggs = DgIDGGS3H::makeRF(*s->net, *s->geoRF, vert0, azimuth,
                                  resolution + 1, "ISEA3H", "ISEA");
    s->dgg   = &(s->idggs->idgg(resolution));

    // Create Z3String RF and register the Q2DI→Z3String converter
    s->z3rf  = DgZ3StringRF::makeRF(*s->net, "Z3String", resolution);
    // The Dg2WayZ3StringConverter registers itself on the network
    new Dg2WayZ3StringConverter(
        dynamic_cast<const DgRF<DgQ2DICoord, long long int>&>(*s->dgg),
        *s->z3rf
    );

    g_state = s;
    return s;
}

// ============================================================
// C ABI
// ============================================================

extern "C" {

/**
 * encode_points_batch:
 *   lats, lons: flat arrays of length n_points
 *   resolution: ISEA3H resolution (e.g. 16)
 *   out_ids: caller-allocated array of (char*) pointers; bridge will allocate
 *            each string with malloc(). Caller must call free_string_array().
 *
 *   Returns 0 on success, -1 on error.
 */
int encode_points_batch(const double* lats, const double* lons,
                        int n_points, int resolution,
                        char** out_ids) {
    try {
        GridState* s = get_or_create_state(resolution);

        for (int i = 0; i < n_points; ++i) {
            // Build a GEO location
            DgGeoCoord geo(lons[i], lats[i], false); // lon first, then lat; isRadians=false
            DgLocation* loc = s->geoRF->makeLocation(geo);

            // Convert GEO → Q2DI (determines which ISEA3H cell)
            s->dgg->convert(loc);

            // Convert Q2DI → Z3String via the registered network converter
            s->z3rf->convert(loc);

            // Extract the string
            std::string id = s->z3rf->toString(*loc);
            // toString gives "Z3String{05012...}" — extract inner value
            // Actually use toAddressString for just the bare address
            std::string addr = s->z3rf->toAddressString(*loc);

            out_ids[i] = (char*)malloc(addr.size() + 1);
            memcpy(out_ids[i], addr.c_str(), addr.size() + 1);

            delete loc;
        }
        return 0;
    } catch (const std::exception& e) {
        return -1;
    } catch (...) {
        return -1;
    }
}

/**
 * get_cell_polygon:
 *   cell_id_str: Z3String cell ID (e.g. "0501212021102022")
 *   resolution:  must match the resolution the ID was encoded at
 *   out_lons, out_lats: caller-allocated arrays of size max_verts
 *   out_n_verts: filled with actual vertex count
 *   pts_per_edge: densification (3 = ~6 pts/hex edge; use 1 for bare corners)
 *
 *   Returns 0 on success, -1 on error.
 */
int get_cell_polygon(const char* cell_id_str, int resolution,
                     double* out_lons, double* out_lats,
                     int* out_n_verts, int pts_per_edge) {
    try {
        GridState* s = get_or_create_state(resolution);

        // Build a Z3String location — use intermediate variable to avoid vexing-parse
        std::string cell_id_stdstr(cell_id_str);
        DgZ3StringCoord z3coord{cell_id_stdstr};
        DgLocation* loc = s->z3rf->makeLocation(z3coord);

        // Convert Z3String → Q2DI
        s->dgg->convert(loc);

        // Get polygon vertices in Q2DI space, then convert to GEO
        DgPolygon verts;
        s->dgg->setVertices(*loc, verts, pts_per_edge);
        s->geoRF->convert(&verts);  // convert all vertices to GEO

        int n = (int)verts.size();
        *out_n_verts = n;
        for (int i = 0; i < n; ++i) {
            // verts[i] returns a DgLocation by index
            const DgLocation& vloc = verts[i];
            const DgGeoCoord* gc = s->geoRF->getAddress(vloc);
            out_lons[i] = (double)gc->lonDegs();
            out_lats[i] = (double)gc->latDegs();
        }

        delete loc;
        return 0;
    } catch (const std::exception& e) {
        return -1;
    } catch (...) {
        return -1;
    }
}

/**
 * get_k_ring:
 *   cell_id_str: Z3String cell ID
 *   resolution: ISEA3H resolution
 *   k: k-ring radius (currently only k=1 is supported)
 *   out_ids: caller-allocated array of char* (size max_out)
 *   out_count: number of neighbors returned
 *   max_out: capacity of out_ids
 *
 *   Returns 0 on success, -1 on error.
 */
int get_k_ring(const char* cell_id_str, int resolution, int k,
               char** out_ids, int* out_count, int max_out) {
    if (k > 1) return -2; // Not implemented for k > 1 yet
    try {
        GridState* s = get_or_create_state(resolution);

        std::string cell_id_stdstr(cell_id_str);
        DgZ3StringCoord z3coord{cell_id_stdstr};
        DgLocation* loc = s->z3rf->makeLocation(z3coord);

        s->dgg->convert(loc);
        const DgQ2DICoord* center_q2di = dynamic_cast<const DgQ2DICoord*>(s->dgg->getAddress(*loc));
        if (!center_q2di) {
            delete loc;
            return -1;
        }

        DgLocVector neighbors(*(s->dgg));
        s->dgg->setAddNeighbors(*center_q2di, neighbors);

        int count = 0;
        for (size_t i = 0; i < neighbors.size() && count < max_out; i++) {
            DgLocation nloc = neighbors[i]; // copy the location so we can mutate it with convert
            s->z3rf->convert(&nloc);
            std::string addr = s->z3rf->toAddressString(nloc);

            out_ids[count] = (char*)malloc(addr.size() + 1);
            memcpy(out_ids[count], addr.c_str(), addr.size() + 1);
            count++;
        }

        *out_count = count;
        delete loc;
        return 0;
    } catch (...) {
        return -1;
    }
}

/**
 * free_string_array: free the char* pointers allocated by encode_points_batch
 */
void free_string_array(char** ids, int n) {
    for (int i = 0; i < n; ++i) {
        free(ids[i]);
    }
}

/**
 * reset_grid_state: tear down the cached grid (call when changing resolution)
 */
void reset_grid_state() {
    delete g_state;
    g_state = nullptr;
}

} // extern "C"
