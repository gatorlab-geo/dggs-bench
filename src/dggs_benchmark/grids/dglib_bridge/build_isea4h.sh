#!/bin/bash
# build_isea4h.sh — Build isea4h_bridge.so against the pre-compiled dglib (v8.43)
set -e

DGGRID_SRC=${DGGRID_SRC:-/tmp/DGGRID_src}
# Falls back to /tmp/DGGRID if _src doesn't exist
if [ ! -d "$DGGRID_SRC" ] && [ -d "/tmp/DGGRID" ]; then
    DGGRID_SRC=/tmp/DGGRID
fi
BUILD_DIR=$DGGRID_SRC/build_pic

INCLUDE_DIR=$DGGRID_SRC/src/lib/dglib/include
LIB_DGLIB=$BUILD_DIR/src/lib/dglib/libdglib.a
LIB_DGAP=$BUILD_DIR/src/lib/dgaplib/libdgaplib.a
LIB_PROJ=$BUILD_DIR/src/lib/proj4lib/libproj4lib.a
LIB_SHAPE=$BUILD_DIR/src/lib/shapelib/libshapelib.a

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Building isea4h_bridge.so..."
g++ -std=c++14 -O2 -fPIC -shared \
    -I"$INCLUDE_DIR" \
    "$SCRIPT_DIR/isea4h_bridge.cpp" \
    -o "$SCRIPT_DIR/isea4h_bridge.so" \
    -Wl,--whole-archive \
    "$LIB_DGLIB" "$LIB_DGAP" "$LIB_PROJ" "$LIB_SHAPE" \
    -Wl,--no-whole-archive \
    -lstdc++ -lm

echo "Done: $(ls -lh "$SCRIPT_DIR/isea4h_bridge.so")"
