"""
Step 2 (Figure 2) - 2/3
Tally the total resident population falling in each redlining grade (A/B/C/D)
for every city, producing one summary CSV.

For each city, the block-level greenspace shapefile (already carrying a 'grade'
field and a per-block population column 'row_pop_to') is grouped by grade and
the population summed.

Input per city : Census2020/<...>_block-level-GE-city-level-redline.shp
Output         : redline_population_by_grade.csv  (city, pop_A, pop_B, pop_C, pop_D)

NOTE: Edit the CONFIG path below before running.
"""

import glob
import os

import geopandas as gpd
import pandas as pd

# ----------------------------- CONFIG (edit these) ---------------------------
BASE_DIR = "/path/to/Redlining_city_tile"      # one sub-folder per city
# -----------------------------------------------------------------------------

results = []

city_folders = sorted([
    d for d in os.listdir(BASE_DIR)
    if os.path.isdir(os.path.join(BASE_DIR, d))
])

print(f"Found {len(city_folders)} city folders")

for city in city_folders:
    census_dir = os.path.join(BASE_DIR, city, "Census2020")

    if not os.path.isdir(census_dir):
        print(f"  [skip] {city}: no Census2020 folder")
        continue

    pattern = os.path.join(census_dir, "*_block-level-GE-city-level-redline.shp")
    shp_files = glob.glob(pattern)

    if not shp_files:
        print(f"  [skip] {city}: no matching .shp file")
        continue

    if len(shp_files) > 1:
        print(f"  [warn] {city}: multiple matches, using first: {shp_files[0]}")

    shp_path = shp_files[0]

    try:
        gdf = gpd.read_file(shp_path)

        if "grade" not in gdf.columns:
            print(f"  [skip] {city}: missing 'grade' column, columns: {list(gdf.columns)}")
            continue
        if "row_pop_to" not in gdf.columns:
            print(f"  [skip] {city}: missing 'row_pop_to' column, columns: {list(gdf.columns)}")
            continue

        # sum population by grade
        pop_by_grade = (
            gdf.groupby("grade")["row_pop_to"]
            .sum()
            .reindex(["A", "B", "C", "D"], fill_value=0)
        )

        results.append({
            "city": city,
            "pop_A": pop_by_grade["A"],
            "pop_B": pop_by_grade["B"],
            "pop_C": pop_by_grade["C"],
            "pop_D": pop_by_grade["D"],
        })

        print(f"  [done] {city}: A={pop_by_grade['A']:.0f}, B={pop_by_grade['B']:.0f}, "
              f"C={pop_by_grade['C']:.0f}, D={pop_by_grade['D']:.0f}")

    except Exception as e:
        print(f"  [error] {city}: {e}")

# ----------------------------- write output ----------------------------------
if results:
    df_out = pd.DataFrame(results, columns=["city", "pop_A", "pop_B", "pop_C", "pop_D"])

    for col in ["pop_A", "pop_B", "pop_C", "pop_D"]:
        df_out[col] = df_out[col].astype(int)

    output_path = os.path.join(BASE_DIR, "redline_population_by_grade.csv")
    df_out.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"\nSaved to: {output_path}")
    print(f"   {len(df_out)} cities summarised")
    print(df_out.head(10).to_string(index=False))
else:
    print("\nNo valid data, no CSV written.")
