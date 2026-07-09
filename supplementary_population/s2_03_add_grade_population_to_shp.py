"""
Step 2 (Figure 2) - 3/3
Join the per-grade population totals (from the previous step) onto the master
city-points shapefile, so that each city point carries pop_A / pop_B / pop_C /
pop_D for the grade-level figures.

Input : redline_population_by_grade.csv                (city, pop_A..pop_D)
        <master>_EcosCa.shp                            (one point per city)
Output: <master>_EcosCa_Redline.shp

NOTE: Edit the CONFIG paths below before running.
"""

import geopandas as gpd
import pandas as pd

# ----------------------------- CONFIG (edit these) ---------------------------
CSV_PATH = "/path/to/redline_population_by_grade.csv"
SHP_PATH = "/path/to/ALL_cities_bbox_points_..._EcosCa.shp"
OUTPUT_SHP = "/path/to/ALL_cities_bbox_points_..._EcosCa_Redline.shp"
# -----------------------------------------------------------------------------

df = pd.read_csv(CSV_PATH)
gdf = gpd.read_file(SHP_PATH)

print(f"CSV rows: {len(df)}")
print(f"SHP features: {len(gdf)}")
print(f"\nCSV columns: {list(df.columns)}")
print(f"SHP columns: {list(gdf.columns)}")

# keep only the needed columns
df_sub = df[["city", "pop_A", "pop_B", "pop_C", "pop_D"]]

# merge on the city column
gdf = gdf.merge(
    df_sub,
    left_on="city",
    right_on="city",
    how="left",
)

# match quality check
matched = gdf["pop_A"].notna().sum()
unmatched = gdf["pop_A"].isna().sum()
print(f"\nMatched: {matched}")
print(f"Unmatched (pop_A is null): {unmatched}")

if unmatched > 0:
    miss = gdf.loc[gdf["pop_A"].isna(), "city"].unique()
    print(f"Unmatched cities (first 20): {list(miss[:20])}")

# save new shp
gdf.to_file(OUTPUT_SHP, encoding="utf-8")
print(f"\nSaved: {OUTPUT_SHP}")
