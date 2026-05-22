# exporters/exporter.py — CSV, JSON, and Polars export
"""Export match results for reporting and downstream analytics."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import List

from dff_lite.core.Models import MatchResult


def _rows(matches: List[MatchResult]) -> List[dict]:
    rows = []
    for m in matches:
        row = m.model_dump()
        row["scores_json"] = json.dumps(m.scores)
        rows.append(row)
    return rows


def export_to_csv(matches: List[MatchResult], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "path_a", "path_b", "file_a_size", "file_b_size",
            "confidence_score", "category", "scores",
        ])
        for m in matches:
            writer.writerow([
                m.path_a, m.path_b, m.file_a_size, m.file_b_size,
                m.confidence_score, m.category, json.dumps(m.scores),
            ])


def export_to_json(matches: List[MatchResult], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump([m.model_dump() for m in matches], f, indent=2, ensure_ascii=False)


def export_to_polars_csv(matches: List[MatchResult], output_path: Path) -> None:
    """Fast columnar export via Polars when available."""
    try:
        import polars as pl
    except ImportError:
        export_to_csv(matches, output_path)
        return

    df = pl.DataFrame(_rows(matches))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.write_csv(output_path)

