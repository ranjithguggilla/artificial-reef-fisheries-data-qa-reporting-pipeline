from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import geopandas as gpd


@dataclass
class QAResult:
    issues: pd.DataFrame
    method_coverage: pd.DataFrame
    month_method_coverage: pd.DataFrame
    treatment_balance: pd.DataFrame


def _issue(category: str, severity: str, record_id: str, message: str) -> dict:
    return {
        "category": category,
        "severity": severity,
        "record_id": record_id,
        "message": message,
    }


def run_qa(
    reef_sites: pd.DataFrame,
    survey_events: pd.DataFrame,
    species_counts: pd.DataFrame,
    receiver_summary: pd.DataFrame,
    reef_polygons: gpd.GeoDataFrame | None = None,
    reef_points: gpd.GeoDataFrame | None = None,
) -> QAResult:
    issues: list[dict] = []

    # Missing coordinate checks.
    for _, row in reef_sites[reef_sites["latitude"].isna() | reef_sites["longitude"].isna()].iterrows():
        issues.append(_issue("missing_coordinates", "high", row["site_id"], "Site missing latitude/longitude"))

    # Duplicate survey detection.
    dupes = survey_events[survey_events.duplicated(subset=["site_id", "survey_date", "method"], keep=False)]
    for _, row in dupes.iterrows():
        issues.append(_issue("duplicate_survey", "medium", row["survey_id"], "Duplicate site/date/method survey event"))

    # Date consistency checks for receiver deployment/retrieval.
    deploy = pd.to_datetime(receiver_summary["deployment_date"], errors="coerce")
    retrieve = pd.to_datetime(receiver_summary["retrieval_date"], errors="coerce")
    bad_dates = receiver_summary[retrieve < deploy]
    for _, row in bad_dates.iterrows():
        issues.append(_issue("receiver_date_consistency", "high", row["receiver_id"], "Retrieval date earlier than deployment date"))

    # Site-method coverage checks.
    required_methods = {"camera", "vertical_line"}
    method_coverage = (
        survey_events.groupby(["site_id", "method"]).size().reset_index(name="event_count")
        .pivot(index="site_id", columns="method", values="event_count")
        .fillna(0)
        .astype(int)
        .reset_index()
    )
    for _, row in method_coverage.iterrows():
        present = {m for m in method_coverage.columns if m != "site_id" and row[m] > 0}
        missing = sorted(required_methods - present)
        if missing:
            issues.append(_issue("method_coverage_gap", "medium", row["site_id"], f"Missing required methods: {', '.join(missing)}"))

    # Treatment/control balance summary.
    visits = survey_events.groupby("site_id").size().reset_index(name="survey_visits")
    treatment_balance = reef_sites[["site_id", "treatment_group"]].merge(visits, on="site_id", how="left").fillna({"survey_visits": 0})
    balance_summary = treatment_balance.groupby("treatment_group")["survey_visits"].mean().reset_index(name="mean_visits")
    if balance_summary["mean_visits"].max() - balance_summary["mean_visits"].min() > 0.75:
        issues.append(_issue("treatment_control_imbalance", "medium", "all_sites", "Survey visit imbalance between treatment groups"))

    # Species count outlier flagging.
    counts = species_counts["count"].astype(float)
    z = (counts - counts.mean()) / counts.std(ddof=0)
    q1, q3 = counts.quantile(0.25), counts.quantile(0.75)
    iqr = q3 - q1
    low, high = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    outliers = species_counts[(np.abs(z) > 2.5) | (species_counts["count"] < low) | (species_counts["count"] > high)]
    for _, row in outliers.iterrows():
        issues.append(_issue("species_count_outlier", "medium", row["survey_id"], f"Suspicious species count: {row['count']}"))

    # Receiver uptime quality flagging.
    low_uptime = receiver_summary[receiver_summary["uptime_percent"] < 70]
    for _, row in low_uptime.iterrows():
        issues.append(_issue("receiver_uptime_low", "medium", row["receiver_id"], f"Low uptime: {row['uptime_percent']}%"))

    # Reef polygon/site distance validation.
    if reef_polygons is not None and reef_points is not None:
        points = reef_points[["site_id", "geometry"]].copy()
        polys = reef_polygons[["site_id", "geometry"]].copy()
        points = points[points.geometry.notna()].copy()
        joined = points.merge(polys, on="site_id", how="left", suffixes=("_pt", "_poly"))
        joined = gpd.GeoDataFrame(joined, geometry="geometry_pt", crs=reef_points.crs).to_crs("EPSG:32614")
        poly_metric = gpd.GeoSeries(joined["geometry_poly"], crs=reef_points.crs).to_crs("EPSG:32614")
        distances = joined.geometry.distance(poly_metric, align=False)
        for site_id, dist_m in zip(joined["site_id"], distances):
            if pd.isna(dist_m):
                issues.append(_issue("polygon_alignment", "medium", str(site_id), "Site missing matching reef polygon"))
            elif float(dist_m) > 1500:
                issues.append(_issue("polygon_alignment", "medium", str(site_id), f"Site point far from reef polygon ({dist_m:.0f} m)"))

    # Sampling coverage by month and method.
    survey_events = survey_events.copy()
    survey_events["survey_date"] = pd.to_datetime(survey_events["survey_date"], errors="coerce")
    survey_events["month"] = survey_events["survey_date"].dt.month
    month_method_coverage = survey_events.groupby(["month", "method"]).size().reset_index(name="event_count")
    if (month_method_coverage.groupby("month")["event_count"].sum().min() < 2):
        issues.append(_issue("month_underrepresentation", "low", "monthly_coverage", "At least one month has sparse sampling effort"))

    issue_df = pd.DataFrame(issues).sort_values(["severity", "category"], ascending=[True, True]).reset_index(drop=True)
    if issue_df.empty:
        issue_df = pd.DataFrame(columns=["category", "severity", "record_id", "message"])
    return QAResult(
        issues=issue_df,
        method_coverage=method_coverage,
        month_method_coverage=month_method_coverage,
        treatment_balance=treatment_balance,
    )
