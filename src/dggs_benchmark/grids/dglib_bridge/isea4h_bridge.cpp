/*
 * isea4h_bridge.cpp
 *
 * A thin C-ABI shared library wrapping DGGRID's dglib for ISEA4H operations.
 *
 * ISEA4H uses aperture 4, which means Z3_STRING (base-3) addressing is invalid.
 * Instead, we use DgZOrderStringRF with aperture=4 and its dedicated
 * Dg2WayZOrderStringConverter for Q2DI <-> ZOrderString conversion.
 *
 * Exposes three operations:
 *   1. isea4h_encode_points_batch()  — batch GEO → ZOrderString
 *   2. isea4h_get_cell_polygon()     — cell_id → WGS84 vertex list
 *   3. isea4h_get_k_ring()           — cell_id → neighbor list
 *
 * Build: see build_isea4h.sh in this directory
 * Link:  libdglib.a, libdgaplib.a, libproj4lib.a, libshapelib.a (all static)
 */

#include <string>
#include <vector>
#include <cstring>
#include <cstdlib>
#include <stdexcept>

// --- dglib headers ---
#include <dglib/DgRFNetwork.h>
#include <dglib/DgGeoSphRF.h>
#include <dglib/DgIDGGS4H.h>
#include <dglib/DgIDGG.h>
#include <dglib/DgLocation.h>
#include <dglib/DgPolygon.h>
#include <dglib/DgZOrderStringRF.h>
#include <dglib/DgConverter.h>

// ============================================================
// Module-level state (singleton per resolution)
// ============================================================

struct GridState4H {
    int resolution;
    DgRFNetwork*         net;
    const DgGeoSphRF*    geoRF;
    const DgIDGGS4H*     idggs;
    const DgIDGG*        dgg;
    DgZOrderStringRF*    zorf;   // ZOrder string RF for aperture 4

    GridState4H()
        : resolution(-1), net(nullptr), geoRF(nullptr),
          idggs(nullptr), dgg(nullptr), zorf(nullptr) {}

    ~GridState4H() {
        delete net;
    }
};

static GridState4H* g_state = nullptr;

static GridState4H* get_or_create_state(int resolution) {
    if (g_state && g_state->resolution == resolution) {
        return g_state;
    }
    delete g_state;
    g_state = nullptr;

    GridState4H* s = new GridState4H();
    s->resolution = resolution;

    // Standard ISEA icosahedron placement (same as DGGRID default)
    DgGeoCoord vert0(11.25L, 58.28252559L, false); // lon, lat, isRadians=false
    long double azimuth = 0.0L;

    s->net   = new DgRFNetwork();
    s->geoRF = DgGeoSphRF::makeRF(*s->net, "GS0");

    // Create ISEA4H DGGS up to resolution+1 levels
    s->idggs = DgIDGGS4H::makeRF(*s->net, *s->geoRF, vert0, azimuth,
                                  resolution + 1, "ISEA4H", "ISEA");
    s->dgg   = &(s->idggs->idgg(resolution));

    // Create ZOrderString RF with aperture=4 and register the Q2DI<->ZOrderString converter
    s->zorf  = DgZOrderStringRF::makeRF(*s->net, "ZOrderString", resolution, 4);
    new Dg2WayZOrderStringConverter(
        dynamic_cast<const DgRF<DgQ2DICoord, long long int>&>(*s->dgg),
        *s->zorf
    );

    g_state = s;
    return s;
}

// ============================================================
// C ABI
// ============================================================

extern "C" {

/**
 * isea4h_encode_points_batch:
 *   lats, lons: flat arrays of length n_points
 *   resolution: ISEA4H resolution (e.g. 12)
 *   out_ids: caller-allocated array of (char*) pointers
 *
 *   Returns 0 on success, -1 on error.
 */
int isea4h_encode_points_batch(const double* lats, const double* lons,
                               int n_points, int resolution,
                               char** out_ids) {
    try {
        GridState4H* s = get_or_create_state(resolution);

        for (int i = 0; i < n_points; ++i) {
            DgGeoCoord geo(lons[i], lats[i], false);
            DgLocation* loc = s->geoRF->makeLocation(geo);

            // GEO → Q2DI
            s->dgg->convert(loc);
            // Q2DI → ZOrderString
            s->zorf->convert(loc);

            std::string addr = s->zorf->toAddressString(*loc);

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
 * isea4h_get_cell_polygon:
 *   cell_id_str: ZOrderString cell ID
 *   resolution:  must match the resolution the ID was encoded at
 *   out_lons, out_lats: caller-allocated arrays of size max_verts
 *   out_n_verts: filled with actual vertex count
 *   pts_per_edge: densification (1 = bare corners only)
 *
 *   Returns 0 on success, -1 on error.
 */
int isea4h_get_cell_polygon(const char* cell_id_str, int resolution,
                            double* out_lons, double* out_lats,
                            int* out_n_verts, int pts_per_edge) {
    try {
        GridState4H* s = get_or_create_state(resolution);

        std::string cell_id_stdstr(cell_id_str);
        DgZOrderStringCoord zcoord(cell_id_stdstr);
        DgLocation* loc = s->zorf->makeLocation(zcoord);

        // ZOrderString → Q2DI
        s->dgg->convert(loc);

        // Get polygon vertices in Q2DI space, then convert to GEO
        DgPolygon verts;
        s->dgg->setVertices(*loc, verts, pts_per_edge);
        s->geoRF->convert(&verts);

        int n = (int)verts.size();
        *out_n_verts = n;
        for (int i = 0; i < n; ++i) {
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
 * isea4h_get_k_ring:
 *   cell_id_str: ZOrderString cell ID
 *   resolution: ISEA4H resolution
 *   k: k-ring radius (currently only k=1 is supported)
 *   out_ids: caller-allocated array of char* (size max_out)
 *   out_count: number of neighbors returned
 *   max_out: capacity of out_ids
 *
 *   Returns 0 on success, -1 on error, -2 if k > 1.
 */
int isea4h_get_k_ring(const char* cell_id_str, int resolution, int k,
                      char** out_ids, int* out_count, int max_out) {
    if (k > 1) return -2;
    try {
        GridState4H* s = get_or_create_state(resolution);

        std::string cell_id_stdstr(cell_id_str);
        DgZOrderStringCoord zcoord(cell_id_stdstr);
        DgLocation* loc = s->zorf->makeLocation(zcoord);

        // ZOrderString → Q2DI
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
            DgLocation nloc = neighbors[i];
            // Q2DI → ZOrderString
            s->zorf->convert(&nloc);
            std::string addr = s->zorf->toAddressString(nloc);

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
 * isea4h_free_string_array: free the char* pointers allocated by encode/k_ring
 */
void isea4h_free_string_array(char** ids, int n) {
    for (int i = 0; i < n; ++i) {
        free(ids[i]);
    }
}

/**
 * isea4h_reset_grid_state: tear down the cached grid state
 */
void isea4h_reset_grid_state() {
    delete g_state;
    g_state = nullptr;
}

} // extern "C"
