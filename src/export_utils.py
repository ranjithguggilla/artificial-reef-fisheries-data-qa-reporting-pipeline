from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

import folium
import pandas as pd

from .analytics import (
    cpue_style_summary,
    effort_by_month_and_method,
    receiver_uptime_summary,
    richness_by_reef_type,
    species_summary_by_site,
)
from .coverage_gap import build_coverage_gap_notes, completeness_score
from .data_loader import OUTPUT_DIR, PROCESSED_DIR, build_sites_gdf, load_raw_tables, load_reef_polygons
from .qa_checks import run_qa


def _write_uncertainty_notes(path: Path, notes: list[str]) -> None:
    body = "# Uncertainty Notes\n\n" + "\n".join([f"- {n}" for n in notes]) + "\n"
    path.write_text(body, encoding="utf-8")


def _write_qa_report_md(path: Path, qa_issues: pd.DataFrame) -> None:
    lines = ["# QA Report", ""]
    lines.append(f"- Total QA issues: {len(qa_issues)}")
    lines.append("")
    if qa_issues.empty:
        lines.append("No QA issues detected.")
    else:
        for category, chunk in qa_issues.groupby("category"):
            lines.append(f"## {category}")
            for _, row in chunk.iterrows():
                lines.append(f"- [{row['severity']}] {row['record_id']}: {row['message']}")
            lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_map_html(path: Path, sites_gdf, polygons_gdf, completeness_df: pd.DataFrame) -> None:
    merged = sites_gdf.merge(completeness_df[["site_id", "completeness_score", "coverage_band"]], on="site_id", how="left")
    fmap = folium.Map(location=[27.95, -96.95], zoom_start=7, tiles="CartoDB positron")
    folium.GeoJson(polygons_gdf.to_json(), name="Reef Polygons").add_to(fmap)
    for _, row in merged.iterrows():
        band = str(row["coverage_band"]) if pd.notna(row["coverage_band"]) else "Low"
        color = {"High": "green", "Medium": "orange", "Low": "red"}.get(band, "gray")
        if pd.notna(row["latitude"]) and pd.notna(row["longitude"]):
            folium.CircleMarker(
                location=[row["latitude"], row["longitude"]],
                radius=6,
                color=color,
                fill=True,
                fill_opacity=0.85,
                popup=f"{row['site_id']} | score {row['completeness_score']:.1f}",
            ).add_to(fmap)
    fmap.save(path)


def generate_outputs() -> dict[str, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    tables = load_raw_tables()
    polygons = load_reef_polygons()
    sites_gdf = build_sites_gdf(tables["reef_sites"])
    qa = run_qa(
        tables["reef_sites"],
        tables["survey_events"],
        tables["species_counts"],
        tables["receiver_summary"],
        reef_polygons=polygons,
        reef_points=sites_gdf,
    )
    comp = completeness_score(tables["reef_sites"], qa.method_coverage, tables["receiver_summary"])
    gap_notes = build_coverage_gap_notes(
        tables["reef_sites"], qa.method_coverage, tables["receiver_summary"], qa.month_method_coverage, qa.treatment_balance
    )

    species = species_summary_by_site(tables["species_counts"], tables["survey_events"])
    cpue = cpue_style_summary(tables["species_counts"], tables["survey_events"])
    richness = richness_by_reef_type(tables["species_counts"], tables["survey_events"], tables["reef_sites"])
    effort = effort_by_month_and_method(tables["survey_events"])
    uptime = receiver_uptime_summary(tables["receiver_summary"])

    qa_csv = OUTPUT_DIR / "qa_report.csv"
    qa_md = OUTPUT_DIR / "qa_report.md"
    coverage_map = OUTPUT_DIR / "reef_site_coverage_map.html"
    species_csv = OUTPUT_DIR / "species_summary_by_site.csv"
    method_cov_csv = OUTPUT_DIR / "method_coverage_matrix.csv"
    uptime_csv = OUTPUT_DIR / "receiver_uptime_summary.csv"
    uncertainty_md = OUTPUT_DIR / "uncertainty_notes.md"
    zip_path = OUTPUT_DIR / "cleaned_export_package.zip"

    qa.issues.to_csv(qa_csv, index=False)
    _write_qa_report_md(qa_md, qa.issues)
    _write_map_html(coverage_map, sites_gdf, polygons, comp)
    species.to_csv(species_csv, index=False)
    qa.method_coverage.to_csv(method_cov_csv, index=False)
    uptime.to_csv(uptime_csv, index=False)
    _write_uncertainty_notes(uncertainty_md, gap_notes)

    # Persist extra processed analytics.
    cpue.to_csv(PROCESSED_DIR / "cpue_summary.csv", index=False)
    richness.to_csv(PROCESSED_DIR / "species_richness_by_reef_type.csv", index=False)
    effort.to_csv(PROCESSED_DIR / "effort_by_month_method.csv", index=False)
    comp.to_csv(PROCESSED_DIR / "coverage_completeness.csv", index=False)

    with ZipFile(zip_path, "w") as zf:
        for p in [qa_csv, qa_md, species_csv, method_cov_csv, uptime_csv, uncertainty_md]:
            zf.write(p, arcname=p.name)

    return {
        "qa_report_md": qa_md,
        "qa_report_csv": qa_csv,
        "coverage_map_html": coverage_map,
        "species_summary_by_site_csv": species_csv,
        "method_coverage_matrix_csv": method_cov_csv,
        "receiver_uptime_summary_csv": uptime_csv,
        "uncertainty_notes_md": uncertainty_md,
        "cleaned_export_package_zip": zip_path,
    }


if __name__ == "__main__":
    outputs = generate_outputs()
    for name, path in outputs.items():
        print(f"{name}: {path}")
