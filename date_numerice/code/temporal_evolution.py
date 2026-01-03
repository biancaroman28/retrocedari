import pandas as pd
import plotly.express as px
import geopandas as gpd
from shapely.geometry import Point


df = pd.read_csv("dosare_pmb.csv")

df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
df = df.dropna(subset=["lat", "lon"])

df["An_solutie"] = pd.to_numeric(df["An_solutie"], errors="coerce")
df = df.dropna(subset=["An_solutie"])
df["An_solutie"] = df["An_solutie"].astype(int)


df["geometry"] = [Point(xy) for xy in zip(df["lon"], df["lat"])]
gdf_points = gpd.GeoDataFrame(df, geometry="geometry", crs="EPSG:4326")


gdf_poly = gpd.read_file(
    "RO-B-294fb6d7-20251108-en-gpkg/data/boundary-polygon.gpkg"
).to_crs("EPSG:4326")

buc_union = gdf_poly.geometry.union_all()
puncte_in = gdf_points[gdf_points.within(buc_union)].copy()

sol_count = (
    puncte_in["Solutie_grup"]
    .dropna()
    .loc[puncte_in["Solutie_grup"] != "NONE"]
    .value_counts()
)

top_solutions = sol_count.head(5).index.tolist()

puncte_filtrate = puncte_in[
    puncte_in["Solutie_grup"].isin(top_solutions)
].copy()

puncte_filtrate["Solutie_grup"] = pd.Categorical(
    puncte_filtrate["Solutie_grup"],
    categories=top_solutions,
    ordered=True
)

ani = list(
    range(
        int(puncte_filtrate["An_solutie"].min()),
        int(puncte_filtrate["An_solutie"].max()) + 1
    )
)

puncte_filtrate["lat_r"] = puncte_filtrate["lat"].round(5)
puncte_filtrate["lon_r"] = puncte_filtrate["lon"].round(5)


def agg_text(series, max_items=9, per_line=3):
    vals = series.dropna().astype(str).unique()
    if len(vals) == 0:
        return ""

    total = len(vals)
    vals = vals[:max_items]

    lines = [
        " | ".join(vals[i:i + per_line])
        for i in range(0, len(vals), per_line)
    ]

    text = "<br>".join(lines)

    if total > max_items:
        text += "<br>..."

    return text

frames = []

for an in ani:
    df_cum = puncte_filtrate[puncte_filtrate["An_solutie"] <= an]

    agg = (
        df_cum
        .groupby(["Solutie_grup", "lat_r", "lon_r"], observed=True)
        .agg(
            n_locatie=("lat_r", "size"),
            An_aparitie=("An_solutie", "min"),
            Adresa_contemporană=("Adresa contemporană", agg_text),
            Adresa_istorică=("Adresa istorică", agg_text),
            Tip_proprietate=("Tip proprietate", agg_text),
            Dosar_PMB=("Dosar PMB", agg_text),
        )
        .reset_index()
    )

    agg["An_slider"] = an
    frames.append(agg)

puncte_animatie = pd.concat(frames, ignore_index=True)

puncte_animatie["gid"] = (
    puncte_animatie["Solutie_grup"].astype(str)
    + "|" + puncte_animatie["lat_r"].astype(str)
    + "|" + puncte_animatie["lon_r"].astype(str)
)

scaffold = pd.DataFrame(
    [(an, sol) for an in ani for sol in top_solutions],
    columns=["An_slider", "Solutie_grup"]
)

scaffold["lat_r"] = pd.NA
scaffold["lon_r"] = pd.NA
scaffold["n_locatie"] = 0
scaffold["An_aparitie"] = pd.NA
scaffold["Adresa_contemporană"] = ""
scaffold["Adresa_istorică"] = ""
scaffold["Tip_proprietate"] = ""
scaffold["Dosar_PMB"] = ""
scaffold["gid"] = scaffold["Solutie_grup"] + "|DUMMY|" + scaffold["An_slider"].astype(str)

puncte_animatie = pd.concat([puncte_animatie, scaffold], ignore_index=True)

rows = []

for an in ani:
    for sol in top_solutions:
        n = (
            puncte_filtrate[
                (puncte_filtrate["An_solutie"] <= an) &
                (puncte_filtrate["Solutie_grup"] == sol)
            ]
            .shape[0]
        )
        rows.append((an, sol, n))

df_line = pd.DataFrame(
    rows,
    columns=["An", "Solutie_grup", "n_dosare"]
)

counts_by_year = {}

for an in ani:
    c = (
        puncte_filtrate[puncte_filtrate["An_solutie"] <= an]
        .groupby("Solutie_grup", observed=True)
        .size()
        .reindex(top_solutions, fill_value=0)
        .astype(int)
        .to_dict()
    )
    counts_by_year[int(an)] = {str(k): int(v) for k, v in c.items()}


def apply_counts(traces, year_counts):
    for tr in traces:
        sol = tr.legendgroup if tr.legendgroup else tr.name
        if sol is None:
            continue
        sol = str(sol)
        tr.name = f"{sol} ({year_counts.get(sol, 0)})"
        tr.legendgroup = sol


fig = px.scatter_mapbox(
    puncte_animatie,
    lat="lat_r",
    lon="lon_r",
    color="Solutie_grup",
    animation_frame="An_slider",
    animation_group="gid",
    category_orders={
        "An_slider": ani,
        "Solutie_grup": top_solutions
    },
    custom_data=[
        "Solutie_grup",
        "n_locatie",
        "An_aparitie",
        "Adresa_contemporană",
        "Adresa_istorică",
        "Tip_proprietate",
        "Dosar_PMB",
    ],
    zoom=11,
    center={"lat": 44.43, "lon": 26.10},
)

apply_counts(fig.data, counts_by_year[int(ani[0])])


HOVER_TEMPLATE = (
    "<b>Soluție:</b> %{customdata[0]}<br>"
    "<b>Număr dosare:</b> %{customdata[1]}<br>"
    "<b>An apariție:</b> %{customdata[2]}<br>"
    "<b>Adresa contemporană:</b> %{customdata[3]}<br>"
    "<b>Adresa istorică:</b> %{customdata[4]}<br>"
    "<b>Tip proprietate:</b> %{customdata[5]}<br>"
    "<b>Dosar PMB:</b><br>%{customdata[6]}<br>"
    "<extra></extra>"
)

for tr in fig.data:
    if tr.name and "|DUMMY|" in tr.name:
        tr.hoverinfo = "skip"
    else:
        tr.hovertemplate = HOVER_TEMPLATE

for fr in fig.frames:
    for tr in fr.data:
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


fig.update_layout(
    mapbox_style="open-street-map",
    title="Evolutia cumulativa a solutiilor in timp",
    legend_title_text="Solutii",
    width=1800,
    height=900,
)

#line chart
fig_line = px.line(
    df_line,
    x="An",
    y="n_dosare",
    color="Solutie_grup",
    markers=True,
    category_orders={"Solutie_grup": top_solutions},
)

fig_line.update_layout(
    title="Evolutia solutiilor in timp",
    xaxis_title="An",
    yaxis_title="Numar dosare (cumulativ)",
    width=1800,
    height=450,
)

#bar chart
annual_counts = (
    puncte_filtrate
    .groupby("An_solutie")
    .size()
    .reindex(ani, fill_value=0)
    .reset_index(name="dosare_anuale")
)

annual_counts["dosare_cumulative"] = annual_counts["dosare_anuale"].cumsum()
annual_counts["delta_abs"] = annual_counts["dosare_cumulative"].diff()

def make_label_cum(r):
    if pd.isna(r["delta_abs"]):
        return f"{r['dosare_cumulative']}"
    sign = "+" if r["delta_abs"] > 0 else ""
    return f"{r['dosare_cumulative']} ({sign}{int(r['delta_abs'])})"

annual_counts["label"] = annual_counts.apply(make_label_cum, axis=1)

fig_bar = px.bar(
    annual_counts,
    x="An_solutie",
    y="dosare_cumulative",
    text="label",
)

fig_bar.update_layout(
    title="Numar total de dosare solutionate in timp",
    xaxis_title="An",
    yaxis_title="Numar total dosare",
    width=1800,
    height=450,
)

fig_bar.update_traces(textposition="outside")


with open("solutions_temporal_evolution.html", "w", encoding="utf-8") as f:
    f.write(fig.to_html(full_html=False, include_plotlyjs="cdn"))
    f.write("<hr>")
    f.write(fig_line.to_html(full_html=False, include_plotlyjs=False))
    f.write("<hr>")
    f.write(fig_bar.to_html(full_html=False, include_plotlyjs=False))


fig.show()
fig_line.show()
