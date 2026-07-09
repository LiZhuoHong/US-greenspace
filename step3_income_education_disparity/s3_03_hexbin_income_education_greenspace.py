"""
Step 3 (Figure 3) - 3/3
Joint distribution of tract-level greenspace cover across the education-income
plane: a hexbin of (education score, household income) coloured by mean
greenspace cover, with marginal histograms and a linear fit.

Input : ALL_city_tract_summary-v2.csv
        (needs columns edu_score_wmean, income_s_1_wmean, All_cover)
Output: PNG figure.

NOTE: Edit the CONFIG paths below before running.
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import rcParams
from matplotlib.ticker import FuncFormatter

# ----------------------------- CONFIG (edit these) ---------------------------
CSV_PATH = "/path/to/ALL_city_tract_summary-v2.csv"
OUTPUT_PNG = "output_all_cover_with_fit.png"
# -----------------------------------------------------------------------------

# Nature-style sans-serif fonts
rcParams["font.family"] = "sans-serif"
rcParams["font.sans-serif"] = ["Helvetica", "Arial", "DejaVu Sans"]

df = pd.read_csv(CSV_PATH)

# drop rows where education or income is 0 or NaN
df = df[
    (df["edu_score_wmean"].notna()) & (df["edu_score_wmean"] != 0)
    & (df["income_s_1_wmean"].notna()) & (df["income_s_1_wmean"] != 0)
]

x = df["edu_score_wmean"]
y = df["income_s_1_wmean"]
z = df["All_cover"]

# ----------------------------- figure layout ---------------------------------
fig = plt.figure(figsize=(8, 8))
gs = fig.add_gridspec(
    4, 4, height_ratios=[1, 3, 3, 3], width_ratios=[3, 3, 3, 1],
    hspace=0.05, wspace=0.05,
)

ax_main = fig.add_subplot(gs[1:4, 0:3])
ax_xhist = fig.add_subplot(gs[0, 0:3], sharex=ax_main)
ax_yhist = fig.add_subplot(gs[1:4, 3], sharey=ax_main)

# ----------------------------- hexbin main panel -----------------------------
hb = ax_main.hexbin(x, y, C=z, gridsize=35, cmap="YlGn", reduce_C_function=np.mean)

# linear fit y ~ x
coeffs = np.polyfit(x, y, deg=1)
x_fit = np.linspace(x.min(), x.max(), 100)
y_fit = np.polyval(coeffs, x_fit)
ax_main.plot(x_fit, y_fit, color="red", linestyle="--", linewidth=2, label="Linear fit")

ax_main.set_xlabel("Education score", fontsize=13)
ax_main.set_ylabel("Annual household income (USD)", fontsize=13)

fig.suptitle(
    "Tract-level greenspace disparity by education & income",
    fontsize=14, fontweight="bold", y=0.94,
)


# y-axis in thousands
def k_format(val, pos):
    return f"{int(val/1000)}k"


ax_main.yaxis.set_major_formatter(FuncFormatter(k_format))

# ----------------------------- marginal histograms ---------------------------
ax_xhist.hist(x, bins=30, color="gray")
ax_yhist.hist(y, bins=30, orientation="horizontal", color="gray")

ax_xhist.set_ylabel("Tract count", fontsize=13)
ax_yhist.set_xlabel("Tract count", fontsize=13)

plt.setp(ax_xhist.get_xticklabels(), visible=False)
plt.setp(ax_yhist.get_yticklabels(), visible=False)

# colorbar
cb = fig.colorbar(hb, ax=[ax_main, ax_xhist, ax_yhist], orientation="vertical")
cb.set_label("Greenspace cover", fontsize=12)

ax_main.legend(fontsize=12)

plt.savefig(OUTPUT_PNG, dpi=200, bbox_inches="tight")
plt.show()
