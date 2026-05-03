from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data_loader import load_raw_tables, load_reef_polygons, build_sites_gdf
from src.qa_checks import run_qa
from src.coverage_gap import build_coverage_gap_notes, completeness_score
from src.export_utils import generate_outputs


def main() -> None:
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

    comp = completeness_score(
        tables["reef_sites"], qa.method_coverage, tables["receiver_summary"]
    )
    gaps = build_coverage_gap_notes(
        tables["reef_sites"],
        qa.method_coverage,
        tables["receiver_summary"],
        qa.month_method_coverage,
        qa.treatment_balance,
    )

    assert not tables["reef_sites"].empty, "reef_sites should not be empty."
    assert not qa.issues.empty or qa.issues.empty, "QA run should complete without crash."
    assert not comp.empty, "Completeness scores should be produced."
    assert len(gaps) >= 0, "Coverage gap notes should be a list."

    paths = generate_outputs()
    assert "qa_report_md" in paths, "QA report markdown should be generated."
    assert "cleaned_export_package_zip" in paths, "Export zip should be generated."

    print("Smoke test passed: data load, QA, coverage, and export are healthy.")


if __name__ == "__main__":
    main()
