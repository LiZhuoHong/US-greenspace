"""
Step 5 (Supplementary Fig. 10) - cooling / near-surface air temperature by grade.

Summarizes the cooling ecosystem service by HOLC grade. It consumes the OUTPUTS
of the near-surface air-temperature causal model (adapted from Calhoun et al.
2024, Sci. Rep. 14:540): per-city rasters of predicted temperature
(*_predicted_temperature_pm.tif) and vegetation cooling effect
(*_causal_effects_pm.tif). For each city it extracts those pixel values within
each HOLC grade zone (A-D) and plots temperature and cooling by grade.

NOTE: The causal cooling MODEL itself (Bayesian spatial causal inference with a
spatially correlated random-effect term, NLCD non-vegetation land cover, and
K-means block cross-validation) is implemented upstream and is NOT part of this
Python package (its code is available at https://github.com/zcalhoun/causal-uhi);
this script only reads its raster outputs and stratifies them by grade. Cities
analysed in the paper have high-quality evening air-temperature data (e.g.
Atlanta, GA; Philadelphia, PA; Asheville, NC).

Violin plot generator for Redlining x Urban Heat analysis.

For each city found in the Zack directory this script will:
  1. Sum all bands of *_causal_effects_pm.tif  → *_causal_effects_pm_sum.tif
  2. Locate the matching city folder in Redlining_city_tile/
  3. Load the block-level redline shapefile (grades A-D)
  4. Extract raster pixel values per grade zone
  5. Draw TWO separate violin plots per city:
       {city}_violin_temperature.png  — Predicted Temperature (°C)
       {city}_violin_cooling.png      — Cooling Effects (unitless)

Usage
-----
  python violin_redlining.py --output /your/output/folder

Dependencies
------------
  pip install rasterio geopandas numpy matplotlib rasterstats
"""

import argparse
import os
import re
import warnings
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from rasterio.features import geometry_mask
from rasterstats import zonal_stats

warnings.filterwarnings("ignore")

# ─────────────────────────── paths ────────────────────────────────────────────
ZACK_DIR = Path(
    "/path/to/cooling_model_outputs"
)
REDLINE_ROOT = Path(
    "/path/to/Redlining_city_tile"
)

GRADE_COLORS = {
    "A": "#AEC798",
    "B": "#B6D5D1",
    "C": "#E6E097",
    "D": "#EAADB3",
}
GRADES = ["A", "B", "C", "D"]


# ─────────────────────────── helpers ──────────────────────────────────────────

def sum_bands(src_path: Path, dst_path: Path) -> Path:
    """Sum all bands of a multi-band TIF into a single-band TIF."""
    if dst_path.exists():
        return dst_path

    with rasterio.open(src_path) as src:
        meta = src.meta.copy()
        data = src.read().astype("float32")          # (bands, rows, cols)
        nodata = src.nodata

    if nodata is not None:
        data = np.where(data == nodata, np.nan, data)

    summed = np.nansum(data, axis=0)                 # (rows, cols)

    meta.update(count=1, dtype="float32", nodata=np.nan)
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(dst_path, "w", **meta) as dst:
        dst.write(summed[np.newaxis, :, :])

    print(f"  [sum] {dst_path.name}")
    return dst_path


def find_city_folder(city_name: str) -> Path | None:
    """
    Fuzzy-match city_name (lower-case, e.g. 'asheville') to a folder
    inside REDLINE_ROOT (e.g. 'Asheville__NC').
    """
    city_lower = city_name.lower()
    for folder in REDLINE_ROOT.iterdir():
        if not folder.is_dir():
            continue
        # folder name may be 'Asheville__NC' – compare only the city part
        folder_city = re.split(r"[_\-\s]+", folder.name)[0].lower()
        if folder_city == city_lower:
            return folder
    return None


def find_shapefile(city_folder: Path) -> Path | None:
    """Find *_block-level-GE-city-level-redline.shp under Census2020/."""
    census_dir = city_folder / "Census2020"
    if not census_dir.exists():
        return None
    for f in census_dir.glob("*_block-level-GE-city-level-redline.shp"):
        return f
    return None


def extract_values_by_grade(
    raster_path: Path, gdf: gpd.GeoDataFrame, grade_col: str = "grade"
) -> dict[str, np.ndarray]:
    """
    Return a dict  {grade: 1-D array of raster pixel values}
    using rasterstats zonal_stats (all_touched=False).
    """
    values_by_grade: dict[str, list] = {g: [] for g in GRADES}

    with rasterio.open(raster_path) as src:
        raster_crs = src.crs
        transform = src.transform
        nodata = src.nodata
        band = src.read(1).astype("float32")

    if nodata is not None:
        band = np.where(band == nodata, np.nan, band)

    # Reproject shapefile to raster CRS if needed
    if gdf.crs != raster_crs:
        gdf = gdf.to_crs(raster_crs)

    for grade in GRADES:
        subset = gdf[gdf[grade_col].str.upper() == grade]
        if subset.empty:
            continue

        for geom in subset.geometry:
            if geom is None or geom.is_empty:
                continue
            try:
                mask = geometry_mask(
                    [geom],
                    transform=transform,
                    invert=True,
                    out_shape=band.shape,
                )
                pixels = band[mask]
                pixels = pixels[~np.isnan(pixels)]
                if pixels.size:
                    values_by_grade[grade].extend(pixels.tolist())
            except Exception:
                pass

    return {g: np.array(v) for g, v in values_by_grade.items()}


# ─────────────────────────── plotting ─────────────────────────────────────────

def _draw_half_box_strip(ax, values_by_grade: dict[str, np.ndarray], spacing: float = 1.0):
    """
    For each grade draw:
      LEFT  half → box plot (IQR box + whiskers + median line)
      RIGHT half → jittered strip plot (subsampled raw points)
    Returns (x_ticks, x_labels) for axis formatting.
    """
    rng = np.random.default_rng(42)
    x_ticks, x_labels = [], []
    BOX_W   = 0.30   # half-width of box / jitter spread
    MAX_PTS = 500    # max dots shown per grade

    for i, grade in enumerate(GRADES):
        x_center = i * spacing
        x_ticks.append(x_center)
        x_labels.append(grade)

        data = values_by_grade.get(grade, np.array([]))
        if data.size < 5:
            continue

        color = GRADE_COLORS[grade]

        # ── statistics ────────────────────────────────────────────────────────
        q1, med, q3 = np.percentile(data, [25, 50, 75])
        iqr = q3 - q1
        lo_fence = q1 - 1.5 * iqr
        hi_fence = q3 + 1.5 * iqr
        inner = data[(data >= lo_fence) & (data <= hi_fence)]
        lo_whisker = inner.min() if inner.size else q1
        hi_whisker = inner.max() if inner.size else q3

        # ── LEFT: box plot ────────────────────────────────────────────────────
        # Filled rectangle Q1–Q3 (left half only)
        box = plt.Polygon(
            [
                [x_center - BOX_W, q1],
                [x_center,         q1],
                [x_center,         q3],
                [x_center - BOX_W, q3],
            ],
            closed=True,
            facecolor=color, edgecolor="#444444",
            linewidth=1.1, alpha=0.88, zorder=3,
        )
        ax.add_patch(box)

        # Median line (full width of left half)
        ax.plot(
            [x_center - BOX_W, x_center], [med, med],
            color="#222222", linewidth=2.0, zorder=4,
        )

        # Whisker stem (centred on left half)
        x_stem = x_center - BOX_W / 2
        ax.plot([x_stem, x_stem], [lo_whisker, q1],
                color="#444444", linewidth=1.1, zorder=3)
        ax.plot([x_stem, x_stem], [q3, hi_whisker],
                color="#444444", linewidth=1.1, zorder=3)

        # Whisker caps
        cap = BOX_W * 0.35
        ax.plot([x_stem - cap, x_stem + cap], [lo_whisker, lo_whisker],
                color="#444444", linewidth=1.1, zorder=3)
        ax.plot([x_stem - cap, x_stem + cap], [hi_whisker, hi_whisker],
                color="#444444", linewidth=1.1, zorder=3)

        # ── RIGHT: jittered strip plot ─────────────────────────────────────────
        sample = (rng.choice(data, MAX_PTS, replace=False)
                  if data.size > MAX_PTS else data)
        jitter = rng.uniform(0.03, BOX_W * 0.95, size=len(sample))
        ax.scatter(
            x_center + jitter, sample,
            color=color, edgecolors="#55555544",
            linewidths=0.3, s=6, alpha=0.55, zorder=2,
        )

    return x_ticks, x_labels


def _format_ax(ax, x_ticks, x_labels, ylabel: str, title: str, spacing: float = 1.0):
    """Apply shared axis formatting."""
    ax.set_xticks(x_ticks)
    ax.set_xticklabels(x_labels, fontsize=14, fontweight="bold")
    ax.set_xlabel("HOLC Grade", fontsize=13)
    ax.set_ylabel(ylabel, fontsize=12, color="#333333")
    ax.tick_params(axis="y", labelsize=10)
    ax.set_xlim(-0.7, (len(GRADES) - 1) * spacing + 0.7)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_title(title, fontsize=13, pad=12)


def make_violin_plots(
    city: str,
    temp_values: dict[str, np.ndarray],
    cool_values: dict[str, np.ndarray],
    output_dir: Path,
):
    """Draw and save two separate violin plots for a city."""
    spacing = 1.0
    city_title = city.replace("_", " ").title()

    # ── Plot 1: Predicted Temperature ─────────────────────────────────────────
    fig1, ax1 = plt.subplots(figsize=(8, 5))
    x_ticks, x_labels = _draw_half_box_strip(ax1, temp_values, spacing)
    _format_ax(
        ax1, x_ticks, x_labels,
        ylabel="Predicted Temperature (°C)",
        title=f"{city_title} — Predicted Temperature by HOLC Grade",
        spacing=spacing,
    )
    fig1.tight_layout()
    out1 = output_dir / f"{city}_violin_temperature.png"
    fig1.savefig(out1, dpi=150, bbox_inches="tight")
    plt.close(fig1)
    print(f"  [plot] saved → {out1}")

    # ── Plot 2: Cooling Effects ────────────────────────────────────────────────
    fig2, ax2 = plt.subplots(figsize=(8, 5))
    x_ticks, x_labels = _draw_half_box_strip(ax2, cool_values, spacing)
    _format_ax(
        ax2, x_ticks, x_labels,
        ylabel="Cooling Effects (°C)",
        title=f"{city_title} — Cooling Effects by HOLC Grade",
        spacing=spacing,
    )
    fig2.tight_layout()
    out2 = output_dir / f"{city}_violin_cooling.png"
    fig2.savefig(out2, dpi=150, bbox_inches="tight")
    plt.close(fig2)
    print(f"  [plot] saved → {out2}")


# ─────────────────────────── main ─────────────────────────────────────────────

def make_summary_violin_plots(
    all_temp: dict[str, np.ndarray],
    all_cool: dict[str, np.ndarray],
    n_cities: int,
    output_dir: Path,
):
    """
    Draw two summary violin plots aggregating ALL cities by HOLC grade.
    all_temp / all_cool: {grade: concatenated pixel array across all cities}
    """
    spacing = 1.0
    title_suffix = f"(all {n_cities} cities)"

    for values, ylabel, fname, title in [
        (
            all_temp,
            "Predicted Temperature (°C)",
            "ALL_CITIES_violin_temperature.png",
            f"Predicted Temperature by HOLC Grade {title_suffix}",
        ),
        (
            all_cool,
            "Cooling Effects (°C)",
            "ALL_CITIES_violin_cooling.png",
            f"Cooling Effects by HOLC Grade {title_suffix}",
        ),
    ]:
        fig, ax = plt.subplots(figsize=(8, 5))
        x_ticks, x_labels = _draw_half_box_strip(ax, values, spacing)
        _format_ax(ax, x_ticks, x_labels, ylabel=ylabel, title=title, spacing=spacing)

        # Annotate each violin with pixel count (n)
        for i, grade in enumerate(GRADES):
            arr = values.get(grade, np.array([]))
            if arr.size >= 5:
                ax.text(
                    i * spacing,
                    ax.get_ylim()[0],
                    f"n={arr.size:,}",
                    ha="center",
                    va="bottom",
                    fontsize=7,
                    color="#555555",
                )

        fig.tight_layout()
        out = output_dir / fname
        fig.savefig(out, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"  [summary plot] saved → {out}")


def main(output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── collect cities ─────────────────────────────────────────────────────────
    temp_files = {
        f.stem.replace("_predicted_temperature_pm", ""): f
        for f in ZACK_DIR.glob("*_predicted_temperature_pm.tif")
    }
    causal_files = {
        f.stem.replace("_causal_effects_pm", ""): f
        for f in ZACK_DIR.glob("*_causal_effects_pm.tif")
    }

    cities = sorted(set(temp_files) & set(causal_files))
    print(f"Found {len(cities)} cities with both TIF files.\n")

    # Accumulators for the cross-city summary plots
    all_temp: dict[str, list] = {g: [] for g in GRADES}
    all_cool: dict[str, list] = {g: [] for g in GRADES}
    processed_cities = 0

    for city in cities:
        print(f"── {city} ──")

        # 1. Sum causal-effects bands
        causal_path = causal_files[city]
        sum_path = ZACK_DIR / f"{city}_causal_effects_pm_sum.tif"
        sum_bands(causal_path, sum_path)

        # 2. Find city folder & shapefile
        city_folder = find_city_folder(city)
        if city_folder is None:
            print(f"  [WARN] No city folder found for '{city}', skipping.\n")
            continue

        shp_path = find_shapefile(city_folder)
        if shp_path is None:
            print(f"  [WARN] No shapefile found under {city_folder}, skipping.\n")
            continue

        print(f"  [shp] {shp_path.name}")

        # 3. Load shapefile
        try:
            gdf = gpd.read_file(shp_path)
        except Exception as e:
            print(f"  [ERROR] Cannot read shapefile: {e}\n")
            continue

        # Identify the grade column (case-insensitive search)
        grade_col = next(
            (c for c in gdf.columns if c.lower() == "grade"), None
        )
        if grade_col is None:
            print(f"  [WARN] No 'grade' column in {shp_path.name}. "
                  f"Columns: {list(gdf.columns)}\n")
            continue

        # 4. Extract pixel values per grade
        temp_path = temp_files[city]
        print(f"  [extract] temperature values …")
        temp_values = extract_values_by_grade(temp_path, gdf, grade_col)

        print(f"  [extract] cooling-effect values …")
        cool_values = extract_values_by_grade(sum_path, gdf, grade_col)

        # Quick summary
        for g in GRADES:
            nt = temp_values.get(g, np.array([])).size
            nc = cool_values.get(g, np.array([])).size
            print(f"    grade {g}: {nt} temp pixels, {nc} cooling pixels")

        # Accumulate into global pools
        for g in GRADES:
            if temp_values.get(g, np.array([])).size:
                all_temp[g].extend(temp_values[g].tolist())
            if cool_values.get(g, np.array([])).size:
                all_cool[g].extend(cool_values[g].tolist())

        # 5. Draw per-city violin plots (two separate figures)
        make_violin_plots(city, temp_values, cool_values, output_dir)
        processed_cities += 1
        print()

    # ── Summary plots across all cities ───────────────────────────────────────
    print(f"── Summary across {processed_cities} cities ──")
    all_temp_arr = {g: np.array(v) for g, v in all_temp.items()}
    all_cool_arr = {g: np.array(v) for g, v in all_cool.items()}
    make_summary_violin_plots(all_temp_arr, all_cool_arr, processed_cities, output_dir)

    print("\nDone.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Redlining violin plots")
    parser.add_argument(
        "--output",
        type=str,
        default="/path/to/output/cooling_plots",
        help="Directory where PNG plots are saved",
    )
    args = parser.parse_args()
    main(Path(args.output))