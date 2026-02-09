import pandas as pd
import plotly.express as px
import geopandas as gpd
from shapely.geometry import Point

# =========================
# 1) CONFIG: TOP LEGI + CULORI
# =========================
top_legi = ["92/1950", "223/1974", "111/1951", "224/1951", "4/1973"]

color_map = {
    "92/1950": "#1f77b4",
    "223/1974": "#ff7f0e",
    "111/1951": "#2ca02c",
    "224/1951": "#d62728",
    "4/1973": "#9467bd",
    "Altele": "#7f7f7f",
}

# =========================
# 2) LOAD PDF CSV
# =========================
df = pd.read_csv("../../pdfuri_restituire_deposedare.csv")

df = df[df["Solutie_grup"] == "Restituire"].copy()

# coordonate
df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
df = df.dropna(subset=["lat", "lon"])

# an
df["An_solutie"] = pd.to_numeric(df["An_solutie"], errors="coerce")
df = df.dropna(subset=["An_solutie"])
df["An_solutie"] = df["An_solutie"].astype(int)

# lege top5 + altele
df["Lege"] = df["Lege"].astype(str).str.strip()
df["Lege_top"] = df["Lege"].apply(lambda x: x if x in top_legi else "Altele")

cat_legi = top_legi + ["Altele"]
df["Lege_top"] = pd.Categorical(df["Lege_top"], categories=cat_legi, ordered=True)

# =========================
# 3) GEO: puncte in Bucuresti
# =========================
df["geometry"] = [Point(xy) for xy in zip(df["lon"], df["lat"])]
gdf_points = gpd.GeoDataFrame(df, geometry="geometry", crs="EPSG:4326")

gdf_poly = gpd.read_file(
    "../../RO-B-294fb6d7-20251108-en-gpkg/data/boundary-polygon.gpkg"
).to_crs("EPSG:4326")

buc_union = gdf_poly.geometry.union_all()
puncte_in = gdf_points[gdf_points.within(buc_union)].copy()

# =========================
# 4) ANI + ROUND COORD
# =========================
ani = list(
    range(
        int(puncte_in["An_solutie"].min()),
        int(puncte_in["An_solutie"].max()) + 1,
    )
)

puncte_in["lat_r"] = puncte_in["lat"].round(5)
puncte_in["lon_r"] = puncte_in["lon"].round(5)

# =========================
# 5) AGG HELPERS
# =========================
def agg_text(series, max_items=9, per_line=3):
    vals = series.dropna().astype(str).unique()
    if len(vals) == 0:
        return ""
    total = len(vals)
    vals = vals[:max_items]
    lines = [
        " | ".join(vals[i : i + per_line])
        for i in range(0, len(vals), per_line)
    ]
    text = "<br>".join(lines)
    if total > max_items:
        text += "<br>..."
    return text

# =========================
# 6) FRAMES CUMULATIVE (<= an)
# =========================
frames = []

for an in ani:
    df_cum = puncte_in[puncte_in["An_solutie"] <= an]

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
    agg["An_slider"] = an
    frames.append(agg)

puncte_animatie = pd.concat(frames, ignore_index=True)

# gid (opțional pt animation_group; la tine era comentat)
puncte_animatie["gid"] = (
    puncte_animatie["Lege_top"].astype(str)
    + "|"
    + puncte_animatie["lat_r"].astype(str)
    + "|"
    + puncte_animatie["lon_r"].astype(str)
)

# =========================
# 7) SCAFFOLD (ca să apară toate legendele la fiecare an)
# =========================
scaffold = pd.DataFrame(
    [(an, lege) for an in ani for lege in cat_legi],
    columns=["An_slider", "Lege_top"],
)

scaffold["lat_r"] = pd.NA
scaffold["lon_r"] = pd.NA
scaffold["n_locatie"] = 0
scaffold["An_aparitie"] = pd.NA
scaffold["Adresa_contemporană"] = ""
scaffold["Pdf_nume"] = ""
scaffold["gid"] = scaffold["Lege_top"].astype(str) + "|DUMMY|" + scaffold["An_slider"].astype(str)

puncte_animatie = pd.concat([puncte_animatie, scaffold], ignore_index=True)

# =========================
# 8) COUNTS BY YEAR (cumulativ) pentru legendă
# =========================
counts_by_year = {}
for an in ani:
    c = (
        puncte_in[puncte_in["An_solutie"] <= an]
        .groupby("Lege_top", observed=True)
        .size()
        .reindex(cat_legi, fill_value=0)
        .astype(int)
        .to_dict()
    )
    counts_by_year[int(an)] = {str(k): int(v) for k, v in c.items()}

def apply_counts(traces, year_counts):
    for tr in traces:
        cat = tr.legendgroup if tr.legendgroup else tr.name
        if cat is None:
            continue
        cat = str(cat)
        tr.name = f"{cat} ({year_counts.get(cat, 0)})"
        tr.legendgroup = cat

# =========================
# 9) MAP ANIMATION
# =========================
fig = px.scatter_mapbox(
    puncte_animatie,
    lat="lat_r",
    lon="lon_r",
    color="Lege_top",
    animation_frame="An_slider",
    # animation_group="gid",
    category_orders={
        "An_slider": ani,
        "Lege_top": cat_legi,
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
apply_counts(fig.data, counts_by_year[int(ani[0])])

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
    if tr.name and "|DUMMY|" in tr.name:
        tr.hoverinfo = "skip"
    else:
        tr.hovertemplate = HOVER_TEMPLATE

for fr in fig.frames:
    try:
        an = int(fr.name)
    except Exception:
        continue
    apply_counts(fr.data, counts_by_year.get(an, {}))
    for tr in fr.data:
        if tr.name and "|DUMMY|" in tr.name:
            tr.hoverinfo = "skip"
        else:
            tr.hovertemplate = HOVER_TEMPLATE

fig.update_layout(
    mapbox_style="open-street-map",
    title="Evoluția cumulativă a imobilelor după legea de preluare",
    legend_title_text="Lege",
    width=1800,
    height=900,
)

# =========================
# 10) LINE CHART: cumulativ pe legi
# =========================
rows = []
for an in ani:
    for lege in cat_legi:
        n = puncte_in[
            (puncte_in["An_solutie"] <= an)
            & (puncte_in["Lege_top"] == lege)
        ].shape[0]
        rows.append((an, lege, n))

df_line = pd.DataFrame(rows, columns=["An", "Lege_top", "n_pdfuri"])

fig_line = px.line(
    df_line,
    x="An",
    y="n_pdfuri",
    color="Lege_top",
    markers=True,
    category_orders={"Lege_top": cat_legi},
    color_discrete_map=color_map,
)

fig_line.update_layout(
    title="Evoluția legilor în timp (cumulativ)",
    xaxis_title="An",
    yaxis_title="Număr PDF-uri (cumulativ)",
    width=1800,
    height=450,
)

# =========================
# 11) BAR: total cumulativ pe ani
# =========================
annual_counts = (
    puncte_in
    .groupby("An_solutie")
    .size()
    .reindex(ani, fill_value=0)
    .reset_index(name="pdfuri_anuale")
)

annual_counts["pdfuri_cumulative"] = annual_counts["pdfuri_anuale"].cumsum()
annual_counts["delta_abs"] = annual_counts["pdfuri_cumulative"].diff()

def make_label_cum(r):
    if pd.isna(r["delta_abs"]):
        return f"{int(r['pdfuri_cumulative'])}"
    sign = "+" if r["delta_abs"] > 0 else ""
    return f"{int(r['pdfuri_cumulative'])} ({sign}{int(r['delta_abs'])})"

annual_counts["label"] = annual_counts.apply(make_label_cum, axis=1)

fig_bar = px.bar(
    annual_counts,
    x="An_solutie",
    y="pdfuri_cumulative",
    text="label",
)

fig_bar.update_layout(
    title="Număr total de PDF-uri (cumulativ) în timp",
    xaxis_title="An",
    yaxis_title="Număr total PDF-uri",
    width=1800,
    height=450,
)

fig_bar.update_traces(textposition="outside")

# =========================
# 12) EXPORT HTML
# =========================
HTML_CONFIG = {
    "scrollZoom": True,
    "displayModeBar": True,
}

with open("../../docs/legislation_temporal_evolution.html", "w", encoding="utf-8") as f:
    f.write(
        fig.to_html(
            full_html=False,
            include_plotlyjs="cdn",
            config=HTML_CONFIG
        )
    )
    f.write("<hr>")
    f.write(fig_line.to_html(full_html=False, include_plotlyjs=False))
    f.write("<hr>")
    f.write(fig_bar.to_html(full_html=False, include_plotlyjs=False))

fig.show()
fig_line.show()
fig_bar.show()
