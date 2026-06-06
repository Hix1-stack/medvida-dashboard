import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import create_engine

# ── Configuración ─────────────────────────────────────────────
st.set_page_config(
    page_title="MedVida · Dashboard BI",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.metric-card {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    border-radius: 12px; padding: 20px; color: white;
    border-left: 4px solid #00d4ff; margin-bottom: 10px;
}
.metric-value { font-size: 2rem; font-weight: 700; color: #00d4ff; }
.metric-label { font-size: 0.85rem; opacity: 0.8; margin-top: 4px; }
</style>
""", unsafe_allow_html=True)

# ── Conexión ──────────────────────────────────────────────────
@st.cache_resource
def get_engine():
    DB_HOST = st.secrets["DB_HOST"]
    DB_PORT = int(st.secrets["DB_PORT"])
    DB_USER = st.secrets["DB_USER"]
    DB_PASS = st.secrets["DB_PASS"]
    SSL_ARGS = {'ssl': {'check_hostname': False, 'verify_mode': 0}}
    return create_engine(
        f'mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/clinica_dw',
        connect_args=SSL_ARGS
    )

@st.cache_data(ttl=300)
def cargar_datos():
    engine = get_engine()
    return pd.read_sql("""
        SELECT f.id_fact, f.id_venta_orig, f.metodo_pago, f.tipo_consulta,
               f.cantidad, f.precio_unitario, f.descuento, f.subtotal,
               f.costo_producto, f.margen,
               t.fecha, t.anio, t.mes, t.nombre_mes,
               t.nombre_dia, t.es_fin_semana,
               p.nombre_producto, p.categoria, p.rango_precio,
               c.nombre_completo, c.genero, c.grupo_edad, c.ciudad AS ciudad_pac,
               s.nombre_sucursal, s.tipo_sucursal
        FROM fact_ventas f
        JOIN dim_tiempo   t ON f.id_tiempo   = t.id_tiempo
        JOIN dim_producto p ON f.id_producto = p.id_producto
        JOIN dim_cliente  c ON f.id_cliente  = c.id_cliente
        JOIN dim_sucursal s ON f.id_sucursal = s.id_sucursal
    """, engine, parse_dates=['fecha'])

# ── Carga ─────────────────────────────────────────────────────
with st.spinner('Cargando datos...'):
    df = cargar_datos()

# ── Header ────────────────────────────────────────────────────
st.title("🏥 MedVida — Sistema de Soporte a Decisiones")
st.caption("Clínica MedVida · Análisis de Ventas y Operaciones · Nov 2024 – Abr 2025")
st.divider()

# ── Sidebar Filtros ───────────────────────────────────────────
with st.sidebar:
    st.title("🔎 Filtros")

    st.subheader("📅 Período")
    meses = sorted(df['fecha'].dt.to_period('M').unique().astype(str))
    mes_ini = st.selectbox("Desde", meses, index=0)
    mes_fin = st.selectbox("Hasta", meses, index=len(meses)-1)

    st.subheader("🏢 Sucursal")
    sucursales = ["Todas"] + sorted(df['nombre_sucursal'].unique().tolist())
    suc_sel = st.multiselect("Sucursal(es)", sucursales, default=["Todas"])

    st.subheader("💊 Categoría")
    cats = ["Todas"] + sorted(df['categoria'].unique().tolist())
    cat_sel = st.multiselect("Categoría(s)", cats, default=["Todas"])

    st.subheader("💳 Método de Pago")
    metodos = ["Todos"] + sorted(df['metodo_pago'].unique().tolist())
    met_sel = st.selectbox("Método", metodos)

# ── Filtros ───────────────────────────────────────────────────
mask = (
    (df['fecha'].dt.to_period('M').astype(str) >= mes_ini) &
    (df['fecha'].dt.to_period('M').astype(str) <= mes_fin)
)
if "Todas" not in suc_sel and suc_sel:
    mask &= df['nombre_sucursal'].isin(suc_sel)
if "Todas" not in cat_sel and cat_sel:
    mask &= df['categoria'].isin(cat_sel)
if met_sel != "Todos":
    mask &= df['metodo_pago'] == met_sel
dff = df[mask].copy()

if dff.empty:
    st.warning("⚠️ No hay datos con los filtros seleccionados.")
    st.stop()

# ── KPIs ──────────────────────────────────────────────────────
k1, k2, k3, k4, k5 = st.columns(5)
kpis = [
    (k1, "💰 Ingresos Totales",  f"${dff['subtotal'].sum():,.0f}"),
    (k2, "📈 Margen Bruto",      f"${dff['margen'].sum():,.0f}"),
    (k3, "🛒 Tickets de Venta",  f"{dff['id_venta_orig'].nunique():,}"),
    (k4, "👤 Pacientes Activos", f"{dff['nombre_completo'].nunique():,}"),
    (k5, "💊 Unidades Vendidas", f"{dff['cantidad'].sum():,}"),
]
for col, label, valor in kpis:
    with col:
        st.markdown(f"""
        <div class="metric-card">
            <div style="font-size:1rem;opacity:.8">{label}</div>
            <div class="metric-value">{valor}</div>
        </div>""", unsafe_allow_html=True)

st.divider()

# ── Fila 1: Evolución + Sucursales ────────────────────────────
c1, c2 = st.columns([3, 2])
with c1:
    st.subheader("📅 Evolución de Ingresos Mensuales")
    evol = (dff.groupby(['anio','mes','nombre_mes'])['subtotal']
               .sum().reset_index().sort_values(['anio','mes']))
    evol['periodo'] = evol['nombre_mes'].str[:3]+' '+evol['anio'].astype(str)
    fig = px.area(evol, x='periodo', y='subtotal',
                  labels={'periodo':'Mes','subtotal':'Ingresos ($)'},
                  color_discrete_sequence=['#00d4ff'])
    fig.update_layout(margin=dict(t=20,b=20))
    fig.update_yaxes(tickprefix='$', tickformat=',.0f')
    st.plotly_chart(fig, use_container_width=True)

with c2:
    st.subheader("🏢 Ingresos por Sucursal")
    suc = dff.groupby('nombre_sucursal')['subtotal'].sum().reset_index()
    fig = px.pie(suc, names='nombre_sucursal', values='subtotal',
                 hole=0.45, color_discrete_sequence=px.colors.sequential.Blues_r)
    fig.update_traces(textinfo='percent+label')
    fig.update_layout(margin=dict(t=20,b=20))
    st.plotly_chart(fig, use_container_width=True)

# ── Fila 2: Top productos + Categorías ───────────────────────
c3, c4 = st.columns([3, 2])
with c3:
    st.subheader("💊 Top 10 Productos por Ingreso")
    top = (dff.groupby('nombre_producto')['subtotal']
              .sum().nlargest(10).reset_index().sort_values('subtotal'))
    fig = px.bar(top, x='subtotal', y='nombre_producto', orientation='h',
                 color='subtotal', color_continuous_scale='Blues',
                 labels={'subtotal':'Ingresos ($)','nombre_producto':'Producto'})
    fig.update_layout(margin=dict(t=20,b=20), coloraxis_showscale=False)
    fig.update_xaxes(tickprefix='$', tickformat=',.0f')
    st.plotly_chart(fig, use_container_width=True)

with c4:
    st.subheader("📦 Ingresos por Categoría")
    cat = dff.groupby('categoria')['subtotal'].sum().reset_index().sort_values('subtotal')
    fig = px.bar(cat, x='subtotal', y='categoria', orientation='h',
                 color_discrete_sequence=['#0096c7'])
    fig.update_layout(margin=dict(t=20,b=20))
    fig.update_xaxes(tickprefix='$', tickformat=',.0f')
    st.plotly_chart(fig, use_container_width=True)

# ── Fila 3: Pago + Edad + Día semana ─────────────────────────
c5, c6, c7 = st.columns(3)
with c5:
    st.subheader("💳 Método de Pago")
    mp = dff.groupby('metodo_pago')['subtotal'].sum().reset_index()
    fig = px.pie(mp, names='metodo_pago', values='subtotal',
                 color_discrete_sequence=['#48cae4','#0096c7','#0077b6','#023e8a'])
    fig.update_layout(margin=dict(t=20,b=20))
    st.plotly_chart(fig, use_container_width=True)

with c6:
    st.subheader("👥 Pacientes por Grupo de Edad")
    edad = dff.groupby('grupo_edad')['nombre_completo'].nunique().reset_index()
    edad.columns = ['grupo_edad','n']
    fig = px.bar(edad, x='grupo_edad', y='n',
                 color='grupo_edad',
                 color_discrete_sequence=px.colors.sequential.Blues_r,
                 labels={'n':'# Pacientes','grupo_edad':'Grupo'})
    fig.update_layout(margin=dict(t=20,b=20), showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

with c7:
    st.subheader("📆 Ventas por Día de la Semana")
    dias = ['Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo']
    dia = dff.groupby('nombre_dia')['subtotal'].sum().reindex(dias).reset_index()
    fig = px.bar(dia, x='nombre_dia', y='subtotal',
                 color_discrete_sequence=['#00b4d8'])
    fig.update_layout(margin=dict(t=20,b=20))
    fig.update_yaxes(tickprefix='$', tickformat=',.0f')
    st.plotly_chart(fig, use_container_width=True)

# ── Mapa de calor ─────────────────────────────────────────────
st.divider()
st.subheader("🗓️ Mapa de Calor — Ingresos por Mes y Día")
pivot = dff.pivot_table(values='subtotal', index='nombre_dia',
                        columns='nombre_mes', aggfunc='sum', fill_value=0)
dias_ord  = [d for d in ['Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo'] if d in pivot.index]
meses_ord = [m for m in ['Noviembre','Diciembre','Enero','Febrero','Marzo','Abril'] if m in pivot.columns]
pivot = pivot.loc[dias_ord, meses_ord]
fig = px.imshow(pivot, color_continuous_scale='Blues',
                labels=dict(color='Ingresos ($)'), aspect='auto')
fig.update_layout(margin=dict(t=20,b=20))
st.plotly_chart(fig, use_container_width=True)

# ── Tabla detalle ─────────────────────────────────────────────
st.divider()
st.subheader("📋 Detalle de Ventas")
with st.expander("Ver tabla"):
    tabla = dff[['fecha','nombre_sucursal','nombre_producto','categoria',
                 'cantidad','precio_unitario','subtotal','margen',
                 'metodo_pago','nombre_completo','grupo_edad','ciudad_pac']].copy()
    tabla['fecha'] = tabla['fecha'].dt.strftime('%Y-%m-%d')
    tabla.columns = ['Fecha','Sucursal','Producto','Categoría','Cantidad',
                     'Precio','Subtotal','Margen','Pago','Paciente','Edad','Ciudad']
    st.dataframe(tabla, use_container_width=True, height=350)

st.caption("🏥 MedVida · Dashboard BI — Datos simulados con fines académicos")
