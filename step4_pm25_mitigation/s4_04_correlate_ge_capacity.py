"""
Step 4 (Figure 4) - 4/4
For each city, correlate tract-level greenspace exposure (GE_all_tot) with
tract-level ecosystem-service capacity (Ecos_capa) using Pearson's r.

The per-city correlation and tract count feed the national maps of PM2.5
mitigation in Figure 4.

Input per city : <city>_tract_summary.shp   (needs GE_all_tot, Ecos_capa)
Output         : City_Pearson_Correlation.csv  (City_Name, Pcorr, N_tract)

NOTE: Edit the CONFIG path below before running.
"""

import glob
import os

import geopandas as gpd
import pandas as pd
from scipy.stats import pearsonr

# ----------------------------- CONFIG (edit these) ---------------------------
ROOT_DIR = "/path/to/Processed_Outputs"    # one sub-folder per city with *_tract_summary.shp
# -----------------------------------------------------------------------------

results = []

for city in os.listdir(ROOT_DIR):
    city_path = os.path.join(ROOT_DIR, city)

    if not os.path.isdir(city_path):
        continue

    shp_files = glob.glob(os.path.join(city_path, "*_tract_summary.shp"))

    if len(shp_files) == 0:
        print(f"No shp found in {city}")
        continue

    shp_path = shp_files[0]

    try:
        gdf = gpd.read_file(shp_path)

        df = gdf[["GE_all_tot", "Ecos_capa"]].dropna()
        n_rows = len(df)

        if n_rows < 2:
            print(f"Not enough data in {city}")
            continue

        x = df["GE_all_tot"].astype(float)
        y = df["Ecos_capa"].astype(float)

        r, _ = pearsonr(x, y)

        results.append({
            "City_Name": city,
            "Pcorr": r,
            "N_tract": n_rows,
        })

        print(f"{city}: Pcorr={r:.4f}, N_tract={n_rows}")

    except Exception as e:
        print(f"Error processing {city}: {e}")

# ----------------------------- save ------------------------------------------
out_csv = os.path.join(ROOT_DIR, "City_Pearson_Correlation.csv")

results_df = pd.DataFrame(results)
results_df.to_csv(out_csv, index=False)

print("Finished!")
print("Saved to:", out_csv)
