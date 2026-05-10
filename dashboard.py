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

from functions import load_original_data,get_geo_features_around_station, plot_geo_features_around_station, plot_pollutant_levels_vs_safety_limits, feature_engineering, plot_deviation_from_permissible_limits

st.title("🌍 India AQI Daily Dashboard")

st.markdown("""
Welcome 👋

Explore how the air changes each day across cities in India 🌏.

This dashboard shows you 📊 average, minimum, and maximum pollution levels for seven major pollutants, compares them with safety limits ⚠️, 
and helps you discover nearby green 🌿 and industrial 🏭 areas using OpenStreetMap 🗺️.
""")

# ---------------- OPTIONAL DATE FILTER ----------------
data_folder = "E:\\AQI_Dashboard\\files"
# get all files in folder
files = [f for f in os.listdir(data_folder) if f.endswith(".csv")]
# extract date part from filename (remove .csv)
date_list = ["Select"] + sorted([f.replace(".csv", "") for f in files])
user_date = st.selectbox("Select Date", date_list)
# optional: load selected file
if user_date != "Select":
    file_path = os.path.join(data_folder, f"{user_date}.csv")
    df_selected = pd.read_csv(file_path)
    st.write(f"Loaded data for {user_date}")
    
    df = df_selected
    # Removing NAN rows
    df = df[df['pollutant_avg'].notna()]
    df = feature_engineering(df)

    state_list = ["Select State"] + df['state'].unique().tolist()
    user_state = st.selectbox('Select State',state_list)

    city_list = ["Select City"] + df[df['state'] == user_state]['city'].unique().tolist()
    user_city = st.selectbox('Select City',city_list)

    station_list =  ["Select Station"] + df[df['city']==user_city]['station'].unique().tolist()
    user_station = st.selectbox('Select Station', station_list)

    if user_station != 'Select Station':
        df_station = df[df['station']==user_station]
        
        col1, col2 = st.columns(2)

        with col1:
            st.metric(
                label="📍 Station Latitude",
                value=df_station['latitude'].iloc[0]
            )

        with col2:
            st.metric(
                label="📍 Station Longitude",
                value=df_station['longitude'].iloc[0]
            )

        fig = plot_pollutant_levels_vs_safety_limits(df_station)
        st.plotly_chart(fig, width='stretch')

        st.markdown("<br>", unsafe_allow_html=True)

        fig = plot_deviation_from_permissible_limits(df_station)
        st.plotly_chart(fig, width='stretch')


        radius = st.selectbox('Select radius', [2000, 3000, 5000])  #metres
        #----------- define station -------------------------

        lon = df_station['longitude'].iloc[0]
        lat = df_station['latitude'].iloc[0]
        #-------------------Parks----------------
        # green_tags = {
        #     "leisure": ["park", "garden", "nature_reserve", "recreation_ground"],
        #     "landuse": ["forest", "meadow", "grass"],
        #     "natural": ["wood", "grassland"]
        # }
        green_tags = {
            "leisure": [
                "park",
                "garden",
                "nature_reserve",
                "recreation_ground",
                "playground"
            ],

            "landuse": [
                "forest",
                "meadow",
                "grass",
                "recreation_ground",
                "orchard",
                "vineyard"
            ],

            "natural": [
                "wood",
                "grassland",
                "scrub",
                "heath",
                "wetland"
            ],

            "boundary": [
                "national_park",
                "protected_area"
            ],

            "amenity": [
                "grave_yard"
            ]
        }
        parks = get_geo_features_around_station(lat,lon,radius,green_tags)
        if parks is None:
            st.write(f'Found no Green Cover in {radius} metres of radius. Try different radius.')
        else:
            green_m = plot_geo_features_around_station(lat,lon,radius,green_tags,'green')
            st.subheader("Green Area around the station")
            st_folium(green_m, width=700, height=500, key="map_1")
            green_area_km2=parks['geometry'].area.sum() / 1000000 # covert m2 to km2
            
        #---------------Industries---------------------
        # industrial_tags = {
        #     "landuse": ["construction", "industrial"],
        #     "building": "construction",
        #     "highway": "construction",

        #     "power": ["plant", "generator"],

        #     "man_made": ["works", "factory"],

        #     "industrial": [
        #         "factory",
        #         "cement_works",
        #         "steelworks",
        #         "brickworks"
        #     ]
        # }

        industrial_tags = {
            "landuse": [
                "industrial",
                "construction",
                "brownfield",
                "depot",
                "railway",
                "quarry",
                "port",
                "commercial"
            ],

            "industrial": [
                "factory",
                "cement_works",
                "steelworks",
                "brickworks",
                "chemical_plant",
                "refinery",
                "warehouse",
                "plant",
                "mill"
            ],

            "man_made": [
                "works",
                "wastewater_plant",
                "pipeline",
                "chimney",
                "storage_tank",
                "silo"
            ],

            "power": [
                "plant",
                "generator",
                "substation"
            ],

            "building": [
                "industrial",
                "factory",
                "warehouse",
                "yes"
            ],

            "aeroway": [
                "hangar"
            ],

            "railway": [
                "yard",
                "depot"
            ]
        }

        industries = get_geo_features_around_station(lat,lon,radius,industrial_tags)
        if industries is None:
            st.write(f'Found no Industries in {radius} metres of radius. Try different radius.')
        else:
            industries_m = plot_geo_features_around_station(lat,lon,radius,industrial_tags,'purple')
            st.subheader("Industrial Area around the station")
            st_folium(industries_m, width=700, height=500, key="map_2")
            industrial_area_km2=industries['geometry'].area.sum() / 1000000

        #---------------Highways-----------------------
        highway_tags = {
                "highway": ["motorway", "trunk", "primary"]
            }
        highways = get_geo_features_around_station(lat, lon, radius, highway_tags, feature_geometry='LineString')
        if highways is None:
            st.write(f'Found no Highways in {radius} metres of radius. Try different radius.')
        else:
            st.subheader("Highways around the station")
            highways_m = plot_geo_features_around_station(lat,lon,radius,highway_tags,'yellow')
            st_folium(highways_m, width=700, height=500, key="map_3")
            highways['identifier'] = (
                highways.get('name')
                .fillna(highways.get('ref'))
            )

            highways_nearby = highways['identifier'].dropna().nunique()
            # highways_nearby = highways['name'].nunique()
            

        st.subheader("🌍 Nearby Environmental Overview")

        col1, col2, col3 = st.columns(3)
        with col1:
            if highways_nearby is not None:
                st.markdown(f"""
                <div style="
                    padding:20px;
                    border-radius:15px;
                    background-color:#f5f5f5;
                    color:black;
                    text-align:center;
                    box-shadow:0 2px 8px rgba(0,0,0,0.1);
                ">
                    <h4>🛣️ Nearby Highways</h4>
                    <h2>{highways_nearby}</h2>
                </div>
                """, unsafe_allow_html=True)

        with col2:
            if industrial_area_km2 is not None:
                st.markdown(f"""
                <div style="
                    padding:20px;
                    border-radius:15px;
                    background-color:#fff3e0;
                    color:black;
                    text-align:center;
                    box-shadow:0 2px 8px rgba(0,0,0,0.1);
                ">
                    <h4>🏭 Industrial Area</h4>
                    <h2>{industrial_area_km2:.2f} km²</h2>
                </div>
                """, unsafe_allow_html=True)

        with col3:
            if green_area_km2 is not None:
                st.markdown(f"""
                <div style="
                    padding:20px;
                    border-radius:15px;
                    background-color:#e8f5e9;
                    text-align:center;
                    color:black;
                    box-shadow:0 2px 8px rgba(0,0,0,0.1);
                ">
                    <h4>🌿 Green Area</h4>
                    <h2>{green_area_km2:.2f} km²</h2>
                </div>
                """, unsafe_allow_html=True)