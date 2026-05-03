from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
OUTPUT_DIR = ROOT / "outputs"


def load_raw_tables() -> dict[str, pd.DataFrame]:
    return {
        "reef_sites": pd.read_csv(RAW_DIR / "reef_sites.csv"),
        "survey_events": pd.read_csv(RAW_DIR / "survey_events.csv"),
        "species_counts": pd.read_csv(RAW_DIR / "species_counts.csv"),
        "receiver_summary": pd.read_csv(RAW_DIR / "acoustic_receiver_summary.csv"),
        "camera_summary": pd.read_csv(RAW_DIR / "camera_survey_summary.csv"),
        "weather_window": pd.read_csv(RAW_DIR / "weather_window.csv"),
        "metadata_dictionary": pd.read_csv(RAW_DIR / "metadata_dictionary.csv"),
    }


def load_reef_polygons() -> gpd.GeoDataFrame:
    gdf = gpd.read_file(RAW_DIR / "reef_polygons.geojson")
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    return gdf.to_crs("EPSG:4326")


def build_sites_gdf(reef_sites: pd.DataFrame) -> gpd.GeoDataFrame:
    df = reef_sites.copy()
    valid = df["latitude"].notna() & df["longitude"].notna()
    df["geometry"] = None
    geometry = gpd.points_from_xy(df.loc[valid, "longitude"], df.loc[valid, "latitude"])
    gdf = gpd.GeoDataFrame(df, geometry="geometry", crs="EPSG:4326")
    gdf.loc[valid, "geometry"] = list(geometry)
    return gdf
