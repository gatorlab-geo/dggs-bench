#!/bin/bash
# build.sh — Build isea3h_bridge.so against the pre-compiled dglib
# Run from /tmp/dglib_bridge/
set -e

DGGRID_SRC=/tmp/DGGRID_src/src
BUILD_DIR=$DGGRID_SRC/build_pic

INCLUDE_DIR=$DGGRID_SRC/src/lib/dglib/include
LIB_DGLIB=$BUILD_DIR/src/lib/dglib/libdglib.a
LIB_DGAP=$BUILD_DIR/src/lib/dgaplib/libdgaplib.a
LIB_PROJ=$BUILD_DIR/src/lib/proj4lib/libproj4lib.a
LIB_SHAPE=$BUILD_DIR/src/lib/shapelib/libshapelib.a

echo "Building isea3h_bridge.so..."
g++ -std=c++14 -O2 -fPIC -shared \
    -I"$INCLUDE_DIR" \
    isea3h_bridge.cpp \
    -o isea3h_bridge.so \
    -Wl,--whole-archive \
    "$LIB_DGLIB" "$LIB_DGAP" "$LIB_PROJ" "$LIB_SHAPE" \
    -Wl,--no-whole-archive \
    -lstdc++ -lm

echo "Done: $(ls -lh isea3h_bridge.so)"
