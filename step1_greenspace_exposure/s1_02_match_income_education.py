"""
Step 1 (Figure 1) - 2/5
Join third-party Census income and education tables (tract level) onto the
census block shapefile, computing the fractional share of each income /
education category.

Input per city  : <city>_pop-race.shp        (blocks with population by race)
Third-party CSV : <STATE>.csv                 (ACS-style income & education counts)
Output per city : <city>_pop-race-inc-edu.shp

Income table columns  : ASQOE001 (total) + ASQOE002..ASQOE017 (income brackets)
Education table columns: ASP3E001 (total) + ASP3E002..ASP3E025 (attainment levels)
For each bracket a "<col>_ratio" column is produced (count / total) and joined to
the blocks by STATE / COUNTY / TRACT code.

NOTE: Edit the CONFIG paths below before running.
"""

import os

import geopandas as gpd
import pandas as pd
from tqdm import tqdm

# ----------------------------- CONFIG (edit these) ---------------------------
ROOT_DIR = "/path/to/Redlining_city_tile"                       # one sub-folder per city
CSV_DIR = "/path/to/Census_table/income-education"              # <STATE>.csv tables
# -----------------------------------------------------------------------------

for city_folder in tqdm(os.listdir(ROOT_DIR), desc="Processing cities"):
    city_path = os.path.join(ROOT_DIR, city_folder)
    if not os.path.isdir(city_path):
        continue

    state_abbr = city_folder.split("__")[-1]
    csv_path = os.path.join(CSV_DIR, f"{state_abbr}.csv")
    if not os.path.exists(csv_path):
        print(f"{state_abbr}.csv not found, skipping {city_folder}")
        continue

    census_folder = os.path.join(city_path, "Census2020")
    if not os.path.exists(census_folder):
        continue

    shp_files = [f for f in os.listdir(census_folder) if f.endswith("_pop-race.shp")]
    if not shp_files:
        print(f"{city_folder}: no _pop-race.shp found")
        continue

    shp_path = os.path.join(census_folder, shp_files[0])
    output_path = shp_path.replace("_pop-race.shp", "_pop-race-inc-edu.shp")

    # ----------------------------- read data ---------------------------------
    try:
        gdf = gpd.read_file(shp_path)
        df = pd.read_csv(csv_path, dtype=str)
    except Exception as e:
        print(f"Failed to read {city_folder}: {e}")
        continue

    # ----------------------------- select & cast columns ---------------------
    income_cols = ["ASQOE001"] + [f"ASQOE{str(i).zfill(3)}" for i in range(2, 18)]
    edu_cols = ["ASP3E001"] + [f"ASP3E{str(i).zfill(3)}" for i in range(2, 26)]
    all_cols = ["STATEA", "COUNTYA", "TRACTA"] + income_cols + edu_cols

    df = df[[c for c in all_cols if c in df.columns]].copy()
    df = df.apply(pd.to_numeric, errors="ignore")

    # ----------------------------- ratio columns -----------------------------
    for i in range(2, 18):
        num_col = f"ASQOE{str(i).zfill(3)}"
        if "ASQOE001" in df.columns and num_col in df.columns:
            df[f"{num_col}_ratio"] = df[num_col] / df["ASQOE001"]

    for i in range(2, 26):
        num_col = f"ASP3E{str(i).zfill(3)}"
        if "ASP3E001" in df.columns and num_col in df.columns:
            df[f"{num_col}_ratio"] = df[num_col] / df["ASP3E001"]

    # keep only the ratio columns + join keys
    keep_cols = ["STATEA", "COUNTYA", "TRACTA"] + [c for c in df.columns if c.endswith("_ratio")]
    df = df[keep_cols].copy()

    for c in df.columns:
        if c.endswith("_ratio"):
            df[c] = pd.to_numeric(df[c], errors="coerce").astype(float)

    # ----------------------------- merge -------------------------------------
    merge_keys_shp = ["STATEFP20", "COUNTYFP20", "TRACTCE20"]
    merge_keys_csv = ["STATEA", "COUNTYA", "TRACTA"]

    missing_keys_csv = [k for k in merge_keys_csv if k not in df.columns]
    missing_keys_shp = [k for k in merge_keys_shp if k not in gdf.columns]
    if missing_keys_csv or missing_keys_shp:
        print(f"Missing keys: CSV {missing_keys_csv}, SHP {missing_keys_shp}, skipping {city_folder}")
        continue

    for k in merge_keys_shp:
        gdf[k] = gdf[k].astype(str).str.zfill(6)
    for k in merge_keys_csv:
        df[k] = df[k].astype(str).str.zfill(6)

    if df.duplicated(subset=merge_keys_csv).any():
        print(f"{state_abbr}.csv contains duplicate tract records.")

    try:
        merged = gdf.merge(
            df,
            how="left",
            left_on=merge_keys_shp,
            right_on=merge_keys_csv,
            validate="m:1",
        )
    except Exception as e:
        print(f"Merge failed {city_folder}: {e}")
        continue

    # ----------------------------- save --------------------------------------
    try:
        merged.to_file(output_path)
        print(f"{city_folder} saved to {output_path}")
    except Exception as e:
        print(f"Save failed {city_folder}: {e}")
