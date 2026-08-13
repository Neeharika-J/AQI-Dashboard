from networkx import radius
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
import streamlit as st

# ----------------------------------------

pollutant_unit = 'ug/m3'

safety_limit = {
    'PM2.5' : 60,
    'PM10' : 100,
    'OZONE' : 100,
    'NO2' : 80,
    'SO2' : 80,
    'CO' : 2,
    'NH3' : 200 
}

pollutant_palette = {
    "OZONE": "#A8E6CF",   # soft mint green
    "PM2.5": "#AFCBFF",   # powder blue
    "NO2": "#CDB4DB",     # lavender
    "PM10": "#FFD6A5",    # peach pastel
    "CO": "#DADADA",      # cool light gray
    "NH3": "#CDE7BE",     # pale sage green
    "SO2": "#FFF1B6"      # butter yellow
}

# ----------------------------------------

@st.cache_data
def load_original_data(path):
    df = pd.read_csv(path)
    return df

def plot_pollutant_levels_vs_safety_limits(df_station):
    bar_colors = df_station['pollutant_id'].map(pollutant_palette)
    fig = go.Figure()
    # Add the Bar for Average with Error Bars for Min/Max
    fig.add_trace(go.Bar(
        name='Average & Range',
        x=df_station['pollutant_id'],
        y=df_station['pollutant_avg'],
        error_y=dict(
            type='data',
            symmetric=False,
            array=[max - avg for max, avg in zip(df_station['pollutant_max'], df_station['pollutant_avg'])],
            # Distance to Max
            arrayminus=[avg - min for avg, min in zip(df_station['pollutant_avg'], df_station['pollutant_min'])]
            # Distance to Min
        ),
        marker_color=bar_colors
    ))

    # Add a Scatter trace for the Safety Limit
    fig.add_trace(go.Scatter(
        name='Safety Limit',
        x=df_station['pollutant_id'],
        y=df_station['safety_limit'],
        mode='markers',
        marker=dict(color='red', symbol='line-ew-open', size=20, line_width=3)
    ))

    fig.update_layout(
        title=f'Pollutant Levels vs Safety Limits. All units ({pollutant_unit})',
        yaxis_title='Concentration',
        barmode='group'
    )
    return fig

def feature_engineering(df):
    # range of pollution throughout the day
    df['pollutant_range'] = round((df['pollutant_max'] - df['pollutant_min']), 2)

    # permissible limit for each pollutant
    df['safety_limit'] = df['pollutant_id'].map(safety_limit)

    # deviation from safety limit, +0.30 = 30% above safety limit
    df['safety_deviation'] = round(
        ((df['pollutant_avg'] - df['pollutant_id'].map(safety_limit)) / df['pollutant_id'].map(safety_limit)), 2)
    return df

def plot_deviation_from_permissible_limits(df_station):
    # Sample data
    data = pd.DataFrame({
        "pollutant": df_station['pollutant_id'],
        "value": df_station['safety_deviation']
    })
    # Baseline (mean)
    # baseline = data["value"].mean()
    baseline = 0
    # Deviation
    data["deviation"] = data["value"] - baseline
    # Colors for above/below
    colors = ["red" if x > 0 else "green" for x in data["deviation"]]
    # Plot
    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=data["pollutant"],
        y=data["deviation"],
        marker_color=colors
    ))
    # Add baseline line (0 after deviation)
    fig.add_hline(y=0, line_dash="dash", line_color="black")
    fig.update_layout(
        title="Deviation from Mean",
        yaxis_title="Deviation",
        xaxis_title="Pollutant"
    )
    return fig

def get_utm_epsg(lat, lon):
    zone = int((lon + 180) // 6) + 1
    return 32600 + zone if lat >= 0 else 32700 + zone

def get_geo_features_around_station(geo_features, lat, lon, radius, tags, feature_geometry='Polygon'):
    epsg = get_utm_epsg(lat, lon)
    # Station buffer
    station_point = gpd.GeoSeries([Point(lon, lat)], crs="EPSG:4326").to_crs(epsg=epsg)
    buffer_geom = station_point.buffer(radius).iloc[0]
    buffer_gdf = gpd.GeoDataFrame(geometry=[buffer_geom], crs=f"EPSG:{epsg}")
    try:
        # Fetch OSM features
        geo_features = geo_features.to_crs(epsg=epsg)
        if geo_features.empty:
            return gpd.GeoDataFrame(columns=["geometry"], crs=f"EPSG:{epsg}")
        # Convert geometry types (allow Multi* variants too)
        geo_features = geo_features[
            geo_features.geom_type.str.contains(feature_geometry)
        ]
        if geo_features.empty:
            return gpd.GeoDataFrame(columns=["geometry"], crs=f"EPSG:{epsg}")
        # Project
        geo_features_proj = geo_features.to_crs(epsg=epsg)
        # Clip (MORE STABLE THAN overlay)
        geo_features_clipped = gpd.clip(geo_features_proj, buffer_gdf)
        # Simplify lines if needed
        if feature_geometry in ("LineString", "MultiLineString"):
            geo_features_clipped = geo_features_clipped.dissolve(by="id")
            geo_features_clipped["geometry"] = geo_features_clipped["geometry"].simplify(1)
        return geo_features_clipped
    except ox._errors.InsufficientResponseError:
        return None

    except Exception as e :
        return e

def plot_geo_features_around_station(lat, lon, radius, tags, color):
    # --- station point ---
    station_loc_point = Point(lon, lat)
    point_gdf = gpd.GeoSeries([station_loc_point], crs="EPSG:4326")
    point_proj = point_gdf.to_crs(epsg=32643)

    # --- buffer ---
    buffer = point_proj.buffer(radius)
    buffer_gdf = gpd.GeoDataFrame(geometry=buffer, crs=point_proj.crs)

    # --- fetch OSM data ---
    geo_features = ox.features_from_point((lat, lon), tags=tags, dist=radius)

    if geo_features.empty:
        raise ValueError("No features found for given tags and radius")

    geo_features_proj = geo_features.to_crs(epsg=32643).reset_index(drop=True)

    # --- split geometry types ---
    lines = geo_features_proj[
        geo_features_proj.geom_type.isin(["LineString", "MultiLineString"])
    ]

    polygons = geo_features_proj[
        geo_features_proj.geom_type.isin(["Polygon", "MultiPolygon"])
    ]

    # --- spatial operations ---
    line_clip = gpd.clip(lines, buffer_gdf) if not lines.empty else lines
    poly_clip = gpd.clip(polygons, buffer_gdf) if not polygons.empty else polygons

    # --- back to WGS84 ---
    buffer_wgs = buffer_gdf.to_crs(epsg=4326)
    line_wgs = line_clip.to_crs(epsg=4326) if not line_clip.empty else line_clip
    poly_wgs = poly_clip.to_crs(epsg=4326) if not poly_clip.empty else poly_clip

    # --- map ---
    m = folium.Map(location=[lat, lon], tiles='CartoDB positron')

    # buffer
    folium.GeoJson(
        buffer_wgs.__geo_interface__,
        style_function=lambda x: {
            "fillColor": "none",
            "color": "red",
            "weight": 2
        }
    ).add_to(m)

    # polygons (buildings, landuse, etc.)
    if not poly_wgs.empty:
        folium.GeoJson(
            poly_wgs.__geo_interface__,
            style_function=lambda x: {
                "fillColor": color,
                "color": color,
                "weight": 1,
                "fillOpacity": 0.5
            }
        ).add_to(m)

    # lines (highways, paths, etc.)
    if not line_wgs.empty:
        folium.GeoJson(
            line_wgs.__geo_interface__,
            style_function=lambda x: {
                "color": color,
                "weight": 2
            }
        ).add_to(m)

    # center marker
    # folium.Marker([lat, lon], popup="Location").add_to(m)
    folium.CircleMarker(
        location=[lat, lon],
        radius=8,
        color="black",
        weight=3,
        fill=True,
        fillColor="red",
        fillOpacity=1,
        popup=folium.Popup(
            f"""
            <b>Monitoring Station</b><br>
            Latitude: {lat:.6f}<br>
            Longitude: {lon:.6f}
            """,
            max_width=250
        ),
        tooltip="Monitoring Station"
    ).add_to(m)

    m.fit_bounds(m.get_bounds())
    return m

def create_combined_map(lat, lon, radius, buffer_gdf,
                         parks_gdf=None,
                         highways_gdf=None,
                         industries_gdf=None):

    # --- map base ---
    m = folium.Map(location=[lat, lon], tiles="CartoDB positron")

    # --- buffer ---
    buffer_wgs = buffer_gdf.to_crs(epsg=4326)

    folium.GeoJson(
        buffer_wgs.__geo_interface__,
        style_function=lambda x: {
            "fillColor": "none",
            "color": "red",
            "weight": 2
        }
    ).add_to(m)

    # --- helper to plot GeoDataFrame ---
    def plot_gdf(gdf, color, weight=2, fill=False):
        if gdf is None or gdf.empty:
            return

        gdf_wgs = gdf.to_crs(epsg=4326)

        for _, row in gdf_wgs.iterrows():
            geom = row.geometry

            if geom.geom_type == "LineString":
                coords = [(y, x) for x, y in geom.coords]
                folium.PolyLine(coords, color=color, weight=weight).add_to(m)

            elif geom.geom_type == "MultiLineString":
                for line in geom:
                    coords = [(y, x) for x, y in line.coords]
                    folium.PolyLine(coords, color=color, weight=weight).add_to(m)

            elif geom.geom_type in ["Polygon", "MultiPolygon"] and fill:
                folium.GeoJson(
                    geom,
                    style_function=lambda x: {
                        "fillColor": color,
                        "color": color,
                        "weight": 1,
                        "fillOpacity": 0.4
                    }
                ).add_to(m)

    # --- plot layers ---
    plot_gdf(parks_gdf, color="green", fill=True)
    plot_gdf(highways_gdf, color="yellow")
    plot_gdf(industries_gdf, color="blue", fill=True)

    # --- center marker ---
    folium.Marker([lat, lon], popup="Location").add_to(m)

    m.fit_bounds(m.get_bounds())
    return m

@st.cache_data(ttl=3600, show_spinner=False)
def get_osm_features_cached(lat, lon, radius, tags):
    """
    Fetch OSM features from Overpass and cache the result.

    Cache duration:
        3600 seconds = 1 hour
    """

    return ox.features_from_point(
        (lat, lon),
        tags=tags,
        dist=radius
    )

def create_station_feature_map(
    lat,
    lon,
    radius,
    feature_groups
):
    """
    Create Folium map and calculate feature summaries.
    """

    # ========================================================
    # 1. UTM
    # ========================================================

    epsg = get_utm_epsg(
        lat,
        lon
    )

    # ========================================================
    # 2. Station point
    # ========================================================

    station_point = gpd.GeoSeries(
        [Point(lon, lat)],
        crs="EPSG:4326"
    ).to_crs(
        epsg=epsg
    )

    # ========================================================
    # 3. Station buffer
    # ========================================================

    buffer_geom = (
        station_point
        .buffer(radius)
        .iloc[0]
    )

    buffer_gdf = gpd.GeoDataFrame(
        geometry=[buffer_geom],
        crs=f"EPSG:{epsg}"
    )

    # ========================================================
    # 4. CREATE FOLIUM MAP
    # ========================================================

    m = folium.Map(
        location=[lat, lon],
        zoom_start=15,
        tiles="CartoDB positron",

        # Important for performance
        prefer_canvas=True,

        # Don't show Leaflet zoom animation
        zoom_control=True
    )

    # ========================================================
    # 5. DISABLE LEAFLET TILE FADE
    # ========================================================

    # Leaflet normally fades new tiles in.
    # This can look like a blurry map during zooming.

    disable_animation = folium.Element(
        """
        <script>
        document.addEventListener("DOMContentLoaded", function() {

            setTimeout(function() {

                var maps = document.querySelectorAll(
                    '.leaflet-container'
                );

                maps.forEach(function(container) {

                    container.style.transition = "none";

                    var tiles = container.querySelectorAll(
                        '.leaflet-tile'
                    );

                    tiles.forEach(function(tile) {
                        tile.style.transition = "none";
                        tile.style.opacity = "1";
                    });

                });

            }, 100);

        });
        </script>
        """
    )

    m.get_root().html.add_child(
        disable_animation
    )

    # ========================================================
    # 6. BUFFER
    # ========================================================

    buffer_wgs = buffer_gdf.to_crs(
        epsg=4326
    )

    folium.GeoJson(
        buffer_wgs.__geo_interface__,
        style_function=lambda x: {
            "fillColor": "none",
            "color": "red",
            "weight": 2,
            "fillOpacity": 0
        }
    ).add_to(m)

    # ========================================================
    # 7. SUMMARY
    # ========================================================

    area_summary = {}

    # ========================================================
    # 8. PLOT HELPER
    # ========================================================

    def plot_gdf(
        gdf,
        color,
        fill=False,
        weight=2
    ):

        if gdf is None:
            return

        if not isinstance(
            gdf,
            gpd.GeoDataFrame
        ):
            return

        if gdf.empty:
            return

        gdf_wgs = gdf.to_crs(
            epsg=4326
        )

        # ----------------------------------------------------
        # Instead of creating a Folium object for every
        # individual geometry, create ONE GeoJSON layer.
        #
        # This is much faster for Leaflet.
        # ----------------------------------------------------

        if fill:

            features = []

            for _, row in gdf_wgs.iterrows():

                geom = row.geometry

                if (
                    geom is None
                    or geom.is_empty
                ):
                    continue

                features.append({
                    "type": "Feature",
                    "geometry": geom.__geo_interface__,
                    "properties": {}
                })

            if not features:
                return

            geojson = {
                "type": "FeatureCollection",
                "features": features
            }

            folium.GeoJson(
                geojson,
                style_function=lambda x, c=color: {
                    "fillColor": c,
                    "color": c,
                    "weight": 1,
                    "fillOpacity": 0.4
                }
            ).add_to(m)

            return

        # ----------------------------------------------------
        # Lines
        # ----------------------------------------------------

        features = []

        for _, row in gdf_wgs.iterrows():

            geom = row.geometry

            if (
                geom is None
                or geom.is_empty
            ):
                continue

            features.append({
                "type": "Feature",
                "geometry": geom.__geo_interface__,
                "properties": {}
            })

        if not features:
            return

        geojson = {
            "type": "FeatureCollection",
            "features": features
        }

        folium.GeoJson(
            geojson,
            style_function=lambda x, c=color, w=weight: {
                "color": c,
                "weight": w,
                "fillOpacity": 0
            }
        ).add_to(m)

    # ========================================================
    # 9. PROCESS FEATURE GROUPS
    # ========================================================

    for group_name, config in feature_groups.items():

        tags = config.get("tags")

        color = config.get(
            "color",
            "blue"
        )

        geometry_type = config.get(
            "geometry"
        )

        # ----------------------------------------------------
        # GET CACHED OSM DATA
        # ----------------------------------------------------

        try:

            geo_features = (
                get_osm_features_cached(
                    lat,
                    lon,
                    radius,
                    tags
                )
            )

        except ox._errors.InsufficientResponseError:

            print(
                f"No OSM response for {group_name}"
            )

            continue

        except Exception as e:

            print(
                f"Error fetching {group_name}: {e}"
            )

            continue

        if geo_features is None:
            continue

        if geo_features.empty:
            continue

        # ----------------------------------------------------
        # PROJECT TO UTM
        # ----------------------------------------------------

        geo_features = geo_features.to_crs(
            epsg=epsg
        )

        # ----------------------------------------------------
        # FILTER GEOMETRY
        # ----------------------------------------------------

        if geometry_type:

            allowed_geometry = {
                geometry_type,
                f"Multi{geometry_type}"
            }

            geo_features = geo_features[
                geo_features.geom_type.isin(
                    allowed_geometry
                )
            ]

        if geo_features.empty:
            continue

        # ----------------------------------------------------
        # CLIP
        # ----------------------------------------------------

        try:

            clipped_gdf = gpd.clip(
                geo_features,
                buffer_gdf
            )

        except Exception as e:

            print(
                f"Error clipping {group_name}: {e}"
            )

            continue

        if (
            clipped_gdf is None
            or clipped_gdf.empty
        ):
            continue

        # ====================================================
        # 10. AREA / LENGTH
        # ====================================================

        if geometry_type in (
            "LineString",
            "MultiLineString"
        ):

            length_m = (
                clipped_gdf
                .geometry
                .length
                .sum()
            )

            area_summary[group_name] = {
                "length_m": float(
                    length_m
                ),
                "length_km": float(
                    length_m / 1000
                )
            }

        else:

            polygon_gdf = clipped_gdf[
                clipped_gdf.geom_type.isin(
                    [
                        "Polygon",
                        "MultiPolygon"
                    ]
                )
            ]

            if not polygon_gdf.empty:

                total_area_m2 = (
                    polygon_gdf
                    .geometry
                    .area
                    .sum()
                )

                area_summary[group_name] = {
                    "area_m2": float(
                        total_area_m2
                    ),
                    "area_ha": float(
                        total_area_m2 / 10000
                    )
                }

        # ====================================================
        # 11. SIMPLIFY
        # ====================================================

        if geometry_type in (
            "LineString",
            "MultiLineString"
        ):

            clipped_gdf = clipped_gdf.copy()

            # Dissolve when possible
            if "id" in clipped_gdf.columns:

                try:

                    clipped_gdf = (
                        clipped_gdf
                        .dissolve(by="id")
                    )

                except Exception:
                    pass

            # Simplify geometry
            clipped_gdf["geometry"] = (
                clipped_gdf.geometry.simplify(
                    2,
                    preserve_topology=True
                )
            )

        # ====================================================
        # 12. ADD TO MAP
        # ====================================================

        is_polygon = geometry_type in (
            "Polygon",
            "MultiPolygon"
        )

        plot_gdf(
            clipped_gdf,
            color=color,
            fill=is_polygon,
            weight=2
        )

    # ========================================================
    # 13. STATION MARKER
    # ========================================================

    # folium.Marker(
    #     location=[
    #         lat,
    #         lon
    #     ],
    #     popup="Location"
    # ).add_to(m)
    # ========================================================
    # STATION MARKER
    # ========================================================

    station_marker = folium.Marker(
        location=[float(lat), float(lon)],
        tooltip="📍 Monitoring Station",
        popup=folium.Popup(
            f"""
            <div style="font-size:14px;">
                <b>Monitoring Station</b><br>
                Latitude: {float(lat):.6f}<br>
                Longitude: {float(lon):.6f}
            </div>
            """,
            max_width=250
        ),
        icon=folium.DivIcon(
            html="""
            <div style="
                width: 24px;
                height: 24px;
                background: red;
                border: 4px solid white;
                border-radius: 50%;
                box-shadow: 0 0 0 3px black, 0 2px 8px rgba(0,0,0,0.6);
                position: relative;
                left: -12px;
                top: -12px;
                z-index: 9999;
            "></div>
            """
        )
    )

    station_marker.add_to(m)

    # ========================================================
    # 14. FIT BOUNDS
    # ========================================================

    minx, miny, maxx, maxy = (
        buffer_wgs.total_bounds
    )

    m.fit_bounds(
        [
            [miny, minx],
            [maxy, maxx]
        ],
        padding=(20, 20)
    )

    # ========================================================
    # 15. RETURN
    # ========================================================

    return (
        m,
        area_summary
    )


@st.cache_resource(
    ttl=3600,
    show_spinner=False
)
def get_cached_station_map(
    lat,
    lon,
    radius,
    feature_groups
):
    """
    Cache the completed Folium map.

    This is different from caching the OSM data.
    """

    return create_station_feature_map(
        lat,
        lon,
        radius,
        feature_groups
    )

