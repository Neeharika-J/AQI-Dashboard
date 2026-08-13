import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
import folium
import osmnx as ox
from shapely.geometry import Point
import geopandas as gpd
import plotly.graph_objects as go
from streamlit_folium import st_folium
import streamlit as st
import os

from feature_groups import feature_groups
from functions import (
    plot_pollutant_levels_vs_safety_limits,
    feature_engineering,
    plot_deviation_from_permissible_limits,
    get_cached_station_map
)


# Page configuration
st.set_page_config(
    page_title="India AQI Dashboard",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded",
)


# Custom CSS
st.markdown("""
<style>
    /* Overall app background */
    .stApp {
        background: linear-gradient(180deg, #f4f7fb 0%, #eef2f7 100%);
    }

    /* Main title */
    .hero {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
        padding: 2rem 2.2rem;
        border-radius: 18px;
        color: white;
        margin-bottom: 1.6rem;
        box-shadow: 0 8px 24px rgba(30, 60, 114, 0.25);
    }
    .hero h1 {
        margin: 0;
        font-size: 2.1rem;
        font-weight: 700;
    }
    .hero p {
        margin-top: 0.6rem;
        font-size: 1.02rem;
        opacity: 0.92;
        line-height: 1.5;
    }

    /* Section headers */
    .section-header {
        font-size: 1.3rem;
        font-weight: 700;
        color: #1e3c72;
        margin: 1.4rem 0 0.8rem 0;
        padding-bottom: 0.4rem;
        border-bottom: 3px solid #2a5298;
        display: inline-block;
    }

    /* Custom metric cards */
    .metric-card {
        background: white;
        border-radius: 14px;
        padding: 1.1rem 1.3rem;
        box-shadow: 0 3px 12px rgba(0,0,0,0.06);
        border-left: 5px solid #2a5298;
        text-align: center;
    }
    .metric-card .label {
        font-size: 0.85rem;
        color: #6b7280;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.03em;
    }
    .metric-card .value {
        font-size: 1.5rem;
        font-weight: 700;
        color: #1e3c72;
        margin-top: 0.2rem;
    }

    /* Feature summary cards */
    .feature-card {
        background: white;
        border-radius: 14px;
        padding: 1.2rem;
        box-shadow: 0 3px 12px rgba(0,0,0,0.06);
        text-align: center;
        transition: transform 0.15s ease;
    }
    .feature-card:hover {
        transform: translateY(-3px);
    }
    .feature-card .icon {
        font-size: 1.8rem;
    }
    .feature-card .title {
        font-weight: 700;
        color: #1e3c72;
        margin: 0.3rem 0;
    }
    .feature-card .big {
        font-size: 1.4rem;
        font-weight: 700;
        color: #2a5298;
    }
    .feature-card .small {
        color: #6b7280;
        font-size: 0.85rem;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: #101c33;
    }
    section[data-testid="stSidebar"] * {
        color: #e5eaf2 !important;
    }

    /* Dataframe corners */
    div[data-testid="stDataFrame"] {
        border-radius: 12px;
        overflow: hidden;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 6px;
    }
    .stTabs [data-baseweb="tab"] {
        background: white;
        border-radius: 10px 10px 0 0;
        padding: 0.6rem 1.2rem;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)


def metric_card(label, value):
    st.markdown(f"""
        <div class="metric-card">
            <div class="label">{label}</div>
            <div class="value">{value}</div>
        </div>
    """, unsafe_allow_html=True)


def feature_card(icon, title, big_value, small_value):
    st.markdown(f"""
        <div class="feature-card">
            <div class="icon">{icon}</div>
            <div class="title">{title}</div>
            <div class="big">{big_value}</div>
            <div class="small">{small_value}</div>
        </div>
    """, unsafe_allow_html=True)


# Hero Section
st.markdown("""
<div class="hero">
    <h1>🌍 India AQI Daily Dashboard</h1>
    <p>
        Explore how the air changes each day across cities in India 🌏 — average, minimum, and maximum
        levels for seven major pollutants, compared against safety limits ⚠️, plus nearby green 🌿 and
        industrial 🏭 areas from OpenStreetMap 🗺️.
    </p>
</div>
""", unsafe_allow_html=True)


# Sidebar Filters
base_dir = os.path.dirname(os.path.abspath(__file__))
data_folder = os.path.join(base_dir, 'files')
files = [f for f in os.listdir(data_folder) if f.endswith(".csv")]
date_list = ["Select"] + sorted([f.replace(".csv", "") for f in files])

with st.sidebar:
    st.markdown("## 🔍 Filters")
    user_date = st.selectbox("📅 Date", date_list)

    user_state = "Select State"
    user_city = "Select City"
    user_station = "Select Station"

    if user_date != "Select":
        file_path = os.path.join(data_folder, f"{user_date}.csv")
        df_selected = pd.read_csv(file_path)
        df = df_selected[df_selected['pollutant_avg'].notna()]
        df = feature_engineering(df)

        state_list = ["Select State"] + df['state'].unique().tolist()
        user_state = st.selectbox('🏙️ State', state_list)

        city_list = ["Select City"] + df[df['state'] == user_state]['city'].unique().tolist()
        user_city = st.selectbox('🏘️ City', city_list)

        station_list = ["Select Station"] + df[df['city'] == user_city]['station'].unique().tolist()
        user_station = st.selectbox('📡 Station', station_list)

    st.markdown("---")
    st.caption("Data source: [https://www.data.gov.in/](https://www.data.gov.in/resource/real-time-air-quality-index-various-locations).")



# Main Content
if user_date == "Select":
    st.info("👈 Pick a date from the sidebar to get started.")
elif user_state == "Select State":
    st.info("👈 Now pick a state.")
elif user_city == "Select City":
    st.info("👈 Now pick a city.")
elif user_station == "Select Station":
    st.info("👈 Now pick a station.")
else:
    df_station = df[df['station'] == user_station]
    st.markdown('<div class="section-header">📊 Pollutant Summary</div>', unsafe_allow_html=True)
    selected_columns = df_station[
        ["pollutant_id", "pollutant_avg", "pollutant_range", "safety_limit", "safety_deviation"]
    ]

    # displaying the dataframe
    st.dataframe(selected_columns, use_container_width=True, hide_index=True)

    st.markdown('<div class="section-header">📍 Station Location</div>', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        metric_card("Latitude", df_station['latitude'].iloc[0])
    with col2:
        metric_card("Longitude", df_station['longitude'].iloc[0])

    st.markdown("<br>", unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs([
        "📈 Pollutant Levels",
        "📉 Deviation Analysis",
        "🗺️ Nearby Features"
    ])

    st.markdown("""
    <style>
    button[data-baseweb="tab"] {
        color: black !important;
    }
    </style>
    """, unsafe_allow_html=True)

    with tab1:
        fig = plot_pollutant_levels_vs_safety_limits(df_station)
        st.plotly_chart(fig, width='stretch')
        st.markdown( '''
        <p style="color: #808080; font-size: 14px;">
        This chart compares pollutant concentrations to WHO's permissible limits for living conditions.
        </p>
        ''', unsafe_allow_html=True)

    with tab2:
        fig = plot_deviation_from_permissible_limits(df_station)
        st.plotly_chart(fig, width='stretch')
        st.markdown("""
            <p style="color: #808080; font-size: 14px;">
            This chart shows the deviation of each pollutant from the permissible limit.
            A positive value means the pollutant level is above the permissible limit,
            while a negative value means it's below it.
            </p>

            <p style="color: #808080; font-size: 14px;">
            <b>Deviation = (Average − Safety Limit) / Safety Limit</b>
            </p>
            """, unsafe_allow_html=True)

    with tab3:
        lon = df_station['longitude'].iloc[0]
        lat = df_station['latitude'].iloc[0]

        st.markdown("""
            <style>
            [data-testid="stSpinner"] p {
                color: black !important;
            }

            [data-testid="stSpinner"] svg {
                stroke: black !important;
            }
            </style>
            """, unsafe_allow_html=True)


        # Map
        map_key = (
            f"map_{user_date}_{user_state}_"
            f"{user_city}_{user_station}"
        )

        with st.spinner(
            "🔄 Loading nearby features. This may take some time...."
        ):

            m, area_summary = get_cached_station_map(
                lat=lat,
                lon=lon,
                radius=2000,
                feature_groups=feature_groups
            )

        st.success(
            "Map loaded!"
        )

        st_folium(
            m,
            width=1200,
            height=500,
            key=map_key,
            returned_objects=[]
        )

        st.markdown('<div class="section-header">🧭 Station Feature Summary</div>', unsafe_allow_html=True)

        features = []
        parks = area_summary.get("parks")
        highways = area_summary.get("highways")
        industries = area_summary.get("industries")

        if parks:
            features.append(("🌳", "Parks", parks))
        if highways:
            features.append(("🛣️", "Highways", highways))
        if industries:
            features.append(("🏭", "Industries", industries))

        if not features:
            st.info("No feature information available.")
        else:
            cols = st.columns(len(features))
            for col, (icon, name, data) in zip(cols, features):
                with col:
                    if "area_ha" in data:
                        feature_card(icon, name, f"{data['area_ha']:,.2f} ha", f"{data['area_m2']:,.2f} m²")
                    elif "length_km" in data:
                        feature_card(icon, name, f"{data['length_km']:,.2f} km", f"{data['length_m']:,.2f} m")


