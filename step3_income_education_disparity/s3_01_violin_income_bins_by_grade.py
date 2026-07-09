"""
Step 3 (Figure 3) - 1/3
Violin plots of residents' greenspace exposure by INCOME interval and redlining
grade, for tree / shrub / grass separately (one figure per city).

For a city's tract-summary table, tracts are binned into equal-width income
intervals; within each interval a violin (KDE), an IQR bar, and a median dot are
drawn per grade (A/B/C/D) for each of the three greenspace types
(GE_all_Tr, GE_all_Sh, GE_all_Gr).

Input : <city>_tract_summary.csv
        (needs columns income_sco_wmean, grade_mode, GE_all_Tr/Sh/Gr)
Output: one SVG per city.

NOTE: Edit the CITIES list below before running.
"""

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.interpolate import make_interp_spline
from scipy.stats import gaussian_kde

# ----------------------------- CONFIG (edit these) ---------------------------
# list of (csv_path, city_display_name, output_svg)
CITIES = [
    ("/path/to/Chicago__IL_tract_summary.csv", "Chicago, IL", "Chicago_GE_violin.svg"),
    ("/path/to/Manhattan__NY_tract_summary.csv", "Manhattan, NY", "Manhattan_GE_violin.svg"),
]
# -----------------------------------------------------------------------------

Y_VARS = ["GE_all_Tr", "GE_all_Sh", "GE_all_Gr"]   # tree / shrub / grass
GRADES = ["A", "B", "C", "D"]
GRADE_COLORS = {"A": "#87B367", "B": "#90C5BF", "C": "#E0D961", "D": "#EC8590"}

SCALE = 1e3        # display values in units of 1e-3
VIO_W = 0.105      # half-width of each violin
GRADE_SP = 0.225   # spacing between grades within a bin
BIN_SP = 1.25      # spacing between income bins
N_BINS = 6
UNIT = 1000        # income rounding unit (USD)


def plot_city(csv_path, city_name, save_name):
    df = pd.read_csv(csv_path)

    cols = ["income_sco_wmean", "grade_mode"] + Y_VARS
    df = df[cols].dropna()

    df["grade_mode"] = df["grade_mode"].astype(str).str.strip().str.upper()
    df = df[df["grade_mode"].isin(GRADES)]

    # ----------------------- income bins -------------------------------------
    vmin, vmax = df["income_sco_wmean"].min(), df["income_sco_wmean"].max()
    step_r = np.ceil((vmax - vmin) / N_BINS / UNIT) * UNIT
    lo = np.floor(vmin / UNIT) * UNIT
    hi = lo + step_r * N_BINS

    bin_edges = np.linspace(lo, hi, N_BINS + 1)
    df["income_bin"] = pd.cut(df["income_sco_wmean"], bins=bin_edges, include_lowest=True)

    bin_order = sorted(df["income_bin"].unique())
    bin_labels = [f"[{int(iv.left/1000)}, {int(iv.right/1000)}]" for iv in bin_order]

    x_centers = np.arange(len(bin_order)) * BIN_SP
    offsets = np.linspace(-(len(GRADES) - 1) / 2, (len(GRADES) - 1) / 2, len(GRADES)) * GRADE_SP

    # ----------------------- figure ------------------------------------------
    fig, axes = plt.subplots(3, 1, figsize=(8.8, 8.2), sharex=True)

    fig.suptitle(
        f"GE by Income Score Bin and Redlining Grade ({city_name})\n"
        "Violin = KDE  ·  Bar = IQR  ·  Dot = median",
        fontsize=15.5, fontweight="bold", y=0.98,
    )
    fig.supylabel("Residents' exposure to specific greenspace (10\u207b\u00b3)", fontsize=14.5, x=0.012)

    for ai, (ax, yvar) in enumerate(zip(axes, Y_VARS)):
        all_scaled = df[yvar].values * SCALE
        y_range = all_scaled.max() - all_scaled.min()
        ax.set_ylim(max(0, all_scaled.min() - y_range * 0.07), all_scaled.max() + y_range * 0.04)

        envelope_top = np.full(len(bin_order), np.nan)

        for bi, bin_iv in enumerate(bin_order):
            xc_base = x_centers[bi]
            bin_max_top = -np.inf

            for gi, grade in enumerate(GRADES):
                xc = xc_base + offsets[gi]

                mask = (df["income_bin"] == bin_iv) & (df["grade_mode"] == grade)
                raw = df.loc[mask, yvar].values * SCALE
                if len(raw) < 3:
                    continue

                c = GRADE_COLORS[grade]

                # violin (KDE clipped to central 95%)
                lo_cut, hi_cut = np.percentile(raw, [2.5, 97.5])
                kde = gaussian_kde(raw)
                y_grid = np.linspace(lo_cut, hi_cut, 200)
                density = kde(y_grid)
                hw = density / density.max() * VIO_W

                ax.fill_betweenx(y_grid, xc - hw, xc + hw, color=c, alpha=0.65, zorder=2)
                ax.plot(xc - hw, y_grid, color=c, lw=0.9)
                ax.plot(xc + hw, y_grid, color=c, lw=0.9)

                # IQR bar
                q1, q3 = np.percentile(raw, [25, 75])
                ax.plot([xc, xc], [q1, q3], color=c, lw=3.8, solid_capstyle="round", zorder=4)

                # median dot
                med = np.median(raw)
                ax.scatter(xc, med, color="white", s=30, edgecolors=c, linewidths=1.5, zorder=5)

                bin_max_top = max(bin_max_top, hi_cut)

            if bin_max_top > -np.inf:
                envelope_top[bi] = bin_max_top

        # ----------------------- envelope line -------------------------------
        valid = ~np.isnan(envelope_top)
        if valid.sum() >= 2:
            x_valid = x_centers[valid]
            y_valid = envelope_top[valid]

            if len(x_valid) >= 4:
                spl = make_interp_spline(x_valid, y_valid, k=3)
                xs = np.linspace(x_valid.min(), x_valid.max(), 400)
                ys = spl(xs)
            else:
                xs, ys = x_valid, y_valid

            ax.plot(xs, ys, color="0.6", linewidth=2.0, alpha=0.45, zorder=1)

        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(axis="both", labelsize=11.5)

    # x-axis
    axes[-1].set_xticks(x_centers)
    axes[-1].set_xticklabels(bin_labels, fontsize=11)
    axes[-1].set_xlabel("Income range (unit: $1,000)", fontsize=13.5)

    plt.tight_layout(rect=[0.04, 0, 1, 0.94])
    plt.savefig(save_name, bbox_inches="tight", format="svg")
    print(f"Saved vector figure: {save_name}")
    plt.show()


if __name__ == "__main__":
    for csv_path, city_name, save_name in CITIES:
        plot_city(csv_path, city_name, save_name)
