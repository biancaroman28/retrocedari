import pandas as pd
import plotly.express as px
import geopandas as gpd
from shapely.geometry import Point

# TOP 5 LEGI
top_legi = ["92/1950", "223/1974", "111/1951", "224/1951", "4/1973"]

color_map = {
    "92/1950": "#1f77b4",
    "223/1974": "#ff7f0e",
    "111/1951": "#2ca02c",
    "224/1951": "#d62728",
    "4/1973": "#9467bd",
    "Altele": "#7f7f7f"
}

df = pd.read_csv("../../pdfuri_restituire_deposedare.csv")
df = df[df["Solutie_grup"] == "Restituire"].copy()

# Curățare coordonate
df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
df = df.dropna(subset=["lat", "lon"])

# Curățare an
df["An_solutie"] = pd.to_numeric(df["An_solutie"], errors="coerce")
df = df.dropna(subset=["An_solutie"])
df["An_solutie"] = df["An_solutie"].astype(int)

# Categorie lege
df["Lege_top"] = df["Lege"].apply(
    lambda x: x if x in top_legi else "Altele"
)

df["Lege_top"] = pd.Categorical(
    df["Lege_top"],
    categories=top_legi + ["Altele"],
    ordered=True
)

# Geo
df["geometry"] = [Point(xy) for xy in zip(df["lon"], df["lat"])]
gdf_points = gpd.GeoDataFrame(df, geometry="geometry", crs="EPSG:4326")

gdf_poly = gpd.read_file(
    "../../RO-B-294fb6d7-20251108-en-gpkg/data/boundary-polygon.gpkg"
).to_crs("EPSG:4326")

buc_union = gdf_poly.geometry.union_all()
puncte_in = gdf_points[gdf_points.within(buc_union)].copy()

ani_completi = list(
    range(
        int(puncte_in["An_solutie"].min()),
        int(puncte_in["An_solutie"].max()) + 1
    )
)

puncte_in["lat_r"] = puncte_in["lat"].round(5)
puncte_in["lon_r"] = puncte_in["lon"].round(5)

# Agregare
agg = (
    puncte_in
    .groupby(["An_solutie", "Lege_top", "lat_r", "lon_r"], observed=True)
    .agg(
        n_locatie=("lat_r", "size"),
        Adresa_contemporană=("Adresa contemporană",
                             lambda x: "<br>".join(x.astype(str).unique()[:5])),
        Pdf_nume=("Pdf_nume",
                  lambda x: "<br>".join(x.astype(str).unique()[:5])),
        Dosar_PMB=("Dosar PMB",
                   lambda x: "<br>".join(x.astype(str).unique()[:5])),
        Tip_proprietate=("Tip proprietate",
                         lambda x: "<br>".join(x.astype(str).unique()[:5])),
    )
    .reset_index()
)

# Scaffold pentru ani fără date
scaffold = pd.DataFrame(
    [(y, s) for y in ani_completi for s in top_legi + ["Altele"]],
    columns=["An_solutie", "Lege_top"]
)

scaffold["lat_r"] = pd.NA
scaffold["lon_r"] = pd.NA
scaffold["n_locatie"] = 0
scaffold["Adresa_contemporană"] = ""
scaffold["Pdf_nume"] = ""

puncte_animatie = pd.concat([agg, scaffold], ignore_index=True)

puncte_animatie["An_solutie"] = pd.Categorical(
    puncte_animatie["An_solutie"],
    categories=ani_completi,
    ordered=True
)

# Count pe ani pentru legendă
counts = (
    puncte_in
    .groupby(["An_solutie", "Lege_top"], observed=True)
    .size()
    .reindex(
        pd.MultiIndex.from_product(
            [ani_completi, top_legi + ["Altele"]],
            names=["An_solutie", "Lege_top"]
        ),
        fill_value=0
    )
    .reset_index(name="n")
)

counts_by_year = {
    int(y): dict(zip(g["Lege_top"].astype(str), g["n"].astype(int)))
    for y, g in counts.groupby("An_solutie")
}

fig = px.scatter_mapbox(
    puncte_animatie,
    lat="lat_r",
    lon="lon_r",
    color="Lege_top",
    animation_frame="An_solutie",
    category_orders={
        "An_solutie": ani_completi,
        "Lege_top": top_legi + ["Altele"]
    },
    color_discrete_map=color_map,
    custom_data=[
    "Lege_top",
    "n_locatie",
    "Adresa_contemporană",
    "Pdf_nume",
    "Dosar_PMB",
    "Tip_proprietate",
    ],

    zoom=11,
    center={"lat": 44.43, "lon": 26.10},
)

fig.update_traces(marker=dict(size=16))

HOVER_TEMPLATE = (
    "<b>Lege:</b> %{customdata[0]}<br>"
    "<b>Număr PDF-uri (locație):</b> %{customdata[1]}<br>"
    "<b>Adresa:</b><br>%{customdata[2]}<br>"
    "<b>PDF-uri:</b><br>%{customdata[3]}<br>"
    "<b>Dosar PMB:</b><br>%{customdata[4]}<br>"
    "<b>Tip proprietate:</b><br>%{customdata[5]}<br>"
    "<extra></extra>"
)


for tr in fig.data:
    tr.hovertemplate = HOVER_TEMPLATE
for fr in fig.frames:
    for tr in fr.data:
        tr.hovertemplate = HOVER_TEMPLATE

def _apply_counts(traces, year_counts):
    for tr in traces:
        lege = tr.legendgroup if tr.legendgroup else tr.name
        if lege is None:
            continue
        lege = str(lege)
        tr.name = f"{lege} ({year_counts.get(lege, 0)})"
        tr.legendgroup = lege

_apply_counts(fig.data, counts_by_year.get(int(ani_completi[0]), {}))
for fr in fig.frames:
    try:
        y = int(fr.name)
    except Exception:
        continue
    _apply_counts(fr.data, counts_by_year.get(y, {}))

fig.update_layout(
    mapbox_style="open-street-map",
    title="Distribuția imobilelor după legea de preluare pe ani",
    legend_title_text="Lege",
    width=1800,
    height=900,
)

# BAR TOTAL PE ANI
total_by_year = (
    puncte_in
    .groupby("An_solutie")
    .size()
    .reindex(ani_completi, fill_value=0)
    .reset_index(name="total_pdfuri")
)

fig_bar = px.bar(
    total_by_year,
    x="An_solutie",
    y="total_pdfuri",
)

fig_bar.update_layout(
    title="Număr total PDF-uri pe ani",
    width=1800,
    height=450,
)

# STACKED ABSOLUT
stacked = (
    puncte_in
    .groupby(["An_solutie", "Lege_top"], observed=True)
    .size()
    .reset_index(name="n_pdfuri")
)

fig_stacked = px.bar(
    stacked,
    x="An_solutie",
    y="n_pdfuri",
    color="Lege_top",
    color_discrete_map=color_map,
    category_orders={
        "An_solutie": ani_completi,
        "Lege_top": top_legi + ["Altele"]
    },
)

fig_stacked.update_layout(
    barmode="stack",
    title="Structura legilor pe ani",
    width=1800,
    height=500,
)

HTML_CONFIG = {
    "scrollZoom": True,
    "displayModeBar": True,
}

with open("../../docs/spatial_distribution_legislation.html", "w", encoding="utf-8") as f:
    f.write(fig.to_html(full_html=False, include_plotlyjs="cdn", config=HTML_CONFIG))
    f.write("<hr>")
    f.write(fig_bar.to_html(full_html=False, include_plotlyjs=False))
    f.write("<hr>")
    f.write(fig_stacked.to_html(full_html=False, include_plotlyjs=False))
