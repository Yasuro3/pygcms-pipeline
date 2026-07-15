#!/usr/bin/env python3
"""Generate the four publication figures for the PyGCMS Pipeline article.

Outputs vector PDF/SVG plus high-resolution PNG/TIFF.  Figures 1-3 are line
art at 1000 dpi; Figure 4 is a quantitative combination figure at 600 dpi.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle
from PIL import Image

mpl.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 8.0,
    "axes.labelsize": 8.5,
    "xtick.labelsize": 7.1,
    "ytick.labelsize": 7.2,
    "legend.fontsize": 6.6,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "svg.fonttype": "none",
})
WIDTH_IN = 190 / 25.4
CHECK_ONLY = False


def save_all(fig: plt.Figure, outbase: Path, dpi: int) -> None:
    """Save publication assets, or only a lightweight PDF during test runs."""
    outbase.parent.mkdir(parents=True, exist_ok=True)
    kwargs = dict(bbox_inches="tight", pad_inches=0.04, facecolor="white")
    fig.savefig(outbase.with_suffix(".pdf"), **kwargs)
    if CHECK_ONLY:
        return
    fig.savefig(outbase.with_suffix(".svg"), **kwargs)
    fig.savefig(outbase.with_suffix(".png"), dpi=dpi, **kwargs)
    tmp = outbase.with_suffix(".tmp.png")
    fig.savefig(tmp, dpi=dpi, **kwargs)
    image = Image.open(tmp).convert("RGB")
    image.save(outbase.with_suffix(".tiff"), dpi=(dpi, dpi), compression="tiff_lzw")
    tmp.unlink(missing_ok=True)


def box(ax, x, y, w, h, title, lines=(), linestyle="-", fontsize=7.4):
    patch = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.012,rounding_size=0.012",
        linewidth=1.0, linestyle=linestyle, facecolor="white", edgecolor="black",
    )
    ax.add_patch(patch)
    ax.text(x + w / 2, y + h * 0.72, title, ha="center", va="center", fontweight="bold", fontsize=fontsize)
    if lines:
        ax.text(x + w / 2, y + h * 0.35, "\n".join(lines), ha="center", va="center", fontsize=fontsize - 0.7, linespacing=1.12)
    return patch


def arrow(ax, x1, y1, x2, y2, label=None, linestyle="-", rad=0.0):
    item = FancyArrowPatch(
        (x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=10,
        linewidth=1.0, linestyle=linestyle, color="black", connectionstyle=f"arc3,rad={rad}",
    )
    ax.add_patch(item)
    if label:
        ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 0.018, label, ha="center", va="bottom", fontsize=6.3)


def figure1(outdir: Path) -> None:
    fig, ax = plt.subplots(figsize=(WIDTH_IN, 4.55))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")

    box(ax, 0.02, 0.66, 0.12, 0.18, "Instrument\ndata", ("vendor-native", "files"), fontsize=6.4)
    box(ax, 0.17, 0.66, 0.15, 0.18, "Authorized\nconversion", ("version + settings", "input/output hashes"), fontsize=6.4)
    box(ax, 0.36, 0.66, 0.11, 0.18, "mzML", ("nominal mass", "MS1 full scan"), fontsize=6.4)
    box(ax, 0.52, 0.57, 0.25, 0.36, "PyGCMS Pipeline", (
        "restricted mzML reader",
        "configurable peak detection",
        "ion-trace modelling and grouping",
        "component-spectrum construction",
        "candidate-preserving controller",
    ), fontsize=6.5)
    box(ax, 0.82, 0.66, 0.16, 0.18, "NIST MS Search", ("local licensed copy", "top-N candidates"), linestyle="--", fontsize=6.3)

    arrow(ax, 0.14, 0.75, 0.17, 0.75)
    arrow(ax, 0.32, 0.75, 0.36, 0.75)
    arrow(ax, 0.47, 0.75, 0.52, 0.75)
    arrow(ax, 0.77, 0.75, 0.82, 0.75)
    arrow(ax, 0.82, 0.69, 0.77, 0.63, linestyle="--", rad=-0.12)

    box(ax, 0.08, 0.18, 0.25, 0.24, "User-adjustable preset", (
        "detection and peak-width controls",
        "ion-model and correlation controls",
        "export / import parameter JSON",
    ), fontsize=6.5)
    box(ax, 0.39, 0.18, 0.22, 0.24, "Evidence and review", (
        "spectral scores and RI",
        "literature and matrix rules",
        "optional model advice",
    ), fontsize=6.5)
    box(ax, 0.67, 0.14, 0.31, 0.30, "Auditable export", (
        "all candidates and scores",
        "selected rank and rationale",
        "parameter preset and software hash",
        "conversion / NIST / AI provenance",
        "CSV + JSON + YAML manifests",
    ), fontsize=6.5)

    arrow(ax, 0.63, 0.57, 0.25, 0.42, rad=0.05)
    arrow(ax, 0.33, 0.30, 0.39, 0.30)
    arrow(ax, 0.61, 0.30, 0.67, 0.30)
    arrow(ax, 0.33, 0.22, 0.67, 0.20, linestyle="--", rad=0.07)

    ax.text(0.02, 0.055, "Public archive boundary: mzML-only source, documentation, example data, scripts, parameter records, and checksums", fontsize=6.4, ha="left", va="center")
    ax.text(0.98, 0.965, "Dashed: separately licensed or optional external resource", fontsize=6.1, ha="right", va="top")
    save_all(fig, outdir / "Figure_1_Architecture_and_data_flow", 1000)
    plt.close(fig)


def figure2(outdir: Path) -> None:
    fig, ax = plt.subplots(figsize=(WIDTH_IN, 4.90))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")

    xs = [0.02, 0.215, 0.41, 0.605, 0.80]
    widths = [0.17, 0.17, 0.17, 0.17, 0.18]
    titles = ["Full-scan\nGC-MS", "Configurable\ndeconvolution", "Library\ncandidates", "Evidence\nassessment", "Comprehensive\nrecord"]
    details = [
        ("scan time", "m/z-intensity arrays"),
        ("adjustable settings", "component spectrum"),
        ("top-N retained", "MF / RMF / probability"),
        ("local QC + RI", "optional model advice"),
        ("all candidates", "decision + provenance"),
    ]
    for x, w, title, detail in zip(xs, widths, titles, details):
        box(ax, x, 0.68, w, 0.23, title, detail, fontsize=6.35)
    for i in range(4):
        arrow(ax, xs[i] + widths[i], 0.795, xs[i + 1], 0.795)

    # Parameter panel
    ax.add_patch(FancyBboxPatch((0.02, 0.31), 0.35, 0.27, boxstyle="round,pad=0.012", facecolor="white", edgecolor="black"))
    ax.text(0.195, 0.545, "Optimization preset", ha="center", fontweight="bold", fontsize=7.0)
    parameter_lines = [
        "Detection - min RT, TIC, separation",
        "Geometry - half-window",
        "Ion model - apex, trace, sharpness",
        "Selection - fraction and maximum ions",
        "Spectrum - correlation, cutoff, bleed",
    ]
    for i, value in enumerate(parameter_lines):
        ax.text(0.038, 0.505 - i * 0.037, u"• " + value, fontsize=5.4, ha="left")
    ax.text(0.195, 0.315, "Export / import the exact JSON preset", fontsize=6.0, fontweight="bold", ha="center")
    arrow(ax, 0.195, 0.58, 0.29, 0.68, linestyle="--", rad=-0.05)

    # Candidate stack
    ax.text(0.50, 0.565, "Alternatives retained", fontsize=6.6, fontweight="bold", ha="center")
    for i, (rank, name, score) in enumerate([
        (1, "Phenol", "MF 874 / RMF 921"),
        (2, "2-Methylphenol", "MF 852 / RMF 904"),
        (3, "Anisole", "MF 801 / RMF 845"),
    ]):
        y = 0.495 - i * 0.073
        ax.add_patch(Rectangle((0.415, y), 0.18, 0.058, fill=False, linewidth=0.8))
        ax.text(0.423, y + 0.038, f"Rank {rank}: {name}", fontsize=5.55, ha="left", va="center")
        ax.text(0.423, y + 0.015, score, fontsize=5.35, ha="left", va="center")

    # Evidence panel
    ax.add_patch(FancyBboxPatch((0.63, 0.31), 0.35, 0.27, boxstyle="round,pad=0.012", facecolor="white", edgecolor="black"))
    ax.text(0.805, 0.545, "Evidence retained per candidate", fontweight="bold", fontsize=6.9, ha="center")
    evidence = [
        "original rank, MF, RMF, probability",
        "calculated and reference RI",
        "diagnostic-ion and matrix flags",
        "literature class and source",
        "model advice (if used) + human rationale",
    ]
    for i, value in enumerate(evidence):
        ax.text(0.647, 0.495 - i * 0.043, u"• " + value, fontsize=5.9, ha="left")

    ax.text(0.50, 0.255, "Candidate selection changes status and rationale - it does not delete ranks 2-N.", ha="center", fontsize=6.7, fontweight="bold")

    ax.add_patch(FancyBboxPatch((0.02, 0.055), 0.96, 0.14, boxstyle="round,pad=0.012", facecolor="white", edgecolor="black", linestyle="--"))
    ax.text(0.13, 0.145, "Top-hit-only table", fontsize=6.5, fontweight="bold", ha="center")
    ax.text(0.13, 0.095, "Rank 1 retained\nRanks 2-N unavailable", fontsize=5.8, ha="center", va="center")
    arrow(ax, 0.24, 0.125, 0.35, 0.125)
    ax.text(0.50, 0.145, "Candidate-preserving table", fontsize=6.5, fontweight="bold", ha="center")
    ax.text(0.50, 0.095, "Ranks 1-N + scores + evidence", fontsize=5.8, ha="center", va="center")
    arrow(ax, 0.64, 0.125, 0.75, 0.125)
    ax.text(0.87, 0.145, "Later reinterpretation", fontsize=6.5, fontweight="bold", ha="center")
    ax.text(0.87, 0.095, "No repeat library search required", fontsize=5.8, ha="center", va="center")

    save_all(fig, outdir / "Figure_2_Candidate_preserving_workflow", 1000)
    plt.close(fig)

def figure3(outdir: Path) -> None:
    fig, ax = plt.subplots(figsize=(WIDTH_IN, 4.60))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    ax.text(0.02, 0.965, "Illustrative synthetic export record", fontsize=9.2, fontweight="bold", va="top")
    ax.text(0.98, 0.965, "Schema example; not an experimental identification.", fontsize=6.7, ha="right", va="top")

    header = [("sample_id", "synthetic_gc_ms"), ("scan", "2"), ("RT_min", "0.50"), ("TIC", "350"), ("component_id", "synthetic_gc_ms__0002")]
    x = 0.02
    for key, value in header:
        w = 0.20 if key == "component_id" else 0.14
        ax.add_patch(Rectangle((x, 0.82), w, 0.10, fill=False, linewidth=0.8))
        ax.text(x + 0.007, 0.884, key, fontsize=5.8, fontweight="bold", ha="left")
        ax.text(x + 0.007, 0.845, value, fontsize=6.4, ha="left")
        x += w

    cols = ["rank", "candidate", "CAS", "MF", "RMF", "Prob.", "class", "status"]
    widths = [0.06, 0.20, 0.12, 0.07, 0.07, 0.08, 0.16, 0.14]
    rows = [
        ["1", "Phenol", "108-95-2", "874", "921", "62.4", "phenolic", "selected"],
        ["2", "2-Methylphenol", "95-48-7", "852", "904", "23.1", "phenolic", "retained"],
        ["3", "Anisole", "100-66-3", "801", "845", "8.9", "methoxy aromatic", "retained"],
    ]
    x0, ytop, rh = 0.02, 0.73, 0.074
    x = x0
    for col, w in zip(cols, widths):
        ax.add_patch(Rectangle((x, ytop), w, rh, fill=False, linewidth=0.9))
        ax.text(x + w / 2, ytop + rh / 2, col, ha="center", va="center", fontsize=6.0, fontweight="bold")
        x += w
    for row_index, row in enumerate(rows):
        y = ytop - (row_index + 1) * rh
        x = x0
        for value, w in zip(row, widths):
            ax.add_patch(Rectangle((x, y), w, rh, fill=False, linewidth=0.7))
            ha = "left" if w > 0.10 else "center"
            ax.text(x + 0.006 if ha == "left" else x + w / 2, y + rh / 2, value, ha=ha, va="center", fontsize=5.9)
            x += w

    box(ax, 0.02, 0.25, 0.45, 0.19, "Decision record", (
        "selected_rank = 1",
        "mode = deterministic local review",
        "reason = strongest combined evidence",
        "alternative ranks retained",
    ), fontsize=6.5)
    box(ax, 0.51, 0.25, 0.47, 0.19, "Run provenance", (
        "deconvolution_parameters.json + software hash",
        "converter and mzML hashes + NIST configuration",
        "literature database version + optional AI record",
    ))
    ax.text(0.02, 0.165, "Machine-readable companion files", fontweight="bold", fontsize=7.1)
    ax.text(0.02, 0.123, "components.csv  -  candidates.csv  -  deconvolution_parameters.json  -  run_manifest.json  -  checksums.sha256", fontsize=6.2)
    ax.text(0.02, 0.058, "Adjustable processing remains reproducible because the exact preset is exported with the result.", fontsize=6.9, fontweight="bold")
    save_all(fig, outdir / "Figure_3_Representative_export_record", 1000)
    plt.close(fig)


def figure4(outdir: Path, class_summary: Path) -> None:
    df = pd.read_csv(class_summary)
    # Display analytical fractions in two contiguous blocks: TD L1-L5, then Py L1-L5.
    fraction_order = pd.CategoricalDtype(categories=["TD", "PY"], ordered=True)
    df["Fraction"] = df["Fraction"].astype(str).str.upper().astype(fraction_order)
    df["Layer_order"] = pd.to_numeric(df["Layer"].astype(str).str.extract(r"(\d+)")[0], errors="raise")
    df = df.sort_values(["Fraction", "Layer_order"], kind="stable").reset_index(drop=True)
    class_cols = [c for c in df.columns if str(c).startswith("%_")]
    labels = {
        "%_Aliphatics_F": "Aliphatics",
        "%_Furans_C": "Furans / carbohydrate products",
        "%_Oaromatics_L": "Oxygenated aromatics",
        "%_Ncomp_P": "N-containing compounds",
        "%_AromCarbonyl_O": "Aromatic carbonyls / oxygenates",
    }
    classified = pd.to_numeric(df["Classified"]).to_numpy(float)

    raw = df[class_cols].apply(pd.to_numeric).to_numpy(float)
    row_sums = raw.sum(axis=1)
    if np.any(row_sums <= 0):
        raise ValueError("Every run must contain positive classified percentages.")
    normalized = raw / row_sums[:, None] * 100.0

    fig, ax = plt.subplots(figsize=(WIDTH_IN, 4.75))
    # Leave a visual gap between the two analytical fractions.
    n_td = int((df["Fraction"].astype(str) == "TD").sum())
    n_py = int((df["Fraction"].astype(str) == "PY").sum())
    x = np.concatenate([np.arange(n_td, dtype=float), np.arange(n_py, dtype=float) + n_td + 1.15])
    bottom = np.zeros(len(df))
    hatches = ["", "///", "\\", "xx", ".."]
    for index, column in enumerate(class_cols):
        values = normalized[:, index]
        ax.bar(
            x, values, bottom=bottom, label=labels.get(column, column.removeprefix("%_").replace("_", " ")),
            edgecolor="black", linewidth=0.35, hatch=hatches[index % len(hatches)],
        )
        bottom += values

    run_labels = [
        f"{layer}\nn={int(c)}"
        for layer, c in zip(df["Layer"], classified)
    ]
    ax.set_ylim(0, 100)
    ax.set_ylabel("Composition within classified records (%)")
    ax.set_xticks(x)
    ax.set_xticklabels(run_labels, rotation=0, ha="center")
    ax.grid(axis="y", linewidth=0.35, alpha=0.5)
    ax.legend(title="Literature-guided class", bbox_to_anchor=(1.01, 1), loc="upper left", frameon=False)
    ax.text(
        0.0, 1.055,
        "Classified records only; n gives the number of classified records in each run.",
        transform=ax.transAxes, fontsize=6.9, ha="left",
    )
    # Fraction headings are placed below the run labels so the two blocks read independently.
    td_center = float(np.mean(x[:n_td])) if n_td else 0.0
    py_center = float(np.mean(x[n_td:])) if n_py else 0.0
    ax.text(td_center, -18.5, "Thermal desorption (TD)", ha="center", va="top", fontsize=7.4, fontweight="bold", clip_on=False)
    ax.text(py_center, -18.5, "Pyrolysis (Py)", ha="center", va="top", fontsize=7.4, fontweight="bold", clip_on=False)
    if n_td and n_py:
        separator = (x[n_td - 1] + x[n_td]) / 2
        ax.axvline(separator, color="black", linewidth=0.55, linestyle="--", alpha=0.65)
    fig.subplots_adjust(right=0.72, bottom=0.25, top=0.88)
    save_all(fig, outdir / "Figure_4_Classified_NOM_class_composition", 600)
    plt.close(fig)


def write_captions(outdir: Path) -> None:
    text = """# Figure captions

**Figure 1.** Architecture and data flow of PyGCMS Pipeline. Vendor-native files are converted outside the archived application using authorized software, and the converter version, settings, and file hashes are recorded. The public application reads nominal-mass, MS1, full-scan mzML; performs configurable peak detection, local ion-trace modelling, coelution grouping, and component-spectrum construction; submits spectra to a locally licensed NIST MS Search installation; preserves the returned top-N candidates; and exports decisions and run provenance. Dashed boxes denote separately licensed or optional external resources.

**Figure 2.** Configurable deconvolution and candidate-preserving interpretation. User-adjustable controls govern retention-time exclusion, TIC peak detection, peak separation, local window width, ion-trace quality, shape correlation, model-ion selection, spectral cutoff, and bleed filtering. The active preset can be exported and re-imported. All NIST candidates and original scores are retained; deterministic evidence and optional model review can support selection but do not delete alternatives. The inset contrasts this design with top-hit-only reporting.

**Figure 3.** Representative structure of an exported component record using synthetic values. The export links a component to its complete candidate table, selected rank, human-readable rationale, deconvolution-parameter preset, converter record, NIST configuration, software hash, and optional model provenance. Values illustrate the schema and are not experimental results.

**Figure 4.** Literature-guided class composition of classified component records from Lake Biwa core 17B. Thermal-desorption runs (TD) are shown first from L1 to L5, followed by pyrolysis runs (Py) from L1 to L5; L1-L5 correspond to 0-1, 1-2, 2-4, 4-10, and 10-20 cm, respectively, and each bar is normalized to 100% across the five assigned classes. One-decimal source percentages were renormalized row-wise to correct minor rounding drift. Unclassified records remain archived but are excluded from the denominator because they include unresolved or low-confidence signals and analytical-background features such as possible siloxane bleed. The plot reports component-count proportions within the classified subset, not abundance-weighted composition.
"""
    (outdir / "FIGURE_CAPTIONS.md").write_text(text, encoding="utf-8")


def main() -> None:
    global CHECK_ONLY
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", type=Path, required=True)
    parser.add_argument("--class-summary", type=Path, required=True)
    parser.add_argument(
        "--check-only", action="store_true",
        help="Generate lightweight PDF outputs only; intended for automated checks.",
    )
    args = parser.parse_args()
    CHECK_ONLY = args.check_only
    args.outdir.mkdir(parents=True, exist_ok=True)
    figure1(args.outdir)
    figure2(args.outdir)
    figure3(args.outdir)
    figure4(args.outdir, args.class_summary)
    write_captions(args.outdir)


if __name__ == "__main__":
    main()
