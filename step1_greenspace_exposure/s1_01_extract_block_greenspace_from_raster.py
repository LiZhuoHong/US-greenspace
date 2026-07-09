"""
Step 1 (Figure 1) - 1/5
Extract per-block greenspace metrics from the classified vegetation raster
(result.tif / resultv2.tif).

For every census block polygon (using the 15-minute buffer geometry) this script
counts the pixels of each vegetation class inside the polygon and derives:
    - pix_total       : total number of valid pixels
    - veg_total_pct   : percentage of pixels that are vegetation
    - veg_diversity   : number of distinct vegetation classes present
    - pix_<class>     : pixel count of each vegetation class

Vegetation class codes (pixel value -> type):
    2  EBF  Evergreen broad-leaved canopy
    4  DBF  Deciduous broad-leaved canopy
    6  ENF  Evergreen needle-leaved canopy
    8  DNF  Deciduous needle-leaved canopy
    10 MF   Mixed canopy
    12 ES   Evergreen shrub
    13 DS   Deciduous shrub
    14 Grass

Output: <city>_census_stat.shp (block polygons with the metrics above joined back).

NOTE: Edit the CONFIG paths below before running.
"""

import os
from multiprocessing import Pool, cpu_count

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.mask import mask
from tqdm import tqdm

# ----------------------------- CONFIG (edit these) ---------------------------
BASE_DIR = "/path/to/Redlining_city_tile"      # root folder, one sub-folder per city
VEG_CLASSES = [2, 4, 6, 8, 10, 12, 13, 14]     # vegetation pixel values to count
LOG_PATH = os.path.join(BASE_DIR, "process_log.csv")
NUM_WORKERS = max(1, cpu_count() - 1)          # leave one CPU free for the system
# -----------------------------------------------------------------------------


def append_log(city, status, reason=""):
    """Append one processing record to the log CSV."""
    df_log = pd.DataFrame([[city, status, reason]], columns=["city", "status", "reason"])
    if os.path.exists(LOG_PATH):
        df_log.to_csv(LOG_PATH, mode="a", index=False, header=False)
    else:
        df_log.to_csv(LOG_PATH, index=False)


def process_polygon(args):
    """Count vegetation pixels inside a single polygon (runs in a worker process)."""
    row, raster_fp, geoid_col = args
    geom = row.geometry
    try:
        with rasterio.open(raster_fp) as src:
            out_image, _ = mask(src, [geom], crop=True)
            data = out_image[0]
            total_count = np.count_nonzero(data >= 0)
            class_counts = {cls: np.count_nonzero(data == cls) for cls in VEG_CLASSES}
            total_veg_pixels = sum(class_counts.values())

        return {
            geoid_col: row[geoid_col],
            "pix_total": float(total_count),
            "veg_total_pct": float(100 * total_veg_pixels / total_count if total_count > 0 else 0.0),
            "veg_diversity": float(sum(1 for cls in VEG_CLASSES if class_counts[cls] > 0)),
            **{f"pix_{cls}": float(v) for cls, v in class_counts.items()},
        }

    except Exception:
        return {
            geoid_col: row[geoid_col],
            "pix_total": 0,
            "veg_total_pct": 0.0,
            "veg_diversity": 0.0,
            **{f"pix_{cls}": 0.0 for cls in VEG_CLASSES},
        }


# ----------------------------- collect cities --------------------------------
cities = sorted([d for d in os.listdir(BASE_DIR) if os.path.isdir(os.path.join(BASE_DIR, d))])
print(f"Detected {len(cities)} cities.")

# ----------------------------- main loop -------------------------------------
for city in tqdm(cities, desc="Processing cities"):
    city_dir = os.path.join(BASE_DIR, city)
    census_dir = os.path.join(city_dir, "Census2020")

    buffer_shp_fp = os.path.join(census_dir, f"{city}_census_15minbuffer.shp")
    orig_shp_fp = os.path.join(census_dir, f"{city}_census.shp")
    raster_fp = os.path.join(city_dir, f"{city}_resultv2.tif")
    out_fp = os.path.join(census_dir, f"{city}_census_stat.shp")

    # ----------------------------- check inputs ------------------------------
    if not (os.path.exists(buffer_shp_fp) and os.path.exists(orig_shp_fp) and os.path.exists(raster_fp)):
        reason = "missing required files"
        if not os.path.exists(buffer_shp_fp):
            reason += " (buffer_shp)"
        if not os.path.exists(orig_shp_fp):
            reason += " (orig_shp)"
        if not os.path.exists(raster_fp):
            reason += " (tif)"
        print(f"[{city}] {reason}, skipped.")
        append_log(city, "skipped", reason)
        continue

    if os.path.exists(out_fp):
        print(f"[{city}] _census_stat.shp already exists, skipped.")
        append_log(city, "skipped", "_census_stat.shp already exists")
        continue

    try:
        buffer_polygons = gpd.read_file(buffer_shp_fp)
        orig_polygons = gpd.read_file(orig_shp_fp)

        # automatically pick the GEOID field
        if "GEOID20" in buffer_polygons.columns:
            geoid_col = "GEOID20"
        elif "GEOID10" in buffer_polygons.columns:
            geoid_col = "GEOID10"
        else:
            print(f"[{city}] skipped: no GEOID20 or GEOID10 field")
            append_log(city, "skipped", "no GEOID20/GEOID10 field")
            continue

        # ----------------------------- parallel polygon processing -----------
        args_list = [(row, raster_fp, geoid_col) for _, row in buffer_polygons.iterrows()]
        stat_list = []

        with Pool(NUM_WORKERS) as pool:
            for result in tqdm(
                pool.imap_unordered(process_polygon, args_list),
                total=len(args_list),
                desc=f"[{city}] Processing polygons",
                leave=False,
            ):
                stat_list.append(result)

        # merge results back onto the original block polygons
        if geoid_col not in orig_polygons.columns:
            print(f"[{city}] warning: original shp missing {geoid_col}, cannot merge.")
            append_log(city, "skipped", f"original shp missing {geoid_col}")
            continue

        stat_df = pd.DataFrame(stat_list)
        merged = orig_polygons.merge(stat_df, on=geoid_col, how="left")

        # shapefile column names cannot exceed 10 characters
        rename_map = {c: c[:10] for c in merged.columns}
        merged = merged.rename(columns=rename_map)

        merged.to_file(out_fp, driver="ESRI Shapefile")
        print(f"[{city}] done (using {geoid_col})")
        append_log(city, "success", f"using {geoid_col}")

    except Exception as e:
        print(f"[{city}] error: {e}")
        append_log(city, "error", str(e))
        continue

# ----------------------------- summary ---------------------------------------
if os.path.exists(LOG_PATH):
    df_log = pd.read_csv(LOG_PATH)
    print("\n===== Processing summary =====")
    print(df_log["status"].value_counts())
    print("==============================")
else:
    print("No log file generated.")
