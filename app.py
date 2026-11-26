import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path

st.set_page_config(page_title="Farmacias del Valle | Demanda", page_icon="💊", layout="wide")

@st.cache_data
def load_data():
    file_path = Path(__file__).parent / "Farmacias_Valle_Demanda_1200.csv"
    df = pd.read_csv(file_path)
    df.columns = [c.strip() for c in df.columns]
    for col in ["Precio_Promedio", "Ingreso_Mensual"]:
        df[col] = pd.to_numeric(df[col].astype(str).str.replace(r"[$,]", "", regex=True), errors="coerce")
    df["Mes"] = pd.to_datetime(df["Mes"], format="%Y-%m", errors="coerce")
    df["Promocion"] = df["Promocion"].map({0: "Sin promoción", 1: "Con promoción"}).fillna(df["Promocion"].astype(str))
    return df.dropna(subset=["Mes", "Ingreso_Mensual", "Unidades_Vendidas"])

df = load_data()
st.title("Farmacias del Valle | Ventas, demanda e inventario")
st.caption("Tablero de mando para apoyar decisiones comerciales y de abastecimiento · Datos mensuales 2020–2024")

# Sidebar filters
st.sidebar.header("Filtros")
min_date, max_date = df["Mes"].min().date(), df["Mes"].max().date()
default_start = max(pd.Timestamp("2024-01-01").date(), min_date)
default_end = max_date
date_range = st.sidebar.date_input("Periodo", value=(default_start, default_end), min_value=min_date, max_value=max_date)
if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date, end_date = min_date, max_date
categories = sorted(df["Categoria"].dropna().unique().tolist())
selected_categories = st.sidebar.multiselect("Categoría", categories, default=categories)
products = sorted(df.loc[df["Categoria"].isin(selected_categories), "Producto_Nombre"].dropna().unique().tolist())
selected_products = st.sidebar.multiselect("Producto", products, default=products)
promo_options = sorted(df["Promocion"].dropna().unique().tolist())
selected_promo = st.sidebar.multiselect("Promoción", promo_options, default=promo_options)

filtered = df[
    df["Mes"].dt.date.between(start_date, end_date)
    & df["Categoria"].isin(selected_categories)
    & df["Producto_Nombre"].isin(selected_products)
    & df["Promocion"].isin(selected_promo)
].copy()

# Equal-length previous period comparison, keeping category/product/promo filters.
period_days = max((end_date - start_date).days + 1, 1)
prev_end = pd.Timestamp(start_date) - pd.Timedelta(days=1)
prev_start = prev_end - pd.Timedelta(days=period_days - 1)
previous = df[
    df["Mes"].between(prev_start, prev_end)
    & df["Categoria"].isin(selected_categories)
    & df["Producto_Nombre"].isin(selected_products)
    & df["Promocion"].isin(selected_promo)
].copy()

def pct_change(current, prior):
    if prior is None or prior == 0 or pd.isna(prior):
        return None
    return (current / prior - 1) * 100

def delta_text(current, prior, fmt="{:+.1f}%"):
    change = pct_change(current, prior)
    return "Sin periodo comparable" if change is None else fmt.format(change) + " vs. periodo anterior"

if filtered.empty:
    st.warning("No hay registros con los filtros seleccionados. Amplía el periodo o selecciona otras categorías/productos.")
    st.stop()

revenue = filtered["Ingreso_Mensual"].sum()
units = filtered["Unidades_Vendidas"].sum()
avg_stock = filtered["Stock_Disponible"].mean()
prev_revenue = previous["Ingreso_Mensual"].sum() if not previous.empty else None
prev_units = previous["Unidades_Vendidas"].sum() if not previous.empty else None
prev_stock = previous["Stock_Disponible"].mean() if not previous.empty else None

st.subheader("Indicadores clave")
k1, k2, k3 = st.columns(3)
k1.metric("Ingresos acumulados", f"${revenue:,.0f}", delta_text(revenue, prev_revenue))
k2.metric("Unidades vendidas", f"{units:,.0f}", delta_text(units, prev_units))
k3.metric("Stock promedio registrado", f"{avg_stock:,.0f} unidades", delta_text(avg_stock, prev_stock))

st.caption(f"Periodo seleccionado: {start_date:%d/%m/%Y} – {end_date:%d/%m/%Y} · {len(filtered):,} registros · Comparación contra los {period_days} días inmediatamente anteriores.")
st.divider()

# Paleta visual: dos gráficas azules y dos verde-azuladas
AZUL = "#3478A8"
VERDE_AZULADO = "#269B8F"

# Estilo común para mantener consistencia visual
def polish_chart(fig, y_title="", x_title=""):
    fig.update_layout(
        template="plotly_white",
        title=dict(font=dict(size=17, color="#243746")),
        font=dict(family="Arial", size=12, color="#34495E"),
        margin=dict(l=15, r=15, t=55, b=35),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis_title=x_title,
        yaxis_title=y_title,
        hoverlabel=dict(bgcolor="white", font_size=12),
    )
    fig.update_xaxes(showgrid=True, gridcolor="#E9EFF3", zeroline=False)
    fig.update_yaxes(showgrid=False, zeroline=False)
    return fig

# Cuatro visualizaciones: 2 azules y 2 verde-azuladas
monthly = filtered.groupby("Mes", as_index=False).agg(
    Ingresos=("Ingreso_Mensual", "sum"),
    Unidades=("Unidades_Vendidas", "sum")
)
left, right = st.columns(2)

# 1. Tendencia mensual: azul
with left:
    fig = px.line(
        monthly, x="Mes", y="Ingresos",
        markers=True,
        title="Tendencia mensual de ingresos",
        color_discrete_sequence=[AZUL],
        custom_data=["Unidades"]
    )
    fig.update_traces(
        line=dict(width=3),
        marker=dict(size=7, color=AZUL, line=dict(width=1, color="white")),
        hovertemplate="<b>%{x|%b %Y}</b><br>Ingresos: $%{y:,.2f}<br>Unidades: %{customdata[0]:,.0f}<extra></extra>"
    )
    polish_chart(fig, y_title="Ingresos ($)")
    fig.update_yaxes(tickprefix="$", separatethousands=True)
    st.plotly_chart(fig, use_container_width=True)

# 2. Ingresos por categoría: verde-azulado
with right:
    cat = filtered.groupby("Categoria", as_index=False).agg(
        Ingresos=("Ingreso_Mensual", "sum")
    ).sort_values("Ingresos", ascending=True)
    fig = px.bar(
        cat, x="Ingresos", y="Categoria", orientation="h",
        text="Ingresos",
        title="Ingresos por categoría",
        color_discrete_sequence=[VERDE_AZULADO]
    )
    fig.update_traces(
        texttemplate="$%{x:,.0f}",
        textposition="outside",
        cliponaxis=False,
        marker_line_width=0,
        hovertemplate="<b>%{y}</b><br>Ingresos: $%{x:,.2f}<extra></extra>"
    )
    polish_chart(fig, x_title="Ingresos ($)")
    fig.update_xaxes(tickprefix="$", separatethousands=True)
    st.plotly_chart(fig, use_container_width=True)

left, right = st.columns(2)

# 3. Top 10 productos: verde-azulado
with left:
    prod = filtered.groupby("Producto_Nombre", as_index=False).agg(
        Unidades=("Unidades_Vendidas", "sum")
    )
    prod = prod.nlargest(10, "Unidades").sort_values("Unidades", ascending=True)
    fig = px.bar(
        prod, x="Unidades", y="Producto_Nombre", orientation="h",
        text="Unidades",
        title="Top 10 productos por unidades vendidas",
        color_discrete_sequence=[VERDE_AZULADO]
    )
    fig.update_traces(
        texttemplate="%{x:,.0f}",
        textposition="outside",
        cliponaxis=False,
        marker_line_width=0,
        hovertemplate="<b>%{y}</b><br>Unidades vendidas: %{x:,.0f}<extra></extra>"
    )
    polish_chart(fig, x_title="Unidades vendidas")
    fig.update_xaxes(separatethousands=True)
    st.plotly_chart(fig, use_container_width=True)

# 4. Distribución del inventario por categoría: azul
# El diagrama de caja permite comparar mediana, dispersión y valores atípicos
# sin saturar la visualización con todos los registros individuales.
with right:
    fig = px.box(
        filtered,
        x="Categoria",
        y="Stock_Disponible",
        points="outliers",
        title="Distribución del stock por categoría",
        color_discrete_sequence=[AZUL]
    )
    fig.update_traces(
        marker=dict(color=AZUL, size=4, opacity=0.55),
        line=dict(color=AZUL, width=2),
        fillcolor="rgba(52,120,168,0.25)",
        hovertemplate="<b>%{x}</b><br>Stock: %{y:,.0f} unidades<extra></extra>"
    )
    polish_chart(fig, y_title="Stock disponible (unidades)")
    fig.update_yaxes(separatethousands=True)
    fig.update_xaxes(showgrid=False, tickangle=-15)
    st.plotly_chart(fig, use_container_width=True)

# Storytelling notes
cat_rev = filtered.groupby("Categoria")["Ingreso_Mensual"].sum().sort_values(ascending=False)
top_cat = cat_rev.index[0]
top_share = cat_rev.iloc[0] / cat_rev.sum() * 100
top_product = filtered.groupby("Producto_Nombre")["Unidades_Vendidas"].sum().idxmax()
st.info(
    f"**Lectura del periodo:** la categoría con mayor contribución a ingresos es **{top_cat}** "
    f"({top_share:.1f}% del total filtrado). El producto con más unidades vendidas es **{top_product}**. "
    "Usa los filtros para comprobar si el patrón se mantiene por temporada, categoría o producto."
)

st.subheader("Detalle para consulta")
detail = filtered.groupby(["Categoria", "Producto_Nombre"], as_index=False).agg(
    Unidades=("Unidades_Vendidas", "sum"),
    Ingresos=("Ingreso_Mensual", "sum"),
    Precio_promedio=("Precio_Promedio", "mean"),
    Stock_promedio=("Stock_Disponible", "mean"),
    Meses_observados=("Mes", "nunique")
).sort_values("Ingresos", ascending=False)
st.dataframe(detail, use_container_width=True, hide_index=True)

st.caption("Nota metodológica: los ingresos se suman para el periodo; el stock se presenta como promedio de los registros mensuales, no como inventario total. La base no contiene metas comerciales, costos, márgenes, pedidos, faltantes ni identificación de sucursales.")
