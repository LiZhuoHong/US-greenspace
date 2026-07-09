#!/usr/bin/env Rscript
# =============================================================================
# Inter-grade greenspace disparity across HOLC redlining grades (A, B, C, D)
# -----------------------------------------------------------------------------
# Robust, ordinal, directional replacement for the mean pairwise Wasserstein
# (Earth Mover's Distance) metric in ALL_cities_inter-grade-EMD-block.py.
#
# For every CITY and every VEGETATION TYPE it reports TWO scale-free disparity
# metrics for how greenspace exposure differs across the ordered HOLC gradient
# A>B>C>D. Both are rank-based, so they are robust to the heavy right-skew and
# the many exact zeros in the GE_* variables.
#
# Vegetation responses (one full set of metrics each):
#   GE_all_Tr  -> "tree"
#   GE_all_Sh  -> "shrub"
#   GE_all_Gr  -> "grass"
#   GE_all_tot -> "all"    (total vegetation; the variable used in the .py)
#
# --------------------------- THE TWO METRICS ---------------------------------
#   1) kendall_tau_b      Kendall's tau-b between grade score (A=1..D=4) and
#                         greenspace. Standardized [-1,1], directional, uses the
#                         full A<B<C<D ordering ("dose-response").
#   2) cliff_delta_AvsD   Cliff's dominance delta for grade A vs grade D,
#                         standardized [-1,1].
#   Both are SCALE-FREE, so they are directly comparable across all cities and
#   vegetation types regardless of a city's overall greenness.
#
# ====================== SIGN CONVENTIONS (disparity!) ========================
#   kendall_tau_b     NEGATIVE  = disparity  (greenspace DECLINES A -> D)
#   cliff_delta_AvsD  POSITIVE  = disparity  (grade-A blocks dominate grade-D)
#
#   The more negative tau_b, or the more positive cliff_delta, the LARGER the
#   greenspace disparity (less green in worse-graded areas). NB: the two carry
#   OPPOSITE signs for the SAME gap, because tau_b runs along A->D (worsening)
#   while cliff_delta is oriented A vs D (best vs redlined).
#
# Inference: kendall_p (+ FDR) tests tau_b; AvsD_p (+ FDR), the Mann-Whitney
# test of grade A vs grade D, is the significance test for cliff_delta.
# p-values are FDR-corrected (Benjamini-Hochberg) across cities within each
# vegetation type.
# =============================================================================

# ================== Modify these lines ==================
csv_path    <- Sys.getenv("GRADE_CSV",
  "/path/to/ALL_cities_BLOCK-level-GE-redline.csv")
# cluster path:
#   "/storage/group/tvq5043/default/Zhuohong/HR_mapping_216MSA/Redlining_city_tile/ALL_cities_BLOCK-level-GE-redline.csv"
output_path <- Sys.getenv("GRADE_OUT",
  "/path/to/ALL_cities_inter-grade-disparity-block.csv")

min_n_per_grade <- as.integer(Sys.getenv("GRADE_MIN_N", "5"))    # min blocks in EACH grade A-D (default 5; override with GRADE_MIN_N)
# ========================================================

suppressMessages({
  if (!requireNamespace("data.table", quietly = TRUE))
    install.packages("data.table", repos = "https://cloud.r-project.org")
  library(data.table)
})

veg_map <- c(tree = "GE_all_Tr", shrub = "GE_all_Sh",
             grass = "GE_all_Gr", all  = "GE_all_tot")
ge_cols <- unname(veg_map)
grades  <- c("A", "B", "C", "D")

# ---- read only the needed columns (fast & memory-light on the ~585 MB file) ---
message("Reading: ", csv_path)
DT <- fread(csv_path, select = c("city", "grade", ge_cols), showProgress = TRUE)

# ---- clean -------------------------------------------------------------------
DT <- DT[grade %chin% grades]                                  # drop E / _Darien / etc.
suppressWarnings(DT[, (ge_cols) := lapply(.SD, as.numeric), .SDcols = ge_cols])
DT[, grade := factor(grade, levels = grades, ordered = TRUE)]
message("Rows after filtering to A/B/C/D: ", format(nrow(DT), big.mark = ","),
        " | cities: ", uniqueN(DT$city))

# ---- the two disparity metrics, per (city, veg) -----------------------------
analyze_disparity <- function(value, grade) {
  keep  <- is.finite(value)
  value <- value[keep]
  grade <- factor(as.character(grade[keep]), levels = grades, ordered = TRUE)
  ns    <- table(grade)

  out <- list(
    n_total = length(value),
    n_A = ns[["A"]], n_B = ns[["B"]], n_C = ns[["C"]], n_D = ns[["D"]],
    kendall_tau_b = NA_real_, kendall_p = NA_real_,   # metric 1 (NEG = disparity)
    cliff_delta_AvsD = NA_real_,                      # metric 2 (POS = disparity)
    AvsD_p = NA_real_,                                # significance for cliff_delta
    status = "ok"
  )
  if (any(ns < min_n_per_grade)) { out$status <- "insufficient_n"; return(out) }
  if (length(unique(value)) < 2L) { out$status <- "no_variation";  return(out) }

  # --- Metric 1: Kendall's tau-b between grade score (A=1..D=4) and greenspace
  #     tau_b < 0  => greenspace DECLINES A -> D  => DISPARITY (redlining penalty)
  #     tau_b > 0  => greenspace increases toward D (reverse pattern)
  gscore <- as.integer(grade)
  kt <- suppressWarnings(cor.test(gscore, value, method = "kendall"))
  out$kendall_tau_b <- unname(kt$estimate)
  out$kendall_p     <- kt$p.value

  # --- Metric 2: Cliff's delta for the extreme grade-A vs grade-D contrast -----
  #     Oriented A vs D (best vs redlined): POSITIVE = A dominates D = DISPARITY
  #     (opposite sign to tau_b for the same gap). Cliff's delta = 2W/(nA*nD) - 1
  #     (tie terms cancel exactly); +1 => every A block greener than every D block.
  a <- value[grade == "A"]; d <- value[grade == "D"]
  w <- suppressWarnings(wilcox.test(a, d))           # Mann-Whitney; W & p-value
  out$AvsD_p <- w$p.value
  out$cliff_delta_AvsD <- 2 * unname(w$statistic) / (length(a) * length(d)) - 1
  out
}

# ---- run for every vegetation type ------------------------------------------
results <- rbindlist(lapply(names(veg_map), function(vt) {
  col <- veg_map[[vt]]
  message("  computing: ", vt, "  (", col, ")")
  res <- DT[, analyze_disparity(get(col), grade), by = city]
  res[, veg_type := vt]
  res
}), fill = TRUE)

# ---- multiple-testing correction (BH/FDR) within each vegetation type --------
results[, kendall_p_fdr := p.adjust(kendall_p, "BH"), by = veg_type]
results[, AvsD_p_fdr    := p.adjust(AvsD_p,    "BH"), by = veg_type]

setcolorder(results, c(
  "city", "veg_type", "status", "n_total", "n_A", "n_B", "n_C", "n_D",
  "kendall_tau_b", "kendall_p", "kendall_p_fdr",   # metric 1: NEG = disparity
  "cliff_delta_AvsD", "AvsD_p", "AvsD_p_fdr"))     # metric 2: POS = disparity
setorder(results, veg_type, kendall_tau_b)         # most negative tau_b (most disparity) first

fwrite(results, output_path)

# ---- console summary ---------------------------------------------------------
message("\nSaved -> ", output_path,
        "   (", nrow(results), " city x veg_type rows; ",
        results[status == "ok", .N], " analysed, ",
        results[status != "ok", .N], " skipped)")

ok_all <- results[status == "ok" & veg_type == "all"]
if (nrow(ok_all)) {
  cat("\nTop 10 cities by largest greenspace disparity (veg = all):\n")
  cat("  tau_b most negative = most disparity; cliff most positive = most disparity\n")
  print(head(ok_all[order(kendall_tau_b), .(
    city,
    tau_b = round(kendall_tau_b, 3),
    tau_q = signif(kendall_p_fdr, 2),
    cliff = round(cliff_delta_AvsD, 3),
    AD_q  = signif(AvsD_p_fdr, 2))], 10), row.names = FALSE)
}
