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

ani_completi = list(
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

    vals = vals[:max_items]

    lines = [
        " | ".join(vals[i:i + per_line])
        for i in range(0, len(vals), per_line)
    ]

    text = "<br>".join(lines)

    if len(series.dropna().unique()) > max_items:
        text += "<br>..."

    return text

agg = (
    puncte_filtrate
    .groupby(["An_solutie", "Solutie_grup", "lat_r", "lon_r"], observed=True)
    .agg(
        n_locatie=("lat_r", "size"),
        Adresa_contemporană=("Adresa contemporană", agg_text),
        Adresa_istorică=("Adresa istorică", agg_text),
        Tip_proprietate=("Tip proprietate", agg_text),
        Dosar_PMB=("Dosar PMB", agg_text),   
    )
    .reset_index()
)

scaffold = pd.DataFrame(
    [(y, s) for y in ani_completi for s in top_solutions],
    columns=["An_solutie", "Solutie_grup"]
)

scaffold["lat_r"] = pd.NA
scaffold["lon_r"] = pd.NA
scaffold["n_locatie"] = 0
scaffold["Adresa_contemporană"] = ""
scaffold["Adresa_istorică"] = ""
scaffold["Tip_proprietate"] = ""
scaffold["Dosar_PMB"] = ""


puncte_animatie = pd.concat([agg, scaffold], ignore_index=True)

puncte_animatie["An_solutie"] = pd.Categorical(
    puncte_animatie["An_solutie"],
    categories=ani_completi,
    ordered=True
)
puncte_animatie["Solutie_grup"] = pd.Categorical(
    puncte_animatie["Solutie_grup"],
    categories=top_solutions,
    ordered=True
)

for col in [
    "Adresa_contemporană",
    "Adresa_istorică",
    "Tip_proprietate",
    "Dosar_PMB",   
]:
    puncte_animatie[col] = puncte_animatie[col].fillna("")

counts = (
    puncte_filtrate
    .groupby(["An_solutie", "Solutie_grup"], observed=True)
    .size()
    .reindex(
        pd.MultiIndex.from_product(
            [ani_completi, top_solutions],
            names=["An_solutie", "Solutie_grup"]
        ),
        fill_value=0
    )
    .reset_index(name="n")
)

counts_by_year = {
    int(y): dict(zip(g["Solutie_grup"].astype(str), g["n"].astype(int)))
    for y, g in counts.groupby("An_solutie")
}

fig = px.scatter_mapbox(
    puncte_animatie,
    lat="lat_r",
    lon="lon_r",
    color="Solutie_grup",
    animation_frame="An_solutie",
    category_orders={
        "An_solutie": ani_completi,
        "Solutie_grup": top_solutions
    },
    custom_data=[
    "Solutie_grup",
    "n_locatie",
    "Adresa_contemporană",
    "Adresa_istorică",
    "Tip_proprietate",
    "Dosar_PMB",  
    ],

    zoom=11,
    center={"lat": 44.43, "lon": 26.10},
)

HOVER_TEMPLATE = (
    "<b>Soluție:</b> %{customdata[0]}<br>"
    "<b>Număr dosare (locație):</b> %{customdata[1]}<br>"
    "<b>Adresa contemporană:</b> %{customdata[2]}<br>"
    "<b>Adresa istorică:</b> %{customdata[3]}<br>"
    "<b>Tip proprietate:</b> %{customdata[4]}<br>"
    "<b>Dosar PMB:</b> %{customdata[5]}<br>"  
    "<extra></extra>"
)


for tr in fig.data:
    tr.hovertemplate = HOVER_TEMPLATE
for fr in fig.frames:
    for tr in fr.data:
        tr.hovertemplate = HOVER_TEMPLATE

def _apply_counts(traces, year_counts):
    for tr in traces:
        sol = tr.legendgroup if tr.legendgroup else tr.name
        if sol is None:
            continue
        sol = str(sol)
        tr.name = f"{sol} ({year_counts.get(sol, 0)})"
        tr.legendgroup = sol

_apply_counts(fig.data, counts_by_year.get(int(ani_completi[0]), {}))
for fr in fig.frames:
    try:
        y = int(fr.name)
    except Exception:
        continue
    _apply_counts(fr.data, counts_by_year.get(y, {}))

fig.update_layout(
    mapbox_style="open-street-map",
    title="Distributia solutiilor pe ani",
    legend_title_text="Solutii",
    width=1800,
    height=900,
)


total_by_year = (
    puncte_filtrate
    .groupby("An_solutie")
    .size()
    .reindex(ani_completi, fill_value=0)
    .reset_index(name="total_dosare")
)

total_by_year["pct_yoy"] = (
    total_by_year["total_dosare"]
    .pct_change()
    .mul(100)
)

total_by_year["label"] = total_by_year.apply(
    lambda r: (
        f"{int(r.total_dosare)}"
        if pd.isna(r.pct_yoy)
        else f"{int(r.total_dosare)} ({r.pct_yoy:+.1f}%)"
    ),
    axis=1
)

fig_bar = px.bar(
    total_by_year,
    x="An_solutie",
    y="total_dosare",
    text="label",
)

fig_bar.update_layout(
    title="Numar total de dosare pe ani si variatia fata de anul precedent",
    xaxis_title="An",
    yaxis_title="Numar dosare",
    width=1800,
    height=450,
)

fig_bar.update_traces(textposition="outside")


stacked_by_year = (
    puncte_filtrate
    .groupby(["An_solutie", "Solutie_grup"], observed=True)
    .size()
    .reset_index(name="n_dosare")
)

stacked_by_year = (
    stacked_by_year
    .set_index(["An_solutie", "Solutie_grup"])
    .reindex(
        pd.MultiIndex.from_product(
            [ani_completi, top_solutions],
            names=["An_solutie", "Solutie_grup"]
        ),
        fill_value=0
    )
    .reset_index()
)

fig_stacked = px.bar(
    stacked_by_year,
    x="An_solutie",
    y="n_dosare",
    color="Solutie_grup",
    category_orders={
        "An_solutie": ani_completi,
        "Solutie_grup": top_solutions
    },
)

fig_stacked.update_layout(
    barmode="stack",
    title="Structura solutiilor pe ani",
    xaxis_title="An",
    yaxis_title="Numar dosare",
    legend_title_text="Solutie",
    width=1800,
    height=500,
)


stacked_pct = stacked_by_year.copy()

total_per_year = (
    stacked_pct
    .groupby("An_solutie", observed=True)["n_dosare"]
    .sum()
    .rename("total_an")
)

stacked_pct = stacked_pct.merge(
    total_per_year,
    on="An_solutie",
    how="left"
)

stacked_pct["pct"] = (
    stacked_pct["n_dosare"] / stacked_pct["total_an"] * 100
)

stacked_pct["label"] = stacked_pct.apply(
    lambda r: f"{r.pct:.1f}%",
    axis=1
)

fig_stacked_pct = px.bar(
    stacked_pct,
    x="An_solutie",
    y="pct",
    color="Solutie_grup",
    category_orders={
        "An_solutie": ani_completi,
        "Solutie_grup": top_solutions
    },
    text="label",
)

fig_stacked_pct.update_layout(
    barmode="stack",
    title="Structura procentuala a solutiilor pe ani",
    xaxis_title="An",
    yaxis_title="Procent din total",
    legend_title_text="Solutie",
    width=1800,
    height=500,
)

fig_stacked_pct.update_traces(textposition="inside")


with open("spatial_distribution_by_year.html", "w", encoding="utf-8") as f:
    f.write(fig.to_html(full_html=False, include_plotlyjs="cdn"))
    f.write("<hr>")
    f.write(fig_bar.to_html(full_html=False, include_plotlyjs=False))
    f.write("<hr>")
    f.write(fig_stacked.to_html(full_html=False, include_plotlyjs=False))
    f.write("<hr>")
    f.write(fig_stacked_pct.to_html(full_html=False, include_plotlyjs=False))
