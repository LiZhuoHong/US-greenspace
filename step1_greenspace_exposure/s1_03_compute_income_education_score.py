"""
Step 1 (Figure 1) - 3/5
Convert the per-category income and education ratios (from the previous step)
into a single continuous score per block.

    income_score = sum( bracket_ratio * bracket_dollar_value )
    edu_score    = sum( attainment_ratio * attainment_year_value )

The bracket -> value tables below follow the ACS income brackets (mid-point
dollars) and educational-attainment years of schooling.

Input per city : <city>_pop-race-inc-edu.shp        (has *_ratio columns; the
                 shapefile driver truncates them to e.g. "ASQOE002_r")
Output per city: <city>_pop-race-inc-edu-score.shp   (adds income_score, edu_score)

NOTE: Edit the CONFIG path below before running.
"""

import os

import geopandas as gpd
import pandas as pd
from tqdm import tqdm

# ----------------------------- CONFIG (edit these) ---------------------------
ROOT_DIR = "/path/to/Redlining_city_tile"      # one sub-folder per city
# -----------------------------------------------------------------------------

# income bracket -> representative annual household income (USD)
INCOME_SCORES = {
    "ASQOE002": 5000,
    "ASQOE003": 10000,
    "ASQOE004": 15000,
    "ASQOE005": 20000,
    "ASQOE006": 25000,
    "ASQOE007": 30000,
    "ASQOE008": 35000,
    "ASQOE009": 40000,
    "ASQOE010": 45000,
    "ASQOE011": 50000,
    "ASQOE012": 60000,
    "ASQOE013": 75000,
    "ASQOE014": 100000,
    "ASQOE015": 125000,
    "ASQOE016": 150000,
    "ASQOE017": 200000,
}

# educational-attainment category -> years of schooling
EDU_SCORES = {
    "ASP3E002": 0, "ASP3E003": 0, "ASP3E004": 0,
    "ASP3E005": 1, "ASP3E006": 2, "ASP3E007": 3, "ASP3E008": 4,
    "ASP3E009": 5, "ASP3E010": 6, "ASP3E011": 7, "ASP3E012": 8,
    "ASP3E013": 9, "ASP3E014": 10, "ASP3E015": 11, "ASP3E016": 12,
    "ASP3E017": 12, "ASP3E018": 12, "ASP3E019": 13, "ASP3E020": 14,
    "ASP3E021": 14, "ASP3E022": 16, "ASP3E023": 18, "ASP3E024": 18, "ASP3E025": 20,
}

for city_folder in tqdm(os.listdir(ROOT_DIR), desc="Calculating scores"):
    city_path = os.path.join(ROOT_DIR, city_folder)
    if not os.path.isdir(city_path):
        continue

    census_folder = os.path.join(city_path, "Census2020")
    if not os.path.exists(census_folder):
        continue

    # find the *_pop-race-inc-edu.shp generated in the previous step
    shp_files = [f for f in os.listdir(census_folder) if f.endswith("_pop-race-inc-edu.shp")]
    if not shp_files:
        print(f"{city_folder}: no *_pop-race-inc-edu.shp found")
        continue

    shp_path = os.path.join(census_folder, shp_files[0])
    output_path = shp_path.replace("_inc-edu.shp", "_inc-edu-score.shp")

    try:
        gdf = gpd.read_file(shp_path)
    except Exception as e:
        print(f"Failed to read {city_folder}: {e}")
        continue

    # ----------------------------- income_score ------------------------------
    # shapefile truncates "ASQOE002_ratio" to "ASQOE002_r"
    income_sum = 0
    for col, score in INCOME_SCORES.items():
        col_r = f"{col}_r"
        if col_r in gdf.columns:
            gdf[col_r] = pd.to_numeric(gdf[col_r], errors="coerce")
            income_sum += gdf[col_r] * score
        else:
            print(f"Missing column {col_r} in {city_folder}")

    gdf["income_score"] = income_sum

    # ----------------------------- edu_score ---------------------------------
    edu_sum = 0
    for col, score in EDU_SCORES.items():
        col_r = f"{col}_r"
        if col_r in gdf.columns:
            gdf[col_r] = pd.to_numeric(gdf[col_r], errors="coerce")
            edu_sum += gdf[col_r] * score
        else:
            print(f"Missing column {col_r} in {city_folder}")

    gdf["edu_score"] = edu_sum

    # ----------------------------- save --------------------------------------
    try:
        gdf.to_file(output_path)
        print(f"{city_folder} saved to {output_path}")
    except Exception as e:
        print(f"Save failed {city_folder}: {e}")
