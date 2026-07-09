"""
Step 4 (Figure 4) - 3/4
Compute tract-level ecosystem-service capacity (PM2.5 mitigation potential,
"Ecos_capa") from block-level greenspace composition and population.

Per block:
    Ecos_row = row_pop_total * ( sum_over_types( pixel_count[type] * coef[type] ) )
                              / pix_total

The per-type coefficients (below) are the PM2.5 removal weights for each
vegetation class. Blocks are aggregated to tracts (Ecos_row summed), then divided
by the tract total population (sum of race groups) and scaled by 100 to give a
per-resident capacity.

Input per city : Census2020/<...>_BLOCK-level-GE-redline2.csv
Output         : Tract_Level_Ecos_Capa_Results.csv
                 (STATEFP20, COUNTYFP20, TRACTCE20, Ecos_capa)

NOTE: Edit the CONFIG paths below before running.
"""

import glob
import os

import numpy as np
import pandas as pd

# ----------------------------- CONFIG (edit these) ---------------------------
BASE_PATH = "/path/to/Redlining_city_tile/"      # one sub-folder per city
OUTPUT_FILENAME = "Tract_Level_Ecos_Capa_Results.csv"
# -----------------------------------------------------------------------------

# race population columns used to form the tract denominator
U7L_COLS = [
    "U7L003_tot", "U7L004_tot", "U7L005_tot", "U7L006_tot",
    "U7L007_tot", "U7L008_tot", "U7L009_tot", "U7L010_tot",
]

# per-type PM2.5 removal coefficients
VEG_COEF = {
    "pix_2": 0.0057,
    "pix_4": 0.0356,
    "pix_6": 0.0076,
    "pix_8": 0.0033,
    "pix_10": 0.0162,
    "pix_12": 0.0143,
    "pix_13": 0.0150,
    "pix_14": 0.0142,
}

results = []

# ----------------------------- per-city loop ---------------------------------
for city_dir in os.listdir(BASE_PATH):
    city_path = os.path.join(BASE_PATH, city_dir)
    census_path = os.path.join(city_path, "Census2020")

    if os.path.isdir(city_path) and os.path.exists(census_path):
        print(f"Processing city: {city_dir}")

        search_pattern = os.path.join(census_path, "*_BLOCK-level-GE-redline2.csv")
        csv_files = glob.glob(search_pattern)

        for file_path in csv_files:
            try:
                df = pd.read_csv(file_path)

                # avoid division by zero
                df["pix_total"] = df["pix_total"].replace(0, np.nan)

                # block-level ecosystem service
                df["Ecos_row"] = df["row_pop_total"] * (
                    sum(df[col] * coef for col, coef in VEG_COEF.items())
                ) / df["pix_total"]

                df["Ecos_row"] = df["Ecos_row"].fillna(0)

                # aggregate to tract
                group_cols = ["STATEFP20", "COUNTYFP20", "TRACTCE20"]
                agg_dict = {col: "first" for col in U7L_COLS}
                agg_dict["Ecos_row"] = "sum"

                tract_df = df.groupby(group_cols).agg(agg_dict).reset_index()

                # capacity per resident (scaled by 100)
                tract_df["U7L_sum"] = tract_df[U7L_COLS].sum(axis=1)
                tract_df["U7L_sum_valid"] = tract_df["U7L_sum"].replace(0, np.nan)

                tract_df["Ecos_capa"] = (tract_df["Ecos_row"] / tract_df["U7L_sum_valid"]) * 100
                tract_df["Ecos_capa"] = tract_df["Ecos_capa"].fillna(0)

                final_tract_df = tract_df[
                    ["STATEFP20", "COUNTYFP20", "TRACTCE20", "Ecos_capa"]
                ].copy()

                results.append(final_tract_df)

            except Exception as e:
                print(f"Error processing {file_path}: {e}")

# ----------------------------- merge & save ----------------------------------
if results:
    final_output = pd.concat(results, ignore_index=True)
    final_output.to_csv(OUTPUT_FILENAME, index=False)
    print(f"\nDone. Result (scaled by 100) saved to: {OUTPUT_FILENAME}")
else:
    print("No qualifying data files found.")
