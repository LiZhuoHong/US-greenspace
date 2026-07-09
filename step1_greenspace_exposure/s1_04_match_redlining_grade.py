"""
Step 1 (Figure 1) - 4/5
Assign a historical HOLC redlining grade (A / B / C / D) to each census block.

A block receives the grade of a redlining polygon when at least 50% of the
block's area is covered by that polygon. Blocks with no qualifying overlap keep
a null grade (all blocks are retained in the output).

Input per city : redlining/<...>_clipped.shp        (HOLC polygons with 'grade')
                 Census2020/<...>_BLOCK-level-GE.shp (block-level greenspace data)
Output per city: Census2020/<...>_BLOCK-level-GE-redline.shp

NOTE: Edit the CONFIG path below before running.
"""

import os

import geopandas as gpd

# ----------------------------- CONFIG (edit these) ---------------------------
BASE_DIR = "/path/to/Redlining_city_tile"      # one sub-folder per city
OVERLAP_THRESHOLD = 0.5                         # min share of block area covered
# -----------------------------------------------------------------------------

for city_folder in os.listdir(BASE_DIR):
    city_path = os.path.join(BASE_DIR, city_folder)
    if not os.path.isdir(city_path):
        continue

    census_folder = os.path.join(city_path, "Census2020")
    redline_folder = os.path.join(city_path, "redlining")
    if not os.path.exists(census_folder) or not os.path.exists(redline_folder):
        continue

    census_shp_files = [f for f in os.listdir(census_folder) if f.endswith("_BLOCK-level-GE.shp")]
    if len(census_shp_files) == 0:
        continue
    census_shp_path = os.path.join(census_folder, census_shp_files[0])
    gdf_census = gpd.read_file(census_shp_path)

    redline_shp_files = [f for f in os.listdir(redline_folder) if f.endswith("_clipped.shp")]
    if len(redline_shp_files) == 0:
        continue
    redline_shp_path = os.path.join(redline_folder, redline_shp_files[0])
    gdf_redline = gpd.read_file(redline_shp_path)

    # align coordinate reference systems
    if gdf_census.crs != gdf_redline.crs:
        gdf_redline = gdf_redline.to_crs(gdf_census.crs)

    # copy census blocks and add an empty 'grade' field
    gdf_result = gdf_census.copy()
    add_cols = ["grade"]
    for col in add_cols:
        gdf_result[col] = None

    # for each redlining polygon, assign its grade to sufficiently covered blocks
    for idx, red_poly in gdf_redline.iterrows():

        overlaps = gdf_result[gdf_result.intersects(red_poly.geometry)]

        for cidx, census_poly in overlaps.iterrows():

            intersection_area = red_poly.geometry.intersection(census_poly.geometry).area
            census_area = census_poly.geometry.area

            if census_area == 0:
                continue

            overlap_ratio = intersection_area / census_area

            # only assign when coverage >= threshold
            if overlap_ratio >= OVERLAP_THRESHOLD:
                for col in add_cols:
                    if col in red_poly:
                        gdf_result.at[cidx, col] = red_poly[col]

    # save (all blocks retained)
    output_path = os.path.join(
        census_folder,
        census_shp_files[0].replace(".shp", "-redline.shp"),
    )
    gdf_result.to_file(output_path)

    print(f"{city_folder}: saved {output_path} (all blocks retained)")
