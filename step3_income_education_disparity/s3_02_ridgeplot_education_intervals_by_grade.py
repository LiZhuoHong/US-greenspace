"""
Step 3 (Figure 3) - 2/3
Ridgeline plots of residents' greenspace exposure by EDUCATION interval and
redlining grade, for tree / shrub / grass separately (one figure per city).

For a city's tract-summary table, tracts are grouped into education-score
intervals (edu_bins). Within each interval, a KDE ridge is drawn per grade for
each of the three greenspace types (GE_all_Tr, GE_all_Sh, GE_all_Gr).

Input : <city>_tract_summary.csv
        (needs columns edu_score_wmean, grade_mode, GE_all_Tr/Sh/Gr)
Output: one SVG per city.

NOTE: Edit the CITIES list below before running.
"""

import matplotlib
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import gaussian_kde

# keep text as text (not paths) in the SVG
matplotlib.rcParams["svg.fonttype"] = "none"

# ----------------------------- CONFIG (edit these) ---------------------------
# list of (csv_path, city_display_name, output_svg)
CITIES = [
    ("/path/to/Chicago__IL_tract_summary.csv", "Chicago, IL", "Chicago_GE_ridgeplot.svg"),
    ("/path/to/Manhattan__NY_tract_summary.csv", "Manhattan, NY", "Manhattan_GE_ridgeplot.svg"),
]
# -----------------------------------------------------------------------------

Y_VARS = ["GE_all_Tr", "GE_all_Sh", "GE_all_Gr"]   # tree / shrub / grass
GRADES = ["A", "B", "C", "D"]
GRADE_COLORS = {"A": "#87B367", "B": "#90C5BF", "C": "#E0D961", "D": "#EC8590"}
SCALE = 1e3
OVERLAP = 0.7
ROW_H = 0.6
EDU_BINS = [0, 12, 14, 16, 21]   # education-score interval edges: [0,12], (12,14], (14,16], (16,21]

for path, city_name, save_name in CITIES:

    # ----------------------- read data ---------------------------------------
    df = pd.read_csv(path)
    cols = ["edu_score_wmean", "grade_mode"] + Y_VARS
    df = df[cols].dropna()
    df["grade_mode"] = df["grade_mode"].astype(str).str.strip().str.upper()
    df = df[df["grade_mode"].isin(GRADES)]

    df["edu_bin"] = pd.cut(df["edu_score_wmean"], bins=EDU_BINS, include_lowest=True)
    bin_order = sorted(df["edu_bin"].unique())
    n_bins_actual = len(bin_order)

    current_bin_labels = [f"{int(iv.left)}-{int(iv.right)}" for iv in bin_order]

    # ----------------------- plot --------------------------------------------
    fig, axes = plt.subplots(1, 3, figsize=(5.9 * 3.55 / 3.66, 5.5))

    for ax, yvar in zip(axes, Y_VARS):
        all_vals = df[yvar].dropna().values * SCALE
        x_min, x_max = all_vals.min(), all_vals.max()
        x_grid = np.linspace(x_min, x_max, 300)

        for bi, bin_iv in enumerate(bin_order):
            y_base = bi * ROW_H   # low interval at bottom

            # alternating background stripes
            if bi % 2 == 0:
                ax.axhspan(y_base - ROW_H * 0.5, y_base + ROW_H * 0.5, color="#f7f7f7", zorder=0)

            for grade in GRADES:
                mask = (df["edu_bin"] == bin_iv) & (df["grade_mode"] == grade)
                raw = df.loc[mask, yvar].values * SCALE
                if len(raw) < 3:
                    continue

                kde = gaussian_kde(raw, bw_method="scott")
                density = kde(x_grid)
                scale_h = ROW_H * OVERLAP / density.max()
                y_curve = y_base + density * scale_h

                ax.fill_between(x_grid, y_base, y_curve, color=GRADE_COLORS[grade], alpha=0.55, zorder=2)
                ax.plot(x_grid, y_curve, color=GRADE_COLORS[grade], linewidth=1.1, alpha=0.9, zorder=3)

        # y-axis
        ax.set_yticks([bi * ROW_H for bi in range(n_bins_actual)])
        ax.set_yticklabels(current_bin_labels, fontsize=8)

        for tick_label in ax.get_yticklabels():
            tick_label.set_rotation(90)
            tick_label.set_verticalalignment("center")

        ax.set_xlim(x_min - (x_max - x_min) * 0.02, x_max + (x_max - x_min) * 0.02)
        ax.set_ylim(-0.05, (n_bins_actual - 1 + OVERLAP + 0.1) * ROW_H)

        ax.set_xlabel("")
        ax.set_title(yvar, fontsize=11, fontweight="bold")
        ax.spines[["top", "right"]].set_visible(False)

    # ----------------------- title & legend ----------------------------------
    fig.suptitle(
        f"GE Distribution by Education Score Interval and Redlining Grade ({city_name})",
        fontsize=12, fontweight="bold", y=1.02,
    )

    legend_patches = [mpatches.Patch(color=GRADE_COLORS[g], label=f"Grade {g}") for g in GRADES]

    axes[0].set_ylabel("Education Score Interval", fontsize=10)
    axes[1].set_yticklabels([])
    axes[2].set_yticklabels([])

    # ----------------------- save --------------------------------------------
    plt.tight_layout()
    plt.savefig(save_name, format="svg", bbox_inches="tight")
    print(f"Saved vector figure: {save_name}")
    plt.show()
