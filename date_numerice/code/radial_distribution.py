import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import geopandas as gpd
from shapely.geometry import Point
import numpy as np

df = pd.read_csv("dosare_pmb.csv")

df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
df = df.dropna(subset=["lat", "lon", "Solutie_grup"])

df = df[df["Solutie_grup"] != "NONE"]

gdf = gpd.GeoDataFrame(
    df,
    geometry=gpd.points_from_xy(df.lon, df.lat),
    crs="EPSG:4326"
)

gdf_poly = gpd.read_file(
    "RO-B-294fb6d7-20251108-en-gpkg/data/boundary-polygon.gpkg"
).to_crs("EPSG:4326")

buc = gdf_poly.geometry.union_all()
gdf = gdf[gdf.within(buc)].copy()

top_solutions = (
    gdf["Solutie_grup"]
    .value_counts()
    .head(5)
    .index
    .tolist()
)

gdf = gdf[gdf["Solutie_grup"].isin(top_solutions)].copy()

center = gdf.geometry.unary_union.centroid
center_lat, center_lon = center.y, center.x

gdf_m = gdf.to_crs("EPSG:3857")
center_m = gdf_m.geometry.unary_union.centroid

gdf_m["dist_km"] = gdf_m.geometry.distance(center_m) / 1000
gdf["dist_km"] = gdf_m["dist_km"].values

#1KM DISTANCE 
gdf["dist_bin"] = gdf["dist_km"].apply(lambda x: int(np.floor(x)))


fig_map = px.scatter_mapbox(
    gdf,
    lat="lat",
    lon="lon",
    color="Solutie_grup",
    zoom=11,
    center={"lat": center_lat, "lon": center_lon},
    opacity=0.7,
)

max_km = int(np.ceil(gdf["dist_km"].max()))
for r in range(1, max_km + 1):
    circle = center_m.buffer(r * 1000)
    circle_wgs = gpd.GeoSeries(circle, crs="EPSG:3857").to_crs("EPSG:4326").iloc[0]
    xs, ys = circle_wgs.exterior.xy

    fig_map.add_trace(
        go.Scattermapbox(
            lon=list(xs),
            lat=list(ys),
            mode="lines",
            line=dict(color="black", width=1),
            hoverinfo="text",
            text=f"{r} km",
            showlegend=False,
        )
    )

fig_map.update_layout(
    mapbox_style="open-street-map",
    title="Distributia dosarelor fata de KM 0",
    width=1800,
    height=900,
)

#HISTOGRAMA 

hist = (
    gdf
    .groupby(["dist_bin", "Solutie_grup"])
    .size()
    .reset_index(name="n_dosare")
)

fig_hist = px.bar(
    hist,
    x="dist_bin",
    y="n_dosare",
    color="Solutie_grup",
    barmode="group",
)

fig_hist.update_layout(
    title="Histograma radiala",
    xaxis_title="Distanta fata de centru (km)",
    yaxis_title="Numar dosare",
    width=1800,
    height=500,
)

with open("radial_distribution.html", "w", encoding="utf-8") as f:
    f.write(fig_map.to_html(full_html=False, include_plotlyjs="cdn"))
    f.write("<hr>")
    f.write(fig_hist.to_html(full_html=False, include_plotlyjs=False))

fig_map.show()
fig_hist.show()
