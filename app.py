from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit_folium import st_folium
import folium

from src.analytics import cpue_style_summary, effort_by_month_and_method, richness_by_reef_type, receiver_uptime_summary, species_summary_by_site
from src.coverage_gap import build_coverage_gap_notes, completeness_score
from src.data_loader import build_sites_gdf, load_raw_tables, load_reef_polygons
from src.export_utils import generate_outputs
from src.qa_checks import run_qa


st.set_page_config(page_title="Artificial Reef Fisheries Data QA & Reporting Pipeline", layout="wide")
st.title("Artificial Reef Fisheries Data QA & Reporting Pipeline")
st.caption("Public-data-safe synthetic workflow for reef survey operations, QA, and export packaging.")


@st.cache_data(show_spinner=False)
def build_state():
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
    gaps = build_coverage_gap_notes(tables["reef_sites"], qa.method_coverage, tables["receiver_summary"], qa.month_method_coverage, qa.treatment_balance)
    return tables, polygons, sites_gdf, qa, comp, gaps


tables, polygons, sites_gdf, qa, comp, gaps = build_state()
pages = ["Project Overview", "Map", "QA Summary", "Analytics", "Export"]
page = st.sidebar.radio("Page", pages)

if page == "Project Overview":
    st.subheader("Program Snapshot")
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Reef Sites", int(tables["reef_sites"]["site_id"].nunique()))
    c2.metric("Survey Events", int(tables["survey_events"]["survey_id"].nunique()))
    c3.metric("Methods", int(tables["survey_events"]["method"].nunique()))
    c4.metric("Species", int(tables["species_counts"]["species"].nunique()))
    c5.metric("QA Issues", int(len(qa.issues)))
    dates = pd.to_datetime(tables["survey_events"]["survey_date"], errors="coerce")
    c6.metric("Date Range", f"{dates.min().date()} to {dates.max().date()}")
    st.markdown("### Coverage Gap Detector")
    for note in gaps:
        st.write(f"- {note}")

elif page == "Map":
    st.subheader("Reef Coverage Map")
    reef_type_filter = st.multiselect("Reef Type", sorted(tables["reef_sites"]["reef_type"].dropna().unique()), default=sorted(tables["reef_sites"]["reef_type"].dropna().unique()))
    treat_filter = st.multiselect("Treatment Group", sorted(tables["reef_sites"]["treatment_group"].dropna().unique()), default=sorted(tables["reef_sites"]["treatment_group"].dropna().unique()))
    method_filter = st.multiselect("Survey Method", sorted(tables["survey_events"]["method"].dropna().unique()), default=sorted(tables["survey_events"]["method"].dropna().unique()))

    method_sites = tables["survey_events"][tables["survey_events"]["method"].isin(method_filter)]["site_id"].unique()
    filtered = comp.merge(tables["reef_sites"], on=["site_id", "reef_type", "treatment_group"], how="left")
    filtered = filtered[
        (filtered["reef_type"].isin(reef_type_filter))
        & (filtered["treatment_group"].isin(treat_filter))
        & (filtered["site_id"].isin(method_sites))
    ]

    fmap = folium.Map(location=[27.95, -96.95], zoom_start=7, tiles="CartoDB positron")
    folium.GeoJson(polygons.to_json(), name="Reef Polygons").add_to(fmap)
    color_map = {"High": "#2a9d8f", "Medium": "#f4a261", "Low": "#d62828"}
    for _, row in filtered.iterrows():
        if pd.notna(row["latitude"]) and pd.notna(row["longitude"]):
            folium.CircleMarker(
                location=[row["latitude"], row["longitude"]],
                radius=7,
                color=color_map.get(str(row["coverage_band"]), "#6c757d"),
                fill=True,
                fill_opacity=0.85,
                popup=f"{row['site_id']} | {row['coverage_band']} | score={row['completeness_score']:.1f}",
            ).add_to(fmap)
    st_folium(fmap, use_container_width=True, height=540)

elif page == "QA Summary":
    st.subheader("QA Findings")
    if qa.issues.empty:
        st.success("No QA issues detected.")
    else:
        st.dataframe(qa.issues, use_container_width=True, hide_index=True)
    st.markdown("### Method Coverage Matrix")
    st.dataframe(qa.method_coverage, use_container_width=True, hide_index=True)
    st.markdown("### Weather / Sea-state limitations")
    bad_weather = tables["weather_window"][tables["weather_window"]["weather_ok"].str.lower() == "no"]
    st.dataframe(bad_weather, use_container_width=True, hide_index=True)

elif page == "Analytics":
    st.subheader("Analytics")
    species_summary = species_summary_by_site(tables["species_counts"], tables["survey_events"])
    cpue = cpue_style_summary(tables["species_counts"], tables["survey_events"])
    richness = richness_by_reef_type(tables["species_counts"], tables["survey_events"], tables["reef_sites"])
    effort = effort_by_month_and_method(tables["survey_events"])
    uptime = receiver_uptime_summary(tables["receiver_summary"])

    st.markdown("### CPUE-style summary")
    st.dataframe(cpue.round(2), use_container_width=True, hide_index=True)
    st.markdown("### Species richness by reef type")
    st.plotly_chart(px.bar(richness, x="reef_type", y="species_richness"), use_container_width=True)
    st.markdown("### Survey effort by month and method")
    st.plotly_chart(px.bar(effort, x="month", y="events", color="method", barmode="group"), use_container_width=True)
    st.markdown("### Receiver detection trends")
    st.plotly_chart(px.line(uptime, x="site_id", y="total_detections", markers=True), use_container_width=True)
    st.markdown("### Species summary by site")
    st.dataframe(species_summary, use_container_width=True, hide_index=True)

else:
    st.subheader("Export Package")
    if st.button("Generate all outputs"):
        paths = generate_outputs()
        st.success("Generated output artifacts.")
        for name, path in paths.items():
            st.write(f"- {name}: `{path}`")
    st.info("Use the button to create QA reports, coverage map, summary tables, and cleaned export zip in `outputs/`.")
