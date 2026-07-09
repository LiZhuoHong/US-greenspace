"""
Step 1 (Figure 1) - 5/5
Compute Resident Greenspace Exposure (RGE / GE): the population-weighted
greenspace that residents are exposed to, broken down by race and vegetation
type.

Per block, per race group, per vegetation type:

    GE_<race>_<veg> = (veg_pixels / total_pixels)          # block greenspace share
                      * (block race population)            # who is exposed
                      / (tract total population of race)   # tract-level normaliser

Summing GE_<race>_<veg> over all blocks in a tract yields that race group's
population-weighted average vegetation exposure for the tract, so each block's
value is its contribution to the tract mean.

Aggregations produced:
    GE_<race>_tot  : sum over all vegetation types
    GE_<race>_Tr   : tree canopy   (EBL, DBL, ENL, DNL, Mix)
    GE_<race>_Sh   : shrub         (ES, DS)
    GE_all_Tr/Sh/Gr/tot : overall population-weighted exposure (city-level
                          normaliser; see note below)

NOTE ON SCALE: GE_<race>_* use a tract-level denominator, while GE_all_* keep a
city-level denominator. They therefore live on different normalisation scales
and GE_all_tot is not equal to the population-weighted sum of the per-race GE
columns. Keep this in mind for any cross-comparison.

Input per city : Census2020/<city>_pop-race-inc-edu.shp
Output per city: Census2020/<city>_block-level-GE-tract-level.shp

NOTE: Edit the CONFIG path below before running.
"""

import os

import geopandas as gpd
import numpy as np
import pandas as pd

# ----------------------------- CONFIG (edit these) ---------------------------
ROOT_DIR = "/path/to/Redlining_city_tile"      # one sub-folder per city
# -----------------------------------------------------------------------------

# census race field -> short label
RACE_MAP = {
    "U7L003": "Wh", "U7L004": "Bl", "U7L005": "AI",
    "U7L006": "As", "U7L007": "NH", "U7L008": "oth",
    "U7L009": "mul", "U7L010": "Hi",
}

# vegetation pixel column -> short label
PIX_MAP = {
    "pix_2": "EBL", "pix_4": "DBL", "pix_6": "ENL",
    "pix_8": "DNL", "pix_10": "Mix", "pix_12": "ES",
    "pix_13": "DS", "pix_14": "Gra",
}

BASE_FIELDS = [
    "STATEFP20", "COUNTYFP20", "TRACTCE20", "BLOCKCE20",
    "U7L003", "U7L004", "U7L005", "U7L006", "U7L007", "U7L008", "U7L009", "U7L010",
    "pix_total", "veg_total_", "veg_divers",
    "pix_2", "pix_4", "pix_6", "pix_8", "pix_10", "pix_12", "pix_13", "pix_14",
    "edu_score", "income_s_1", "income_sco",
]

U_FIELDS = list(RACE_MAP.keys())
PIX_FIELDS = list(PIX_MAP.keys())

TR_TYPES = ["EBL", "DBL", "ENL", "DNL", "Mix"]   # tree canopy classes
SH_TYPES = ["ES", "DS"]                          # shrub classes

for city in os.listdir(ROOT_DIR):
    city_path = os.path.join(ROOT_DIR, city)
    if not os.path.isdir(city_path):
        continue

    census_path = os.path.join(city_path, "Census2020")
    if not os.path.exists(census_path):
        continue

    for f in os.listdir(census_path):
        if not f.endswith("_pop-race-inc-edu.shp"):
            continue

        shp_path = os.path.join(census_path, f)
        print(f"\nProcessing: {shp_path}")

        gdf = gpd.read_file(shp_path)

        # fix income field name if needed
        if "income_s_1" not in gdf.columns and "income_sco" in gdf.columns:
            gdf["income_s_1"] = gdf["income_sco"]

        # ensure all expected fields exist
        for col in BASE_FIELDS:
            if col not in gdf.columns:
                gdf[col] = np.nan

        new_gdf = gdf[BASE_FIELDS + ["geometry"]].copy()

        # ----------------------- Step 1: block total population --------------
        new_gdf["row_pop_total"] = new_gdf[U_FIELDS].sum(axis=1)

        # ----------------------- Step 1.1: race population per tract ---------
        tract_race_pop = (
            new_gdf.groupby("TRACTCE20")[U_FIELDS]
            .sum()
            .reset_index()
            .set_index("TRACTCE20")
        )

        # ----------------------- Step 2: per-block GE (tract normaliser) -----
        for idx, row in new_gdf.iterrows():
            tract_id = row["TRACTCE20"]

            for U in U_FIELDS:
                race_short = RACE_MAP[U]
                total_race_pop = tract_race_pop.loc[tract_id, U]  # tract-level population

                # guard against zero tract race population
                if total_race_pop == 0 or pd.isna(total_race_pop):
                    for pix in PIX_FIELDS:
                        pix_short = PIX_MAP[pix]
                        new_gdf.loc[idx, f"GE_{race_short}_{pix_short}"] = 0
                    continue

                # GE = pixel proportion * block race pop / tract race pop
                for pix in PIX_FIELDS:
                    pix_short = PIX_MAP[pix]
                    col_name = f"GE_{race_short}_{pix_short}"

                    new_gdf.loc[idx, col_name] = (
                        (row[pix] / row["pix_total"]) * row[U] / total_race_pop
                    )

        # clean invalid values
        ge_cols = [c for c in new_gdf.columns if c.startswith("GE_")]
        new_gdf[ge_cols] = new_gdf[ge_cols].replace([np.inf, -np.inf], np.nan).fillna(0)

        # ----------------------- Step 3: GE_<race>_tot -----------------------
        for U in U_FIELDS:
            race_short = RACE_MAP[U]
            cols_to_sum = [f"GE_{race_short}_{PIX_MAP[pix]}" for pix in PIX_FIELDS]
            new_gdf[f"GE_{race_short}_tot"] = new_gdf[cols_to_sum].sum(axis=1)

        # ----------------------- Step 4: GE_<race>_Tr (trees) ----------------
        for U in U_FIELDS:
            race_short = RACE_MAP[U]
            tr_cols = [f"GE_{race_short}_{t}" for t in TR_TYPES]
            new_gdf[f"GE_{race_short}_Tr"] = new_gdf[tr_cols].sum(axis=1)

        # ----------------------- Step 5: GE_<race>_Sh (shrubs) ---------------
        for U in U_FIELDS:
            race_short = RACE_MAP[U]
            sh_cols = [f"GE_{race_short}_{t}" for t in SH_TYPES]
            new_gdf[f"GE_{race_short}_Sh"] = new_gdf[sh_cols].sum(axis=1)

        # ----------------------- Step 6: GE_all_* (city-level normaliser) ----
        city_total_pop = new_gdf["row_pop_total"].sum()

        new_gdf["GE_all_Tr"] = new_gdf["row_pop_total"] * (
            new_gdf[["pix_2", "pix_4", "pix_6", "pix_8", "pix_10"]].sum(axis=1) / new_gdf["pix_total"]
        ) / city_total_pop

        new_gdf["GE_all_Sh"] = new_gdf["row_pop_total"] * (
            new_gdf[["pix_12", "pix_13"]].sum(axis=1) / new_gdf["pix_total"]
        ) / city_total_pop

        new_gdf["GE_all_Gr"] = new_gdf["row_pop_total"] * (
            new_gdf["pix_14"] / new_gdf["pix_total"]
        ) / city_total_pop

        new_gdf["GE_all_tot"] = new_gdf["row_pop_total"] * (
            new_gdf[["pix_2", "pix_4", "pix_6", "pix_8", "pix_10", "pix_12", "pix_13", "pix_14"]].sum(axis=1)
            / new_gdf["pix_total"]
        ) / city_total_pop

        # ----------------------- Step 6.1: drop zero-population polygons ------
        new_gdf = new_gdf[~(new_gdf[U_FIELDS].sum(axis=1) == 0)].copy()

        # ----------------------- Step 7: cast numeric fields to float --------
        numeric_cols = [c for c in new_gdf.columns if c != "geometry"]
        for col in numeric_cols:
            new_gdf[col] = pd.to_numeric(new_gdf[col], errors="coerce")

        # ----------------------- Step 8: save --------------------------------
        out_name = f.replace("_pop-race-inc-edu.shp", "_block-level-GE-tract-level.shp")
        out_path = os.path.join(census_path, out_name)
        new_gdf.to_file(out_path)
        print(f"Saved -> {out_path}")
