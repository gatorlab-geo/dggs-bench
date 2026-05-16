#!/usr/bin/env python3
"""
Generate paper figures from dggs-bench release datasets.

This script reproduces the figures from the ACM TSAS 2026 paper:
  "How Do Discrete Global Grid Systems Actually Perform?
   A Systematic Benchmark Across Geometry, Computation and Relational Joins"

It reads from the pre-built release parquets and generates publication-quality
PNG and PDF figures. By default it uses all grids present in the dataset.

Usage:
    # Generate all figures from the release dataset
    python generate_paper_figures.py

    # Specify a custom data directory and output directory
    python generate_paper_figures.py --data-dir path/to/release --output-dir path/to/figures

    # Generate figures for a subset of grids only
    python generate_paper_figures.py --grids "H3 (Uber),S2 Geometry (Google)"

Requirements:
    pip install pandas matplotlib seaborn cartopy numpy
"""

import argparse
import math
import os
import sys

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import seaborn as sns

# ==========================================================================
# Color Palette — 11 grids, grouped by tier
# ==========================================================================
# T1: Industry DGGS (mature, widely adopted)
# T2: Academic DGGS (equal-area, research-grade)
# T3: Legacy Planar (traditional map projection baselines)

GRID_COLORS = {
    # T1: Industry DGGS
    'H3 (Uber)':                    '#1f77b4',
    'S2 Geometry (Google)':         '#ff7f0e',
    # T2: Academic DGGS
    'rHEALPix (Equal Area Square)': '#d62728',
    'ISEA4H (Aperture 4 Hexagons)': '#9467bd',
    'ISEA3H (Aperture 3 Hexagons)': '#17becf',
    'A5 (Pentagon / Dodecahedron)': '#2ca02c',
    'QTM (Triangles)':              '#e377c2',
    # T3: Legacy Planar
    'Geohash':                      '#8c564b',
    'XYZ Tiles (WMTS / Slippy Map)':'#7f7f7f',
    'Web Mercator (EPSG:3857)':     '#bcbd22',
    'UTM (Universal Transverse Mercator)': '#ff9896',
}

GRID_SHORT = {
    'H3 (Uber)':                    'H3',
    'S2 Geometry (Google)':         'S2',
    'rHEALPix (Equal Area Square)': 'rHEALPix',
    'ISEA4H (Aperture 4 Hexagons)': 'ISEA4H',
    'ISEA3H (Aperture 3 Hexagons)': 'ISEA3H',
    'A5 (Pentagon / Dodecahedron)': 'A5',
    'QTM (Triangles)':              'QTM',
    'Geohash':                      'Geohash',
    'XYZ Tiles (WMTS / Slippy Map)':'XYZ Tiles',
    'Web Mercator (EPSG:3857)':     'Mercator',
    'UTM (Universal Transverse Mercator)': 'UTM',
}

# Canonical display ordering
GRID_ORDER = [
    'H3 (Uber)',
    'S2 Geometry (Google)',
    'rHEALPix (Equal Area Square)',
    'ISEA4H (Aperture 4 Hexagons)',
    'ISEA3H (Aperture 3 Hexagons)',
    'A5 (Pentagon / Dodecahedron)',
    'QTM (Triangles)',
    'Geohash',
    'XYZ Tiles (WMTS / Slippy Map)',
    'Web Mercator (EPSG:3857)',
    'UTM (Universal Transverse Mercator)',
]


def setup_plot_style():
    """Configure matplotlib for publication-quality output."""
    plt.rcParams['figure.dpi'] = 300
    plt.rcParams['savefig.dpi'] = 300
    plt.rcParams['font.family'] = 'sans-serif'
    plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'Helvetica']
    plt.rcParams['axes.linewidth'] = 0.8
    plt.rcParams['xtick.major.width'] = 0.6
    plt.rcParams['ytick.major.width'] = 0.6


def save_figure(fig, fig_dir, name):
    """Save figure as both PNG and PDF."""
    fig.savefig(os.path.join(fig_dir, f'{name}.png'), bbox_inches='tight', dpi=300)
    fig.savefig(os.path.join(fig_dir, f'{name}.pdf'), bbox_inches='tight')
    plt.close(fig)
    print(f'  ✓ Saved: {name}.png / .pdf')


# ==========================================================================
# Figure Generators
# ==========================================================================

def fig_area_angular_profiles(df_exp1, grid_order, fig_dir):
    """
    Meridian & Equatorial Profiles — Area and Angular Deviation.
    2x2 grid: (Lat × Area, Lat × Angular, Lon × Area, Lon × Angular)
    """
    print('Generating: area_angular_profiles...')
    plot_df = df_exp1.copy()

    present_grids = [g for g in grid_order if g in plot_df['grid_name'].unique()]
    palette = {g: GRID_COLORS.get(g, '#333333') for g in present_grids}

    plot_df['norm_area'] = plot_df.groupby('grid_name')['area_m2'].transform(
        lambda x: x / x.mean()
    )
    plot_df['lat_bin'] = plot_df['center_lat'].round()
    plot_df['lon_bin'] = plot_df['center_lon'].round()

    fig, axs = plt.subplots(2, 2, figsize=(10, 10))

    # Top-left: Area vs Latitude
    sns.lineplot(
        data=plot_df, y='lat_bin', x='norm_area', hue='grid_name', orient='y',
        palette=palette, hue_order=present_grids, linewidth=1.2, alpha=0.85,
        errorbar=None, ax=axs[0, 0], legend=False
    )
    axs[0, 0].set_ylabel('Latitude (°)', fontsize=10)
    axs[0, 0].set_xlabel('Normalized Area (ratio to grid mean)', fontsize=10)
    axs[0, 0].set_title('A) Area Ratio vs Latitude', fontsize=11, fontweight='bold')
    axs[0, 0].axvline(1.0, color='black', linestyle='--', linewidth=0.8, alpha=0.4)

    # Top-right: Angular Deviation vs Latitude
    sns.lineplot(
        data=plot_df, y='lat_bin', x='angular_deviation', hue='grid_name', orient='y',
        palette=palette, hue_order=present_grids, linewidth=1.2, alpha=0.85,
        errorbar=None, ax=axs[0, 1], legend=False
    )
    axs[0, 1].set_ylabel('')
    axs[0, 1].set_xlabel('Angular Deviation (°)', fontsize=10)
    axs[0, 1].set_title('B) Angular Deviation vs Latitude', fontsize=11, fontweight='bold')

    # Bottom-left: Area vs Longitude
    sns.lineplot(
        data=plot_df, x='lon_bin', y='norm_area', hue='grid_name',
        palette=palette, hue_order=present_grids, linewidth=1.2, alpha=0.85,
        errorbar=None, ax=axs[1, 0], legend=False
    )
    axs[1, 0].set_xlabel('Longitude (°)', fontsize=10)
    axs[1, 0].set_ylabel('Normalized Area (ratio to grid mean)', fontsize=10)
    axs[1, 0].set_title('C) Area Ratio vs Longitude', fontsize=11, fontweight='bold')
    axs[1, 0].axhline(1.0, color='black', linestyle='--', linewidth=0.8, alpha=0.4)

    # Bottom-right: Angular Deviation vs Longitude
    sns.lineplot(
        data=plot_df, x='lon_bin', y='angular_deviation', hue='grid_name',
        palette=palette, hue_order=present_grids, linewidth=1.2, alpha=0.85,
        errorbar=None, ax=axs[1, 1], legend=False
    )
    axs[1, 1].set_xlabel('Longitude (°)', fontsize=10)
    axs[1, 1].set_ylabel('Angular Deviation (°)', fontsize=10)
    axs[1, 1].set_title('D) Angular Deviation vs Longitude', fontsize=11, fontweight='bold')

    # Shared legend at bottom
    short_labels = [GRID_SHORT.get(g, g) for g in present_grids]
    handles = [plt.Line2D([0], [0], color=palette[g], linewidth=2) for g in present_grids]
    fig.legend(handles, short_labels, loc='lower center', ncol=min(len(present_grids), 6),
               fontsize=9, frameon=True, edgecolor='#cccccc', bbox_to_anchor=(0.5, -0.02))

    plt.tight_layout(rect=[0, 0.04, 1, 1])
    save_figure(fig, fig_dir, 'area_angular_profiles')


def fig_globe_area_heatmap(df_exp1, grid_order, fig_dir):
    """
    Orthographic Globe Projections — Area Distortion Heatmaps.
    One globe per grid showing spatial distribution of area ratio.
    """
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature
    from matplotlib.colors import TwoSlopeNorm

    print('Generating: globe_area_distortion...')
    target_grids = [g for g in grid_order if g in df_exp1['grid_name'].unique()]
    n_grids = len(target_grids)
    n_cols = min(3, n_grids)
    n_rows = math.ceil(n_grids / n_cols)

    fig, axes = plt.subplots(n_rows, n_cols, figsize=(3.5 * n_cols, 3.5 * n_rows + 1),
                             subplot_kw={'projection': ccrs.Orthographic(0, 20)})
    if n_rows == 1 and n_cols == 1:
        axes = [[axes]]
    elif n_rows == 1:
        axes = [axes]
    axes_flat = np.array(axes).flatten()

    norm = TwoSlopeNorm(vmin=0.6, vcenter=1.0, vmax=1.4)

    for idx, grid_name in enumerate(target_grids):
        ax = axes_flat[idx]
        ax.set_global()
        ax.add_feature(cfeature.COASTLINE, linewidth=0.3, alpha=0.4)

        gdf = df_exp1[df_exp1['grid_name'] == grid_name].copy()
        gdf['norm_area'] = gdf['area_m2'] / gdf['area_m2'].mean()

        sc = ax.scatter(
            gdf['center_lon'], gdf['center_lat'],
            c=gdf['norm_area'], cmap='RdBu_r', norm=norm,
            s=1.5, alpha=0.6, transform=ccrs.PlateCarree(), zorder=5
        )
        ax.set_title(GRID_SHORT.get(grid_name, grid_name), fontsize=9, fontweight='bold', pad=2)

    for idx in range(n_grids, len(axes_flat)):
        axes_flat[idx].set_visible(False)

    plt.subplots_adjust(hspace=0.3)
    cbar_ax = fig.add_axes([0.15, 0.05, 0.7, 0.03])
    cbar = fig.colorbar(sc, cax=cbar_ax, orientation='horizontal')
    cbar.set_label('Normalized Area (ratio to grid mean)', fontsize=9)
    cbar.ax.tick_params(labelsize=8)

    plt.suptitle('Geometric Distortion — Global Area Ratio', fontsize=12, fontweight='bold', y=0.98)
    save_figure(fig, fig_dir, 'globe_area_distortion')


def fig_globe_angular_heatmap(df_exp1, grid_order, fig_dir):
    """
    Orthographic Globe Projections — Angular Distortion Heatmaps.
    One globe per grid showing spatial distribution of angular deviation.
    """
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature
    from matplotlib.colors import Normalize

    print('Generating: globe_angular_distortion...')
    target_grids = [g for g in grid_order if g in df_exp1['grid_name'].unique()]
    n_grids = len(target_grids)
    n_cols = min(3, n_grids)
    n_rows = math.ceil(n_grids / n_cols)

    fig, axes = plt.subplots(n_rows, n_cols, figsize=(3.5 * n_cols, 3.5 * n_rows + 1),
                             subplot_kw={'projection': ccrs.Orthographic(0, 20)})
    if n_rows == 1 and n_cols == 1:
        axes = [[axes]]
    elif n_rows == 1:
        axes = [axes]
    axes_flat = np.array(axes).flatten()

    norm = Normalize(vmin=0, vmax=35)

    lon_equator = np.linspace(-180, 180, 1000)
    lat_equator = np.zeros(1000)
    lat_prime = np.linspace(-90, 90, 1000)
    lon_prime = np.zeros(1000)

    for idx, grid_name in enumerate(target_grids):
        ax = axes_flat[idx]
        ax.set_global()
        ax.add_feature(cfeature.COASTLINE, linewidth=0.3, alpha=0.4)

        ax.plot(lon_equator, lat_equator, color='black', linestyle='--', linewidth=0.8,
                alpha=0.6, transform=ccrs.Geodetic(), zorder=10)
        ax.plot(lon_prime, lat_prime, color='black', linestyle='--', linewidth=0.8,
                alpha=0.6, transform=ccrs.Geodetic(), zorder=10)

        gdf = df_exp1[df_exp1['grid_name'] == grid_name].copy()
        sc = ax.scatter(
            gdf['center_lon'], gdf['center_lat'],
            c=gdf['angular_deviation'], cmap='RdYlBu_r', norm=norm,
            s=1.5, alpha=0.6, transform=ccrs.PlateCarree(), zorder=5
        )
        ax.set_title(GRID_SHORT.get(grid_name, grid_name), fontsize=9, fontweight='bold', pad=2)

    for idx in range(n_grids, len(axes_flat)):
        axes_flat[idx].set_visible(False)

    plt.subplots_adjust(hspace=0.3)
    cbar_ax = fig.add_axes([0.15, 0.05, 0.7, 0.03])
    cbar = fig.colorbar(sc, cax=cbar_ax, orientation='horizontal')
    cbar.set_label('Angular Deviation (°)', fontsize=9)
    cbar.ax.tick_params(labelsize=8)

    plt.suptitle('Geometric Distortion — Angular Deviation', fontsize=12, fontweight='bold', y=0.98)
    save_figure(fig, fig_dir, 'globe_angular_distortion')


def fig_topological_resilience(df_exp2, grid_order, fig_dir):
    """
    Topological Resilience — Latency and Spacing bar plots.
    1x2 grid showing encoding latency and neighbor spacing variance by region.
    """
    print('Generating: topological_resilience...')
    plot_df = df_exp2[df_exp2['success'] == True].copy()
    plot_df['grid_short'] = plot_df['grid_name'].map(GRID_SHORT)
    plot_df['latency_us'] = plot_df['latency_sec'] * 1e6

    present_short = [GRID_SHORT[g] for g in grid_order if g in plot_df['grid_name'].unique()]
    case_palette = sns.color_palette("muted")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    sns.barplot(
        data=plot_df, x='grid_short', y='latency_us', hue='point_type',
        order=present_short,
        errorbar='ci', capsize=0.05, err_kws={'linewidth': 1},
        edgecolor='gray', linewidth=0.5, ax=ax1, palette=case_palette
    )
    ax1.set_title('A) Encoding Latency', fontsize=12, fontweight='bold')
    ax1.set_ylabel('CPU Execution Time (µs)', fontsize=10)
    ax1.set_xlabel('')
    ax1.tick_params(axis='x', rotation=30, labelsize=9)
    ax1.set_yscale('log')
    ax1.legend_.remove()

    sns.barplot(
        data=plot_df, x='grid_short', y='spacing_std_m', hue='point_type',
        order=present_short,
        errorbar='ci', capsize=0.05, err_kws={'linewidth': 1},
        edgecolor='gray', linewidth=0.5, ax=ax2, palette=case_palette
    )
    ax2.set_title('B) Topological Neighbor Spacing Variation', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Spacing Variance (σ meters)', fontsize=10)
    ax2.set_xlabel('')
    ax2.tick_params(axis='x', rotation=30, labelsize=9)
    ax2.set_yscale('log')
    ax2.legend_.remove()

    handles, labels = ax1.get_legend_handles_labels()
    fig.legend(handles, labels, loc='lower center', ncol=len(labels),
               fontsize=10, frameon=True, edgecolor='#cccccc',
               bbox_to_anchor=(0.5, -0.15), title="Evaluation Singularity", title_fontsize=10)

    plt.tight_layout()
    save_figure(fig, fig_dir, 'topological_resilience')




def fig_geometric_summary_table(df_exp1, grid_order, fig_dir):
    """
    Summary statistics table for geometric distortion — area CV, mean angular deviation.
    Saved as CSV alongside the figures.
    """
    print('Generating: geometric_summary_table...')
    present_grids = [g for g in grid_order if g in df_exp1['grid_name'].unique()]
    summary = df_exp1[df_exp1['grid_name'].isin(present_grids)].groupby('grid_name').agg(
        area_mean=('area_m2', 'mean'),
        area_std=('area_m2', 'std'),
        area_cv=('area_m2', lambda x: x.std() / x.mean() * 100),
        angular_mean=('angular_deviation', 'mean'),
        angular_std=('angular_deviation', 'std'),
        zsc_mean=('zsc', 'mean'),
        n_cells=('cell_id', 'count'),
    ).round(4)

    summary = summary.reindex([g for g in grid_order if g in summary.index])
    summary.index = summary.index.map(lambda x: GRID_SHORT.get(x, x))

    out = os.path.join(fig_dir, 'geometric_summary.csv')
    summary.to_csv(out)
    print(f'  ✓ Saved: geometric_summary.csv')
    print(summary.to_string())
    print()


# ==========================================================================
# Main
# ==========================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Generate paper figures from dggs-bench release datasets',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        '--data-dir', type=str, default=None,
        help='Path to directory containing release parquets. '
             'Default: auto-detect from package data directory.'
    )
    parser.add_argument(
        '--output-dir', type=str, default=None,
        help='Directory to save generated figures. Default: <data-dir>/../figures'
    )
    parser.add_argument(
        '--grids', type=str, default=None,
        help='Comma-separated list of full grid names to include. '
             'Default: all grids in the dataset.'
    )
    parser.add_argument(
        '--skip-cartopy', action='store_true',
        help='Skip globe heatmap figures (requires cartopy, which can be hard to install).'
    )
    args = parser.parse_args()

    # --- Resolve data directory ---
    if args.data_dir:
        data_dir = args.data_dir
    else:
        # Auto-detect: look relative to this script's location
        script_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.join(script_dir, '..', 'data', 'tsas_v1', 'release')
        if not os.path.exists(data_dir):
            # Try cwd
            data_dir = os.path.join('data', 'tsas_v1', 'release')

    data_dir = os.path.abspath(data_dir)
    if not os.path.exists(data_dir):
        print(f'[Error] Data directory not found: {data_dir}', file=sys.stderr)
        print('  Download the release dataset first: dggs-bench download-data', file=sys.stderr)
        sys.exit(1)

    # --- Resolve output directory ---
    if args.output_dir:
        fig_dir = os.path.abspath(args.output_dir)
    else:
        fig_dir = os.path.join(os.path.dirname(data_dir), 'figures')
    os.makedirs(fig_dir, exist_ok=True)

    print(f'Data dir:   {data_dir}')
    print(f'Figure dir: {fig_dir}')
    print()

    setup_plot_style()

    # --- Load datasets ---
    exp1_path = os.path.join(data_dir, 'geometric_distortion.parquet')
    exp2_path = os.path.join(data_dir, 'topological_resilience.parquet')

    # --- Resolve grid filter ---
    grid_filter = None
    if args.grids:
        grid_filter = [g.strip() for g in args.grids.split(',')]

    # Determine active grid ordering based on available data
    active_order = GRID_ORDER[:]  # start from canonical order

    # --- Experiment 1: Geometric Distortion ---
    if os.path.exists(exp1_path):
        print('Loading Experiment 1: Geometric Distortion...')
        df_exp1 = pd.read_parquet(exp1_path)
        if grid_filter:
            df_exp1 = df_exp1[df_exp1['grid_name'].isin(grid_filter)]
        available_grids_1 = set(df_exp1['grid_name'].unique())
        order_1 = [g for g in active_order if g in available_grids_1]
        print(f'  {len(df_exp1):,} rows, {len(order_1)} grids: {[GRID_SHORT.get(g,g) for g in order_1]}')
        print()

        # Precompute derived columns
        df_exp1['norm_area'] = df_exp1.groupby('grid_name')['area_m2'].transform(lambda x: x / x.mean())
        df_exp1['lat_bin'] = df_exp1['center_lat'].round()
        df_exp1['lon_bin'] = df_exp1['center_lon'].round()

        fig_area_angular_profiles(df_exp1, order_1, fig_dir)

        if not args.skip_cartopy:
            try:
                fig_globe_area_heatmap(df_exp1, order_1, fig_dir)
                fig_globe_angular_heatmap(df_exp1, order_1, fig_dir)
            except ImportError:
                print('  ⚠ Skipping globe heatmaps (cartopy not installed)')
        else:
            print('  ⚠ Skipping globe heatmaps (--skip-cartopy)')

        fig_geometric_summary_table(df_exp1, order_1, fig_dir)
    else:
        print(f'[Skip] geometric_distortion.parquet not found')
        print()

    # --- Experiment 2: Topological Resilience ---
    if os.path.exists(exp2_path):
        print('Loading Experiment 2: Topological Resilience...')
        df_exp2 = pd.read_parquet(exp2_path)
        if grid_filter:
            df_exp2 = df_exp2[df_exp2['grid_name'].isin(grid_filter)]
        # Add grid_short for plotting
        df_exp2['grid_short'] = df_exp2['grid_name'].map(GRID_SHORT)
        available_grids_2 = set(df_exp2['grid_name'].unique())
        order_2 = [g for g in active_order if g in available_grids_2]
        print(f'  {len(df_exp2):,} rows, {len(order_2)} grids: {[GRID_SHORT.get(g,g) for g in order_2]}')
        print()

        fig_topological_resilience(df_exp2, order_2, fig_dir)
    else:
        print(f'[Skip] topological_resilience.parquet not found')
        print()

    print(f'\nAll figures saved to: {fig_dir}')


if __name__ == '__main__':
    main()
