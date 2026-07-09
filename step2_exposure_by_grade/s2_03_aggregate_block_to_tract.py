"""
Step 2 (Figure 2) - 1/3
Aggregate block-level greenspace-exposure data up to the census-tract level and
attach the HOLC redlining attributes, producing one combined CSV for all cities.

For every city:
  1. Assign redlining attributes (grade, category, ...) to each block by >=50%
     areal overlap with the HOLC polygons.
  2. Group blocks into tracts by GEOID and take the simple mean of the income /
     education scores (redlining fields are constant within a block group and
     taken with 'first').

Input per city : Census2020/<...>_block-level-GE-tract-level-redline.shp
                 redlining/<...>_clipped.shp
Output         : one master CSV (All_cities_GE_tract_level_with_redline.csv)
                 plus a per-city *-tract-group.shp

NOTE: Edit the CONFIG paths below before running.
"""

import os

import geopandas as gpd
import pandas as pd

# ----------------------------- CONFIG (edit these) ---------------------------
BASE_DIR = "/path/to/Redlining_city_tile"                                  # one sub-folder per city
FINAL_OUTPUT_CSV = "/path/to/output/All_cities_GE_tract_level_with_redline.csv"
OVERLAP_THRESHOLD = 0.5
# -----------------------------------------------------------------------------

all_city_results = []

for city_folder in os.listdir(BASE_DIR):
    city_path = os.path.join(BASE_DIR, city_folder)
    if not os.path.isdir(city_path):
        continue

    census_folder = os.path.join(city_path, "Census2020")
    redline_folder = os.path.join(city_path, "redlining")

    if not os.path.exists(census_folder) or not os.path.exists(redline_folder):
        continue

    # find tract-level greenspace data
    census_shp_files = [
        f for f in os.listdir(census_folder)
        if f.endswith("_block-level-GE-tract-level-redline.shp")
    ]
    if len(census_shp_files) == 0:
        continue
    census_shp_path = os.path.join(census_folder, census_shp_files[0])

    # find redlining data
    redline_shp_files = [f for f in os.listdir(redline_folder) if f.endswith("_clipped.shp")]
    if len(redline_shp_files) == 0:
        continue
    redline_shp_path = os.path.join(redline_folder, redline_shp_files[0])

    gdf_census = gpd.read_file(census_shp_path)
    gdf_redline = gpd.read_file(redline_shp_path)

    # align CRS
    if gdf_census.crs != gdf_redline.crs:
        gdf_redline = gdf_redline.to_crs(gdf_census.crs)

    # ----------------------- add redlining fields ----------------------------
    gdf_result = gdf_census.copy()
    add_cols = ["category", "grade", "label", "residentia", "commercial", "industrial"]
    for col in add_cols:
        gdf_result[col] = None

    # assign redlining attributes by areal overlap
    for idx, red_poly in gdf_redline.iterrows():
        overlaps = gdf_result[gdf_result.intersects(red_poly.geometry)]

        for cidx, census_poly in overlaps.iterrows():
            intersection_area = red_poly.geometry.intersection(census_poly.geometry).area
            census_area = census_poly.geometry.area

            if census_area == 0:
                continue

            overlap_ratio = intersection_area / census_area

            if overlap_ratio >= OVERLAP_THRESHOLD:
                for col in add_cols:
                    if col in red_poly:
                        gdf_result.at[cidx, col] = red_poly[col]

    # ----------------------- tract-level simple mean -------------------------
    # these fields are averaged (simple mean, not population weighted)
    mean_fields = ["edu_score", "income_s_1", "income_sco"]

    if "GEOID" not in gdf_result.columns:
        print(f"{city_folder}: missing GEOID, skipped")
        continue

    group = gdf_result.groupby("GEOID")

    df_mean = group[mean_fields].mean().reset_index()

    # redlining fields constant within a block group -> take first
    df_meta = group[add_cols].first().reset_index()

    df_city_final = pd.merge(df_mean, df_meta, on="GEOID", how="left")
    df_city_final["city"] = city_folder

    all_city_results.append(df_city_final)

    # save per-city tract-grouped shp (with redlining)
    out_shp = os.path.join(
        census_folder,
        census_shp_files[0].replace(".shp", "-tract-group.shp"),
    )
    gdf_result.to_file(out_shp)
    print(f"{city_folder}: saved {out_shp}")

# ----------------------------- merge & save ----------------------------------
if len(all_city_results) > 0:
    df_all = pd.concat(all_city_results, ignore_index=True)
    df_all.to_csv(FINAL_OUTPUT_CSV, index=False)
    print(f"\n=== Saved master CSV: {FINAL_OUTPUT_CSV} ===")
else:
    print("No city data generated.")
