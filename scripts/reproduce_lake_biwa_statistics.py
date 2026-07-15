#!/usr/bin/env python3
"""Reproduce Lake Biwa class-summary statistics and optional candidate metrics.

The verified article-level totals are regenerated from
``data/application/17B_class_summary_percent.csv``.  Candidate-level metrics
are emitted only when an actual candidate table is supplied; the script never
substitutes values from a manuscript draft.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Optional

import pandas as pd

NA = {"", "na", "n/a", "none", "null", "nan", "unknown", "unclassified"}


def norm(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


def read_csv(path: Path) -> pd.DataFrame:
    errors: list[str] = []
    for encoding in ("utf-8-sig", "utf-8", "cp932", "latin1"):
        try:
            return pd.read_csv(path, encoding=encoding, low_memory=False)
        except Exception as exc:  # pragma: no cover - diagnostic path
            errors.append(f"{encoding}: {exc}")
    raise RuntimeError(f"Cannot read {path}: {' | '.join(errors)}")


def find_column(df: pd.DataFrame, *names: str) -> Optional[str]:
    mapping = {norm(c): str(c) for c in df.columns}
    for name in names:
        if norm(name) in mapping:
            return mapping[norm(name)]
    for key, original in mapping.items():
        if any(norm(name) in key for name in names):
            return original
    return None


def text_present(value: object) -> bool:
    if pd.isna(value):
        return False
    return str(value).strip().lower() not in NA


def summarize_class_table(path: Path, outdir: Path) -> dict:
    df = read_csv(path)
    required = ["Layer", "Depth_cm", "Fraction", "Components", "Classified"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Class-summary table lacks columns: {', '.join(missing)}")

    class_cols = [c for c in df.columns if str(c).startswith("%_")]
    if not class_cols:
        raise ValueError("No class-percentage columns beginning with '%_' were found.")

    df = df.copy()
    fraction_order = pd.CategoricalDtype(categories=["TD", "PY"], ordered=True)
    df["Fraction"] = df["Fraction"].astype(str).str.upper().astype(fraction_order)
    df["Layer_order"] = pd.to_numeric(df["Layer"].astype(str).str.extract(r"(\d+)")[0], errors="raise")
    df = df.sort_values(["Fraction", "Layer_order"], kind="stable").reset_index(drop=True)
    df["Components"] = pd.to_numeric(df["Components"], errors="raise").astype(int)
    df["Classified"] = pd.to_numeric(df["Classified"], errors="raise").astype(int)
    df["Excluded_or_unclassified"] = df["Components"] - df["Classified"]
    df["Group"] = df["Layer"].astype(str) + " | " + df["Depth_cm"].astype(str) + " | " + df["Fraction"].astype(str)

    label_map = {
        "%_Aliphatics_F": "Aliphatics",
        "%_Furans_C": "Furans / carbohydrate products",
        "%_Oaromatics_L": "Oxygenated aromatics",
        "%_Ncomp_P": "N-containing compounds",
        "%_AromCarbonyl_O": "Aromatic carbonyls / oxygenates",
    }

    long_rows: list[dict] = []
    for _, row in df.iterrows():
        raw_values = [float(row[column]) for column in class_cols]
        row_sum = sum(raw_values)
        if row_sum <= 0:
            raise ValueError(f"Non-positive classified-percentage sum for {row['Group']}")
        for column, raw_value in zip(class_cols, raw_values):
            long_rows.append({
                "Layer": row["Layer"],
                "Depth_cm": row["Depth_cm"],
                "Fraction": row["Fraction"],
                "Group": row["Group"],
                "Classified_records": int(row["Classified"]),
                "Category": label_map.get(column, column.removeprefix("%_").replace("_", " ")),
                "Source_percent_within_classified": raw_value,
                "Normalized_percent_within_classified": 100.0 * raw_value / row_sum,
                "Source_precision_note": "Source percentage rounded to one decimal; row renormalized to 100%",
            })

    composition = pd.DataFrame(long_rows)
    exclusions = df[[
        "Layer", "Depth_cm", "Fraction", "Group", "Components", "Classified", "Excluded_or_unclassified",
    ]].copy()
    exclusions["Interpretive_use"] = "Retained for audit; excluded from class-composition normalization"

    composition.to_csv(outdir / "class_composition_classified_records_percent.csv", index=False)
    exclusions.to_csv(outdir / "excluded_record_counts_by_sample.csv", index=False)


    total = int(df["Components"].sum())
    classified = int(df["Classified"].sum())
    unclassified = total - classified
    result = {
        "source": str(path),
        "runs": int(len(df)),
        "selected_component_records": total,
        "classified_records": classified,
        "excluded_or_unclassified_records": unclassified,
        "classified_fraction_for_accounting": 100.0 * classified / total if total else None,
        "class_percentage_precision": "one decimal within the classified subset",
    }
    return result


def summarize_candidate_table(path: Optional[Path]) -> dict:
    if path is None or not path.exists():
        return {"available": False, "reason": "Candidate-level source file was not supplied."}
    df = read_csv(path)
    rank_col = find_column(df, "candidate_rank", "nist_rank", "rank")
    name_col = find_column(df, "candidate_name", "compound_name", "hit_name")
    class_col = find_column(df, "candidate_class", "literature_class", "nom_class")
    component_col = find_column(df, "component_id", "feature_id", "record_id")
    sample_col = find_column(df, "sample_id", "sample", "filename")
    if not rank_col or not name_col:
        return {"available": False, "reason": "Candidate rank/name columns were not recognized."}

    work = df.copy()
    work["__rank"] = pd.to_numeric(work[rank_col], errors="coerce")
    work = work[work["__rank"].notna()].copy()
    if component_col:
        keys = [c for c in (sample_col, component_col) if c]
    else:
        rt_col = find_column(work, "rt_min", "retention_time", "scan")
        keys = [c for c in (sample_col, rt_col) if c]
    if not keys:
        return {"available": False, "reason": "A component grouping key was not recognized."}

    components = 0
    with_second = 0
    name_different = 0
    class_comparable = 0
    class_different = 0
    for _, group in work.sort_values(keys + ["__rank"]).groupby(keys, dropna=False, sort=False):
        group = group.sort_values("__rank")
        if group.empty:
            continue
        components += 1
        first = group.iloc[0]
        if len(group) < 2:
            continue
        second = group.iloc[1]
        with_second += 1
        if str(first[name_col]).strip().casefold() != str(second[name_col]).strip().casefold():
            name_different += 1
        if class_col and text_present(first[class_col]) and text_present(second[class_col]):
            class_comparable += 1
            if str(first[class_col]).strip().casefold() != str(second[class_col]).strip().casefold():
                class_different += 1

    return {
        "available": True,
        "source": str(path),
        "candidate_records": int(len(work)),
        "components": components,
        "components_with_second_candidate": with_second,
        "second_candidate_name_diff_count": name_different,
        "second_candidate_name_diff_percent": 100.0 * name_different / with_second if with_second else None,
        "second_candidate_class_comparable": class_comparable,
        "second_candidate_class_diff_count": class_different,
        "second_candidate_class_diff_percent": 100.0 * class_different / class_comparable if class_comparable else None,
        "group_columns": keys,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--class-summary-csv", type=Path, required=True)
    parser.add_argument("--candidate-csv", type=Path)
    parser.add_argument("--outdir", type=Path, required=True)
    args = parser.parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)

    result = {
        "class_summary": summarize_class_table(args.class_summary_csv, args.outdir),
        "candidate_metrics": summarize_candidate_table(args.candidate_csv),
    }
    (args.outdir / "reproduced_statistics.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    summary = result["class_summary"]
    candidate = result["candidate_metrics"]
    lines = [
        "# Reproduced statistics",
        "",
        f"- Runs: {summary['runs']}",
        f"- Component records: {summary['selected_component_records']:,}",
        f"- Classified records: {summary['classified_records']:,}",
        f"- Excluded or unclassified records retained for audit: {summary['excluded_or_unclassified_records']:,}",
        "- Class composition is normalized only within the classified subset; excluded records are not an interpretive axis.",
        "- Source class proportions are reported to one decimal place and renormalized row-wise to 100%.",
        "",
        "## Candidate-level metrics",
    ]
    if candidate.get("available"):
        lines.extend([
            f"- Candidate records: {candidate['candidate_records']:,}",
            f"- Components: {candidate['components']:,}",
            f"- Components with a second candidate: {candidate['components_with_second_candidate']:,}",
            f"- Second-candidate name differs: {candidate['second_candidate_name_diff_percent']:.2f}%",
            f"- Second-candidate class differs among comparable pairs: {candidate['second_candidate_class_diff_percent']:.2f}%",
        ])
    else:
        lines.append(f"- Not reproduced: {candidate.get('reason', 'source unavailable')}")
    (args.outdir / "REPRODUCED_STATISTICS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
