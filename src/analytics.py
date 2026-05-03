from __future__ import annotations

import pandas as pd


def species_summary_by_site(species_counts: pd.DataFrame, survey_events: pd.DataFrame) -> pd.DataFrame:
    merged = species_counts.merge(survey_events[["survey_id", "site_id", "method", "duration_min"]], on="survey_id", how="left")
    out = (
        merged.groupby(["site_id", "species"], as_index=False)
        .agg(total_count=("count", "sum"), mean_length_cm=("mean_length_cm", "mean"), surveys=("survey_id", "nunique"))
    )
    return out.sort_values(["site_id", "total_count"], ascending=[True, False])


def cpue_style_summary(species_counts: pd.DataFrame, survey_events: pd.DataFrame) -> pd.DataFrame:
    merged = species_counts.merge(survey_events[["survey_id", "site_id", "method", "duration_min"]], on="survey_id", how="left")
    merged["hours"] = merged["duration_min"] / 60.0
    merged["cpue"] = merged["count"] / merged["hours"].clip(lower=0.25)
    return (
        merged.groupby(["site_id", "method"], as_index=False)
        .agg(mean_cpue=("cpue", "mean"), total_count=("count", "sum"), effort_hours=("hours", "sum"))
        .sort_values(["mean_cpue"], ascending=False)
    )


def richness_by_reef_type(
    species_counts: pd.DataFrame, survey_events: pd.DataFrame, reef_sites: pd.DataFrame
) -> pd.DataFrame:
    merged = species_counts.merge(survey_events[["survey_id", "site_id"]], on="survey_id", how="left")
    merged = merged.merge(reef_sites[["site_id", "reef_type"]], on="site_id", how="left")
    return merged.groupby("reef_type", as_index=False)["species"].nunique().rename(columns={"species": "species_richness"})


def effort_by_month_and_method(survey_events: pd.DataFrame) -> pd.DataFrame:
    df = survey_events.copy()
    df["survey_date"] = pd.to_datetime(df["survey_date"], errors="coerce")
    df["month"] = df["survey_date"].dt.to_period("M").astype(str)
    return (
        df.groupby(["month", "method"], as_index=False)
        .agg(events=("survey_id", "count"), effort_min=("duration_min", "sum"))
        .sort_values(["month", "method"])
    )


def receiver_uptime_summary(receiver_summary: pd.DataFrame) -> pd.DataFrame:
    return receiver_summary.groupby("site_id", as_index=False).agg(
        mean_uptime_percent=("uptime_percent", "mean"),
        total_detections=("detection_count", "sum"),
    )
