from __future__ import annotations

import pandas as pd


def build_coverage_gap_notes(
    reef_sites: pd.DataFrame,
    method_coverage: pd.DataFrame,
    receiver_summary: pd.DataFrame,
    month_method_coverage: pd.DataFrame,
    treatment_balance: pd.DataFrame,
) -> list[str]:
    notes: list[str] = []

    merged = reef_sites[["site_id"]].merge(method_coverage, on="site_id", how="left").fillna(0)
    for _, row in merged.iterrows():
        cam = int(row["camera"]) if "camera" in merged.columns else 0
        vline = int(row["vertical_line"]) if "vertical_line" in merged.columns else 0
        if cam > 0 and vline == 0:
            notes.append(f"Site {row['site_id']} has camera coverage but no vertical line survey.")

    low_uptime = receiver_summary[receiver_summary["uptime_percent"] < 70]
    for _, row in low_uptime.iterrows():
        notes.append(f"Site {row['site_id']} has low acoustic receiver uptime ({row['uptime_percent']}%).")

    group_means = treatment_balance.groupby("treatment_group")["survey_visits"].mean()
    if "control" in group_means.index and "reef" in group_means.index:
        if group_means["control"] < group_means["reef"]:
            notes.append("Control sites have fewer repeat visits than reef sites.")

    month_totals = month_method_coverage.groupby("month")["event_count"].sum()
    if not month_totals.empty:
        sparse_month = int(month_totals.idxmin())
        notes.append(f"Month {sparse_month:02d} surveys are underrepresented.")

    if len(notes) < 3:
        notes.append("Coverage appears broadly complete but targeted repeat sampling is still recommended.")
    return notes


def completeness_score(
    sites: pd.DataFrame,
    method_coverage: pd.DataFrame,
    receiver_summary: pd.DataFrame,
) -> pd.DataFrame:
    df = sites[["site_id", "reef_type", "treatment_group"]].copy()
    df = df.merge(method_coverage, on="site_id", how="left").fillna(0)
    rec = receiver_summary[["site_id", "uptime_percent"]].groupby("site_id", as_index=False).mean()
    df = df.merge(rec, on="site_id", how="left").fillna({"uptime_percent": 0})

    df["method_score"] = ((df.get("camera", 0) > 0).astype(int) + (df.get("vertical_line", 0) > 0).astype(int) + (df.get("diver", 0) > 0).astype(int)) / 3
    df["uptime_score"] = (df["uptime_percent"] / 100).clip(0, 1)
    df["completeness_score"] = ((df["method_score"] * 0.6) + (df["uptime_score"] * 0.4)) * 100
    df["coverage_band"] = pd.cut(
        df["completeness_score"],
        bins=[-1, 49.9, 74.9, 101],
        labels=["Low", "Medium", "High"],
    )
    return df
