"""
Step 4 (Figure 4) - 2/4
Compute block-level Resident PM2.5 Mitigation (RPM) from the vegetation pixel
composition and per-type, per-city removal coefficients (betas).

    RPM_Block = sum_over_veg_types( pixel_count[type] * beta_per_km2[type] )

Each city has a beta CSV giving beta_per_km2 for every vegetation type. City
folder names are fuzzily matched to the beta filenames (handling hyphens,
ampersands, extra underscores, etc).

Input per city : Census2020/<...>BLOCK-level-GE-redline2.shp   (pixel columns)
Beta table     : betas_<city>.csv                             (type, beta_per_km2)
Output per city: <OUTPUT_DIR>/<city>_RPM_Block.shp

Vegetation class -> type:
    pix_2 EBF, pix_4 DBF, pix_6 ENF, pix_8 DNF, pix_10 MF,
    pix_12 ES, pix_13 DS, pix_14 Grass

NOTE: Edit the CONFIG paths below before running.
"""

import os
import re
import traceback

import geopandas as gpd
import pandas as pd

# ----------------------------- CONFIG (edit these) ---------------------------
ROOT_DIR = "/path/to/Redlining_city_tile"      # one sub-folder per city
BETA_DIR = "/path/to/beta_PM25"                # betas_<city>.csv files
OUTPUT_DIR = os.path.join(ROOT_DIR, "Processed_RPM_Block-new")
# -----------------------------------------------------------------------------

os.makedirs(OUTPUT_DIR, exist_ok=True)

PIX_TO_TYPE = {
    "pix_2": "EBF",
    "pix_4": "DBF",
    "pix_6": "ENF",
    "pix_8": "DNF",
    "pix_10": "MF",
    "pix_12": "ES",
    "pix_13": "DS",
    "pix_14": "Grass",
}


def normalize_name(name):
    """Normalise a city name: unify hyphens, ampersands, commas, underscores."""
    name = str(name)
    name = name.replace("-", "_")       # Wilkes-Barre
    name = name.replace("&", "")        # Pawtucket_&_Central -> Pawtucket_Central
    name = name.replace(" & ", "_")
    name = name.replace("_&_", "_")
    name = re.sub(r"[,._]+", "_", name)
    name = re.sub(r"_+", "_", name)
    name = name.strip("_ ")
    return name


def find_beta_csv(city_folder_name):
    """Fuzzy-match the beta CSV file for a city."""
    norm_name = normalize_name(city_folder_name)
    original = city_folder_name

    possible_patterns = [
        f"betas_{norm_name}.csv",
        f"betas_{original}.csv",
        f"beta_{norm_name}.csv",
        norm_name + ".csv",
    ]

    if "Co" in norm_name or "Co" in original:
        alt1 = norm_name.replace("_Co", "")
        alt2 = norm_name.replace("Co", "County")
        possible_patterns.extend([f"betas_{alt1}.csv", f"betas_{alt2}.csv"])

    print(f"  searching -> normalized name: {norm_name}")

    for name in possible_patterns:
        path = os.path.join(BETA_DIR, name)
        if os.path.exists(path):
            print(f"  found beta file: {name}")
            return path

    print("  beta file not found")
    return None


def is_already_processed(city_name):
    output_path = os.path.join(OUTPUT_DIR, f"{city_name}_RPM_Block.shp")
    return os.path.exists(output_path)


def process_city(city_folder):
    city_name_norm = normalize_name(city_folder)
    city_dir = os.path.join(ROOT_DIR, city_folder)

    print(f"\nProcessing city: {city_folder} -> normalized: {city_name_norm}")

    if is_already_processed(city_name_norm):
        print("  already processed, skipping")
        return True, None

    # find the block-level shapefile
    shp_path = None
    census_dir = os.path.join(city_dir, "Census2020")
    if os.path.exists(census_dir):
        for file in os.listdir(census_dir):
            if file.endswith("BLOCK-level-GE-redline2.shp"):
                shp_path = os.path.join(census_dir, file)
                break

    if not shp_path:
        return False, "BLOCK-level-GE-redline2.shp not found"

    beta_path = find_beta_csv(city_folder)
    if not beta_path:
        return False, "beta CSV not found"

    try:
        gdf = gpd.read_file(shp_path)
        beta_df = pd.read_csv(beta_path)

        print(f"  shapefile rows: {len(gdf)}, beta rows: {len(beta_df)}")

        # build type -> beta lookup
        beta_dict = {}
        for _, row in beta_df.iterrows():
            type_str = str(row["type"]).strip()
            if type_str in PIX_TO_TYPE.values():
                beta_dict[type_str] = float(row["beta_per_km2"])

        print(f"  beta types found: {list(beta_dict.keys())}")

        # RPM_Block = sum(pixel_count * beta)
        gdf["RPM_Block"] = 0.0
        for pix_col, beta_type in PIX_TO_TYPE.items():
            if pix_col in gdf.columns and beta_type in beta_dict:
                gdf["RPM_Block"] += gdf[pix_col] * beta_dict[beta_type]

        output_filename = f"{city_name_norm}_RPM_Block.shp"
        output_path = os.path.join(OUTPUT_DIR, output_filename)
        gdf.to_file(output_path)

        print("  success")
        return True, None

    except Exception as e:
        error_msg = f"{str(e)}\n{traceback.format_exc()}"
        print(f"  error: {e}")
        return False, error_msg


if __name__ == "__main__":
    print("Starting batch RPM-Block computation ...\n")

    success_count = 0
    total_count = 0
    failed_cities = []

    for item in sorted(os.listdir(ROOT_DIR)):
        city_dir_path = os.path.join(ROOT_DIR, item)
        if os.path.isdir(city_dir_path) and item != "Processed_RPM_Block":
            total_count += 1
            success, error = process_city(item)
            if success:
                success_count += 1
            else:
                failed_cities.append((item, error))

    print("\n" + "=" * 90)
    print(f"Done. Processed {total_count} cities, {success_count} succeeded.")
    print(f"Output dir: {OUTPUT_DIR}")

    if failed_cities:
        print(f"\nFailed cities ({len(failed_cities)}):")
        for city, reason in failed_cities:
            print(f"   - {city}  ->  {reason.splitlines()[0]}")
    else:
        print("\nAll cities processed successfully.")

    print("=" * 90)
