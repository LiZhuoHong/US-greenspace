"""
Step 4 (Figure 4) - 1/4
Prepare the PM2.5 raster: read the national GHAP monthly PM2.5 NetCDF and clip
it to each city's bounding box, saving a per-city GeoTIFF.

Input : GHAP monthly PM2.5 NetCDF (variable 'PM2.5', EPSG:4326)
        per-city <city>_bbox.shp bounding boxes
Output: per-city <city>_pm25.tif

NOTE: Edit the CONFIG paths below before running.
"""

import gc
import glob
import os

import geopandas as gpd
import rioxarray  # noqa: F401  (registers the .rio accessor)
import xarray as xr
from tqdm import tqdm

# ----------------------------- CONFIG (edit these) ---------------------------
NC_FILE = "/path/to/GHAP_PM25_M1K_202208_V1.nc"
BASE_DIR = "/path/to/Redlining_city_tile"      # one sub-folder per city
OUTPUT_SUFFIX = "_pm25.tif"
PM25_VAR = "PM2.5"
# -----------------------------------------------------------------------------

# ----------------------------- read NetCDF -----------------------------------
print("Reading NetCDF file...")
with xr.open_dataset(NC_FILE) as ds:
    print("Available variables:", list(ds.variables))

    if PM25_VAR not in ds.variables:
        raise KeyError(f"Variable {PM25_VAR} not found")

    pm25 = ds[PM25_VAR].copy()

    print("\nPM2.5 dims:", pm25.dims)
    print("PM2.5 coords:", list(pm25.coords.keys()))

    if "lat" in pm25.dims and "lon" in pm25.dims:
        pm25 = pm25.rio.set_spatial_dims(x_dim="lon", y_dim="lat")
    elif "latitude" in pm25.dims and "longitude" in pm25.dims:
        pm25 = pm25.rio.set_spatial_dims(x_dim="longitude", y_dim="latitude")
    else:
        raise ValueError("Could not auto-detect spatial dims; set them manually")

    pm25 = pm25.rio.write_crs("EPSG:4326", inplace=True)

    print("Raster CRS:", pm25.rio.crs)
    print("Raster shape:", pm25.shape)

# ----------------------------- find bbox shapefiles --------------------------
shp_files = sorted(glob.glob(os.path.join(BASE_DIR, "**", "*_bbox.shp"), recursive=True))
print(f"\nFound {len(shp_files)} bbox shapefiles")

# ----------------------------- clip loop -------------------------------------
skipped_count = 0
processed_count = 0

for shp_path in tqdm(shp_files, desc="Processing cities"):
    try:
        city_dir = os.path.dirname(shp_path)
        city_name = os.path.basename(shp_path).replace("_bbox.shp", "")
        out_file = os.path.join(city_dir, f"{city_name}{OUTPUT_SUFFIX}")

        if os.path.exists(out_file) and os.path.getsize(out_file) > 1000:
            print(f"  already exists, skipping -> {city_name}")
            skipped_count += 1
            continue

        gdf = gpd.read_file(shp_path)
        if gdf.crs is None:
            gdf = gdf.set_crs("EPSG:4326")

        if gdf.crs != pm25.rio.crs:
            gdf = gdf.to_crs(pm25.rio.crs)

        clipped = pm25.rio.clip(
            gdf.geometry.values,
            gdf.crs,
            all_touched=True,
            from_disk=True,
        )

        if clipped.size == 0:
            print(f"  {city_name}: empty after clip, skipping")
            del clipped
            gc.collect()
            continue

        clipped.rio.to_raster(
            out_file,
            driver="GTiff",
            dtype="float32",
            compress="DEFLATE",
            tiled=True,
            blockxsize=512,
            blockysize=512,
            num_threads="ALL_CPUS",
        )

        print(f"  saved: {out_file}")
        processed_count += 1

        del clipped
        gc.collect()

        if processed_count % 5 == 0:
            print(f"  processed {processed_count}, extra memory cleanup...")
            gc.collect()

    except Exception as e:
        print(f"  failed for {city_name}: {e}")
        continue

print("\nDone.")
print(f"Processed/saved: {processed_count} cities")
print(f"Skipped (existing): {skipped_count} cities")
print(f"Total files: {len(shp_files)}")
