"""
Análisis de Inventario con Alertas
Dashboard interactivo que detecta productos por agotarse, calcula cuándo
reabastecer y mide el capital "congelado" en inventario.
Ejecutar: streamlit run inventario.py
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
from datetime import datetime

# ============================================================
# CONFIGURACIÓN
# ============================================================
st.set_page_config(
    page_title="Análisis de Inventario",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# TOKENS DE DISEÑO
# ============================================================
INK         = "#0E1218"
SURFACE     = "#171C24"
SURFACE_2   = "#1F2530"
BORDER      = "#2A3140"
RULE        = "#3A4258"
CREAM       = "#F2EDE3"
COOL        = "#9AA3B5"
MUTED       = "#5A6478"

AMBER       = "#D4A574"
AMBER_HI    = "#E8C9A0"
AMBER_DIM   = "#8B6E47"
AMBER_FILL  = "rgba(212, 165, 116, 0.08)"

# Semáforo de alertas
RED         = "#C26B5E"   # crítico / agotado
YELLOW      = "#D4A574"   # alerta / bajo
GREEN       = "#7A9B7E"   # saludable
BLUE        = "#7088A8"   # exceso

CHART_PALETTE = [
    "#D4A574", "#9AA3B5", "#E8C9A0", "#7088A8",
    "#A88555", "#B0A084", "#5A7088", "#F2EDE3",
]

COLUMN_PATTERNS = {
    'sku':           ['sku', 'codigo', 'clave', 'id_producto', 'product_id', 'item_code'],
    'producto':      ['producto', 'product', 'item', 'product_name',
                      'nombre_producto', 'descripcion', 'nombre', 'articulo'],
    'categoria':     ['categoria', 'category', 'tipo', 'type', 'grupo', 'familia'],
    'proveedor':     ['proveedor', 'supplier', 'vendor', 'distribuidor'],
    'stock_actual':  ['stock_actual', 'stock', 'existencia', 'inventario',
                      'cantidad_disponible', 'on_hand', 'qty', 'cantidad'],
    'stock_minimo':  ['stock_minimo', 'minimo', 'min', 'punto_reorden',
                      'reorder_point', 'safety_stock'],
    'stock_maximo':  ['stock_maximo', 'maximo', 'max', 'capacidad'],
    'costo_unitario':['costo_unitario', 'costo', 'cost', 'precio_compra',
                      'unit_cost', 'precio_costo'],
    'precio_venta':  ['precio_venta', 'precio', 'price', 'sale_price',
                      'precio_publico'],
    'consumo_diario_promedio': ['consumo_diario_promedio', 'consumo_diario',
                                'consumo', 'venta_diaria', 'demanda_diaria',
                                'avg_daily_sales'],
    'tiempo_entrega_dias':     ['tiempo_entrega_dias', 'tiempo_entrega',
                                'lead_time', 'lead_time_dias', 'dias_entrega'],
    'ultima_entrada':          ['ultima_entrada', 'last_in', 'fecha_compra'],
    'ultima_venta':            ['ultima_venta', 'last_sale', 'fecha_ultima_venta'],
}


def detect_columns(df):
    detected = {}
    cols_normalized = {c.lower().strip().replace(' ', '_'): c for c in df.columns}
    for target, patterns in COLUMN_PATTERNS.items():
        for pattern in patterns:
            if pattern in cols_normalized:
                detected[target] = cols_normalized[pattern]
                break
    return detected


def prepare_dataframe(df, mapping):
    rename_map = {v: k for k, v in mapping.items() if v in df.columns}
    df = df.rename(columns=rename_map)

    # Tipos numéricos
    for col in ['stock_actual', 'stock_minimo', 'stock_maximo',
                'costo_unitario', 'precio_venta',
                'consumo_diario_promedio', 'tiempo_entrega_dias']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # Fechas
    for col in ['ultima_entrada', 'ultima_venta']:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')

    # Defaults razonables si faltan campos
    if 'costo_unitario' not in df.columns:
        df['costo_unitario'] = 0
    if 'stock_actual' not in df.columns:
        df['stock_actual'] = 0
    if 'stock_minimo' not in df.columns:
        df['stock_minimo'] = 0

    # Capital congelado
    df['capital_inmovilizado'] = df['stock_actual'].fillna(0) * df['costo_unitario'].fillna(0)

    # Margen
    if 'precio_venta' in df.columns:
        df['margen_unitario'] = df['precio_venta'].fillna(0) - df['costo_unitario'].fillna(0)
        df['valor_venta_potencial'] = df['stock_actual'].fillna(0) * df['precio_venta'].fillna(0)

    # Días estimados hasta agotamiento
    if 'consumo_diario_promedio' in df.columns:
        df['dias_hasta_agotar'] = df.apply(
            lambda r: round(r['stock_actual'] / r['consumo_diario_promedio'], 1)
            if pd.notna(r.get('consumo_diario_promedio')) and r.get('consumo_diario_promedio', 0) > 0
            else None,
            axis=1
        )

    # Clasificación de estado
    def clasificar(row):
        stock = row.get('stock_actual', 0) or 0
        minimo = row.get('stock_minimo', 0) or 0
        maximo = row.get('stock_maximo', None)
        if stock <= 0:
            return 'Agotado'
        if stock < minimo * 0.5:
            return 'Crítico'
        if stock < minimo:
            return 'Bajo'
        if maximo and stock > maximo:
            return 'Exceso'
        return 'Saludable'

    df['estado'] = df.apply(clasificar, axis=1)

    # Cantidad sugerida a reabastecer (hasta el máximo, o 2x mínimo si no hay máximo)
    def sugerir_pedido(row):
        if row['estado'] not in ['Agotado', 'Crítico', 'Bajo']:
            return 0
        maximo = row.get('stock_maximo')
        if pd.notna(maximo) and maximo > 0:
            return max(0, int(maximo - row.get('stock_actual', 0)))
        minimo = row.get('stock_minimo', 0) or 0
        return max(0, int(minimo * 2 - row.get('stock_actual', 0)))

    df['pedido_sugerido'] = df.apply(sugerir_pedido, axis=1)

    return df


# ============================================================
# ESTILOS — mismo lenguaje visual del Proyecto 1
# ============================================================
st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght,SOFT@9..144,300..700,0..100&family=DM+Sans:wght@400;500;600&family=JetBrains+Mono:wght@400;500;600&display=swap');

    html, body, [class*="css"], .stApp {{
        font-family: 'DM Sans', sans-serif;
        background-color: {INK};
        color: {CREAM};
    }}

    #MainMenu, footer {{visibility: hidden;}}

    .block-container {{
        padding-top: 2.5rem;
        padding-bottom: 3rem;
        max-width: 1340px;
    }}

    [data-testid="stSidebar"] > div:first-child {{
        background-color: {SURFACE};
        padding-top: 2rem;
    }}

    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] div {{
        color: {CREAM};
    }}

    [data-testid="stSidebar"] label {{
        font-family: 'DM Sans', sans-serif !important;
        font-size: 0.7rem !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        letter-spacing: 1.2px !important;
        color: {MUTED} !important;
    }}

    .meta-bar {{
        display: flex;
        gap: 3rem;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.72rem;
        color: {MUTED};
        text-transform: uppercase;
        letter-spacing: 1.5px;
        padding: 1rem 0;
        border-top: 1px solid {BORDER};
        border-bottom: 1px solid {BORDER};
        margin: 2rem 0;
    }}

    .meta-bar strong {{ color: {CREAM}; font-weight: 500; }}

    .upload-card {{
        background: {SURFACE};
        border: 1px solid {BORDER};
        border-radius: 8px;
        padding: 2.5rem;
        margin: 1rem 0 2rem 0;
    }}

    .upload-card-header {{
        display: flex; align-items: baseline; gap: 1rem;
        margin-bottom: 1.5rem;
    }}

    .upload-card-id {{
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.7rem; color: {AMBER};
        letter-spacing: 2px; text-transform: uppercase;
    }}

    .upload-card-divider {{ flex: 1; height: 1px; background: {BORDER}; }}

    .upload-card-title {{
        font-family: 'Fraunces', serif;
        font-weight: 500; font-size: 1.5rem;
        color: {CREAM}; margin: 0 0 0.5rem 0; line-height: 1.2;
    }}

    .upload-card-text {{
        font-family: 'DM Sans', sans-serif;
        font-size: 0.9rem; color: {COOL};
        margin: 0 0 1.5rem 0; max-width: 520px; line-height: 1.5;
    }}

    .kpi-grid {{
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 0;
        border-top: 1px solid {BORDER};
        border-bottom: 1px solid {BORDER};
        margin: 2rem 0;
    }}

    .kpi-cell {{
        padding: 1.75rem 1.5rem 1.75rem 0;
        border-right: 1px solid {BORDER};
    }}

    .kpi-cell:first-child {{ padding-left: 0; }}
    .kpi-cell:last-child {{ border-right: none; padding-right: 0; }}
    .kpi-cell-padded {{ padding-left: 1.5rem; }}

    .kpi-label {{
        font-family: 'DM Sans', sans-serif;
        font-size: 0.65rem; font-weight: 600;
        text-transform: uppercase; letter-spacing: 2px;
        color: {MUTED}; margin: 0 0 0.75rem 0;
    }}

    .kpi-number {{
        font-family: 'Fraunces', serif;
        font-weight: 400; font-size: 2.5rem;
        line-height: 1; letter-spacing: -1.5px;
        color: {CREAM}; margin: 0;
        font-feature-settings: 'tnum';
    }}

    .kpi-unit {{
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.7rem; color: {MUTED};
        text-transform: uppercase; letter-spacing: 1.5px;
        margin: 0.75rem 0 0 0;
        display: flex; align-items: center; gap: 6px;
    }}

    .kpi-tick {{
        display: inline-block; width: 8px; height: 1px;
        background: {AMBER};
    }}

    .section-block {{
        margin: 3rem 0 1.5rem 0;
        padding-top: 2rem;
        border-top: 1px solid {BORDER};
    }}

    .section-meta {{
        display: flex; align-items: baseline; gap: 1rem;
        margin-bottom: 0.5rem;
    }}

    .section-id {{
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.65rem; color: {AMBER};
        letter-spacing: 1.5px; text-transform: uppercase;
    }}

    .section-divider {{ flex: 1; height: 1px; background: {BORDER}; }}

    .section-headline {{
        font-family: 'Fraunces', serif;
        font-weight: 500; font-size: 1.75rem;
        line-height: 1.1; letter-spacing: -0.5px;
        color: {CREAM}; margin: 0.5rem 0 0 0;
    }}

    .section-deck {{
        font-family: 'DM Sans', sans-serif;
        font-size: 0.85rem; color: {COOL};
        margin: 0.5rem 0 0 0;
    }}

    /* Tarjetas de alerta */
    .alert-card {{
        background: {SURFACE};
        border: 1px solid {BORDER};
        border-left: 3px solid {AMBER};
        border-radius: 6px;
        padding: 1.25rem 1.5rem;
        margin-bottom: 0.75rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }}
    .alert-card.crit {{ border-left-color: {RED}; }}
    .alert-card.warn {{ border-left-color: {YELLOW}; }}
    .alert-card.over {{ border-left-color: {BLUE}; }}

    .alert-left {{ display: flex; flex-direction: column; gap: 0.25rem; }}
    .alert-sku {{
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.7rem; color: {MUTED};
        letter-spacing: 1.5px; text-transform: uppercase;
    }}
    .alert-product {{
        font-family: 'DM Sans', sans-serif;
        font-size: 1rem; font-weight: 500; color: {CREAM};
    }}
    .alert-note {{
        font-family: 'DM Sans', sans-serif;
        font-size: 0.8rem; color: {COOL};
    }}
    .alert-tag {{
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.7rem; padding: 0.3rem 0.7rem;
        border-radius: 999px;
        letter-spacing: 1.5px; text-transform: uppercase;
    }}
    .tag-crit {{ background: rgba(194, 107, 94, 0.15); color: {RED}; border: 1px solid {RED}; }}
    .tag-warn {{ background: rgba(212, 165, 116, 0.12); color: {AMBER}; border: 1px solid {AMBER_DIM}; }}
    .tag-over {{ background: rgba(112, 136, 168, 0.12); color: {BLUE}; border: 1px solid {BLUE}; }}

    .colophon {{
        margin-top: 4rem;
        padding-top: 1.5rem;
        border-top: 2px solid {RULE};
        display: flex; justify-content: space-between;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.7rem; color: {MUTED};
        text-transform: uppercase; letter-spacing: 1.5px;
    }}

    .stFileUploader > div {{
        background: {INK};
        border: 1px dashed {BORDER};
        border-radius: 4px;
    }}
    .stFileUploader > div:hover {{ border-color: {AMBER}; }}

    span[data-baseweb="tag"] {{
        background-color: {AMBER_DIM} !important;
        color: {CREAM} !important;
        border-radius: 2px !important;
    }}

    .stSelectbox > div > div,
    .stMultiSelect > div > div {{
        background-color: {INK} !important;
        border: 1px solid {BORDER} !important;
        border-radius: 4px !important;
        color: {CREAM} !important;
        font-family: 'JetBrains Mono', monospace !important;
    }}

    .streamlit-expanderHeader {{
        background-color: transparent !important;
        border: 1px solid {BORDER} !important;
        border-radius: 4px !important;
        font-family: 'DM Sans', sans-serif !important;
        font-size: 0.75rem !important;
        text-transform: uppercase !important;
        letter-spacing: 1.5px !important;
        color: {CREAM} !important;
    }}

    .stCheckbox label {{
        font-size: 0.85rem !important;
        text-transform: none !important;
        letter-spacing: normal !important;
        color: {CREAM} !important;
    }}
</style>
""", unsafe_allow_html=True)


# ============================================================
# PANEL LATERAL — encabezado
# ============================================================
with st.sidebar:
    st.markdown(f"""
    <div style="padding: 0 0 1rem 0; border-bottom: 1px solid {BORDER}; margin-bottom: 1rem;">
        <p style="font-family: 'JetBrains Mono', monospace; font-size: 0.65rem; color: {AMBER}; letter-spacing: 2px; text-transform: uppercase; margin: 0;">— Controles</p>
        <p style="font-family: 'Fraunces', serif; font-style: italic; font-size: 1.2rem; color: {CREAM}; margin: 0.3rem 0 0 0;">Configuración</p>
    </div>
    """, unsafe_allow_html=True)


# ============================================================
# CARGA DE DATOS
# ============================================================
df_raw = None
data_source = ""

st.markdown(f"""
<div class="upload-card">
    <div class="upload-card-header">
        <span class="upload-card-id">— FUENTE DE DATOS</span>
        <div class="upload-card-divider"></div>
    </div>
    <p class="upload-card-title">Cargar archivo de inventario</p>
    <p class="upload-card-text">
        Sube un Excel (.xlsx) o CSV con tu catálogo. El sistema detecta automáticamente
        columnas comunes (SKU, producto, stock actual, stock mínimo, costo, etc.) y
        calcula alertas, días hasta agotamiento y capital inmovilizado.
    </p>
</div>
""", unsafe_allow_html=True)

upload_col, demo_col = st.columns([2, 1])

with upload_col:
    uploaded_file = st.file_uploader(
        "Cargar archivo",
        type=['csv', 'xlsx', 'xls'],
        label_visibility="collapsed"
    )

with demo_col:
    use_demo = st.checkbox(
        "Usar datos de demostración",
        value=(uploaded_file is None),
        key="demo_check"
    )


def leer_archivo(file_or_path, nombre):
    if nombre.lower().endswith(('.xlsx', '.xls')):
        return pd.read_excel(file_or_path, sheet_name=0)
    return pd.read_csv(file_or_path)


if uploaded_file is not None and not use_demo:
    try:
        df_raw = leer_archivo(uploaded_file, uploaded_file.name)
        data_source = uploaded_file.name
    except Exception as e:
        st.error(f"Error al leer el archivo: {e}")
        st.stop()
elif use_demo and os.path.exists("inventario.xlsx"):
    df_raw = leer_archivo("inventario.xlsx", "inventario.xlsx")
    data_source = "inventario.xlsx · demostración"


if df_raw is None:
    st.markdown(f"""
    <div style="text-align: center; padding: 3rem 2rem; margin-top: 1rem;">
        <p style="font-family: 'JetBrains Mono', monospace; font-size: 0.7rem; color: {AMBER}; letter-spacing: 2px; text-transform: uppercase; margin: 0 0 1rem 0;">— ESPERANDO DATOS</p>
        <p style="font-family: 'Fraunces', serif; font-style: italic; font-size: 1.5rem; color: {COOL}; margin: 0;">Sube un archivo o activa el modo demostración para comenzar</p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()


# ============================================================
# MAPEO DE COLUMNAS
# ============================================================
detected = detect_columns(df_raw)

with st.sidebar:
    st.markdown(f"""
    <p style="font-family: 'DM Sans', sans-serif; font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 2px; color: {MUTED}; margin: 1rem 0 0.5rem 0;">— Mapeo de columnas</p>
    """, unsafe_allow_html=True)

    with st.expander("Ajustar mapeo", expanded=False):
        available_cols = ['(no disponible)'] + list(df_raw.columns)
        manual_mapping = {}

        required_fields = {
            'producto': 'Producto',
            'stock_actual': 'Stock actual',
            'stock_minimo': 'Stock mínimo',
        }
        optional_fields = {
            'sku': 'SKU',
            'categoria': 'Categoría',
            'proveedor': 'Proveedor',
            'stock_maximo': 'Stock máximo',
            'costo_unitario': 'Costo unitario',
            'precio_venta': 'Precio de venta',
            'consumo_diario_promedio': 'Consumo diario',
            'tiempo_entrega_dias': 'Tiempo de entrega (días)',
            'ultima_entrada': 'Última entrada',
            'ultima_venta': 'Última venta',
        }

        for key, label in {**required_fields, **optional_fields}.items():
            default_idx = available_cols.index(detected[key]) if key in detected else 0
            sel = st.selectbox(label, available_cols, index=default_idx, key=f"map_{key}")
            if sel != '(no disponible)':
                manual_mapping[key] = sel

required_min = {'producto', 'stock_actual', 'stock_minimo'}
if not required_min.issubset(manual_mapping.keys()):
    st.markdown(f"""
    <div style="text-align: center; padding: 3rem 2rem;">
        <p style="font-family: 'JetBrains Mono', monospace; font-size: 0.7rem; color: {AMBER}; letter-spacing: 2px; text-transform: uppercase; margin: 0 0 1rem 0;">— MAPEO INCOMPLETO</p>
        <p style="font-family: 'Fraunces', serif; font-style: italic; font-size: 1.5rem; color: {CREAM}; margin: 0 0 1rem 0;">Faltan columnas requeridas</p>
        <p style="font-family: 'DM Sans'; color: {COOL}; max-width: 480px; margin: 0 auto; line-height: 1.6;">
            Para procesar el archivo necesitamos al menos: Producto, Stock actual y Stock mínimo.
            Abre el panel lateral y ajusta el mapeo.
        </p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

df = prepare_dataframe(df_raw, manual_mapping)


# ============================================================
# FILTROS
# ============================================================
with st.sidebar:
    st.markdown(f"""
    <div style="margin: 1.5rem 0 0.5rem 0; padding-top: 1.5rem; border-top: 1px solid {BORDER};">
    <p style="font-family: 'DM Sans', sans-serif; font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 2px; color: {MUTED}; margin: 0;">— Filtros</p>
    </div>
    """, unsafe_allow_html=True)

    categorias = None
    if 'categoria' in df.columns:
        categorias = st.multiselect(
            "Categorías",
            options=sorted(df['categoria'].dropna().unique()),
            default=sorted(df['categoria'].dropna().unique())
        )

    proveedores = None
    if 'proveedor' in df.columns:
        proveedores = st.multiselect(
            "Proveedores",
            options=sorted(df['proveedor'].dropna().unique()),
            default=sorted(df['proveedor'].dropna().unique())
        )

    estados_disponibles = ['Agotado', 'Crítico', 'Bajo', 'Saludable', 'Exceso']
    estados_sel = st.multiselect(
        "Estado",
        options=estados_disponibles,
        default=estados_disponibles
    )

df_f = df.copy()
if categorias is not None:
    df_f = df_f[df_f['categoria'].isin(categorias)]
if proveedores is not None:
    df_f = df_f[df_f['proveedor'].isin(proveedores)]
df_f = df_f[df_f['estado'].isin(estados_sel)]


# ============================================================
# BARRA DE INFORMACIÓN
# ============================================================
issue_date = datetime.now().strftime('%d %b %Y').upper()
meses_es = {'JAN':'ENE','FEB':'FEB','MAR':'MAR','APR':'ABR','MAY':'MAY','JUN':'JUN',
            'JUL':'JUL','AUG':'AGO','SEP':'SEP','OCT':'OCT','NOV':'NOV','DEC':'DIC'}
for en, es in meses_es.items():
    issue_date = issue_date.replace(en, es)

num_skus = len(df_f)
num_alertas = (df_f['estado'].isin(['Agotado', 'Crítico', 'Bajo'])).sum()

st.markdown(f"""
<div class="meta-bar">
    <div>EMITIDO &nbsp;·&nbsp; <strong>{issue_date}</strong></div>
    <div>SKUS ANALIZADOS &nbsp;·&nbsp; <strong>{num_skus}</strong></div>
    <div>ALERTAS ACTIVAS &nbsp;·&nbsp; <strong>{num_alertas}</strong></div>
    <div>FUENTE &nbsp;·&nbsp; <strong>{data_source}</strong></div>
</div>
""", unsafe_allow_html=True)


# ============================================================
# INDICADORES PRINCIPALES (KPI)
# ============================================================
capital_total = df_f['capital_inmovilizado'].sum()
num_agotados = (df_f['estado'] == 'Agotado').sum()
num_criticos = (df_f['estado'].isin(['Crítico', 'Bajo'])).sum()
capital_exceso = df_f.loc[df_f['estado'] == 'Exceso', 'capital_inmovilizado'].sum()

st.markdown(f"""
<div class="kpi-grid">
    <div class="kpi-cell">
        <p class="kpi-label">Capital inmovilizado</p>
        <p class="kpi-number">${capital_total:,.0f}</p>
        <p class="kpi-unit"><span class="kpi-tick"></span> Pesos en inventario</p>
    </div>
    <div class="kpi-cell kpi-cell-padded">
        <p class="kpi-label">Productos agotados</p>
        <p class="kpi-number">{num_agotados}</p>
        <p class="kpi-unit"><span class="kpi-tick"></span> Sin existencia</p>
    </div>
    <div class="kpi-cell kpi-cell-padded">
        <p class="kpi-label">En alerta</p>
        <p class="kpi-number">{num_criticos}</p>
        <p class="kpi-unit"><span class="kpi-tick"></span> Bajo punto de reorden</p>
    </div>
    <div class="kpi-cell kpi-cell-padded">
        <p class="kpi-label">Capital en exceso</p>
        <p class="kpi-number">${capital_exceso:,.0f}</p>
        <p class="kpi-unit"><span class="kpi-tick"></span> Sobre-stock</p>
    </div>
</div>
""", unsafe_allow_html=True)


# ============================================================
# UTILIDADES DE GRÁFICA
# ============================================================
def apply_chart_style(fig, height=380):
    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(family="DM Sans, sans-serif", color=CREAM, size=12),
        height=height,
        margin=dict(l=10, r=10, t=20, b=10),
        xaxis=dict(
            gridcolor=BORDER, zerolinecolor=BORDER,
            tickfont=dict(color=COOL, size=10, family="JetBrains Mono, monospace"),
            linecolor=BORDER, showgrid=False
        ),
        yaxis=dict(
            gridcolor=BORDER, zerolinecolor=BORDER,
            tickfont=dict(color=COOL, size=10, family="JetBrains Mono, monospace"),
            linecolor=BORDER, showgrid=True, gridwidth=1
        ),
        legend=dict(font=dict(color=CREAM, size=11, family="DM Sans, sans-serif"), bgcolor='rgba(0,0,0,0)'),
        hoverlabel=dict(bgcolor=SURFACE_2, bordercolor=BORDER,
                        font=dict(color=CREAM, family="JetBrains Mono, monospace", size=11))
    )
    return fig


def section_header(section_id, title, subtitle):
    st.markdown(f"""
    <div class="section-block">
        <div class="section-meta">
            <span class="section-id">— {section_id}</span>
            <div class="section-divider"></div>
        </div>
        <p class="section-headline">{title}</p>
        <p class="section-deck">{subtitle}</p>
    </div>
    """, unsafe_allow_html=True)


# ============================================================
# SECCIÓN 01 — ALERTAS ACCIONABLES
# ============================================================
section_header("ALERTAS 01 / ACCIÓN INMEDIATA",
               "Productos que requieren atención",
               "Agotados y críticos primero. Toca para ver el detalle y el pedido sugerido.")

alertas_df = df_f[df_f['estado'].isin(['Agotado', 'Crítico', 'Bajo'])].copy()
orden_estado = {'Agotado': 0, 'Crítico': 1, 'Bajo': 2}
alertas_df['orden'] = alertas_df['estado'].map(orden_estado)
alertas_df = alertas_df.sort_values(['orden', 'pedido_sugerido'], ascending=[True, False])

if len(alertas_df) == 0:
    st.markdown(f"""
    <div style="text-align: center; padding: 2rem; border: 1px dashed {BORDER}; border-radius: 6px;">
        <p style="font-family: 'Fraunces', serif; font-style: italic; font-size: 1.2rem; color: {GREEN}; margin: 0;">
            Sin alertas activas. Todo el inventario está dentro de rangos saludables.
        </p>
    </div>
    """, unsafe_allow_html=True)
else:
    for _, r in alertas_df.head(15).iterrows():
        estado = r['estado']
        if estado == 'Agotado':
            cls, tag_cls = 'crit', 'tag-crit'
            nota = "Producto fuera de inventario — perdiendo ventas"
        elif estado == 'Crítico':
            cls, tag_cls = 'crit', 'tag-crit'
            dias = r.get('dias_hasta_agotar')
            nota = f"Quedan {int(r['stock_actual'])} unidades · {dias} días estimados antes de agotar" if pd.notna(dias) else f"Quedan {int(r['stock_actual'])} unidades"
        else:
            cls, tag_cls = 'warn', 'tag-warn'
            dias = r.get('dias_hasta_agotar')
            nota = f"Stock {int(r['stock_actual'])} bajo el mínimo de {int(r['stock_minimo'])}" + (f" · {dias} días para agotar" if pd.notna(dias) else "")

        sku_txt = r.get('sku', '—') if pd.notna(r.get('sku', None)) else '—'
        pedido = int(r['pedido_sugerido']) if r['pedido_sugerido'] > 0 else 0

        st.markdown(f"""
        <div class="alert-card {cls}">
            <div class="alert-left">
                <span class="alert-sku">{sku_txt} · {r.get('categoria', '')}</span>
                <span class="alert-product">{r['producto']}</span>
                <span class="alert-note">{nota}</span>
            </div>
            <div style="text-align: right;">
                <span class="alert-tag {tag_cls}">{estado}</span>
                <p style="font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; color: {COOL}; margin: 0.5rem 0 0 0;">
                    Pedido sugerido: <strong style="color: {CREAM};">{pedido} u.</strong>
                </p>
            </div>
        </div>
        """, unsafe_allow_html=True)

    if len(alertas_df) > 15:
        st.markdown(f"""<p style="font-family: 'JetBrains Mono', monospace; font-size: 0.7rem; color: {MUTED}; text-align: center; margin-top: 1rem; letter-spacing: 1.5px;">+ {len(alertas_df) - 15} alertas adicionales en la tabla detallada</p>""", unsafe_allow_html=True)


# ============================================================
# SECCIÓN 02 — DISTRIBUCIÓN DE ESTADOS
# ============================================================
section_header("GRÁFICA 02 / DISTRIBUCIÓN",
               "Salud general del inventario",
               "Distribución de productos por estado y capital atrapado en cada nivel.")

col_a, col_b = st.columns(2, gap="large")

with col_a:
    st.markdown(f"""<p style="font-family: 'DM Sans'; font-size: 0.65rem; font-weight: 600; text-transform: uppercase; letter-spacing: 2px; color: {AMBER}; margin: 0.5rem 0 0.5rem 0;">— PRODUCTOS POR ESTADO</p>""", unsafe_allow_html=True)
    color_map_estado = {
        'Agotado': RED, 'Crítico': RED, 'Bajo': YELLOW,
        'Saludable': GREEN, 'Exceso': BLUE
    }
    estados_count = df_f['estado'].value_counts().reindex(
        ['Agotado', 'Crítico', 'Bajo', 'Saludable', 'Exceso']
    ).fillna(0)

    fig1 = go.Figure()
    fig1.add_trace(go.Bar(
        x=estados_count.values, y=estados_count.index,
        orientation='h',
        marker=dict(color=[color_map_estado[e] for e in estados_count.index],
                    line=dict(width=0)),
        text=[int(v) for v in estados_count.values],
        textposition='outside',
        textfont=dict(color=CREAM, family="JetBrains Mono, monospace"),
        hovertemplate='<b>%{y}</b><br>%{x} productos<extra></extra>'
    ))
    fig1 = apply_chart_style(fig1, height=320)
    fig1.update_layout(
        yaxis=dict(showgrid=False, tickfont=dict(color=CREAM, size=11, family="DM Sans, sans-serif")),
        xaxis=dict(showgrid=True, gridcolor=BORDER, gridwidth=1)
    )
    st.plotly_chart(fig1, use_container_width=True)

with col_b:
    st.markdown(f"""<p style="font-family: 'DM Sans'; font-size: 0.65rem; font-weight: 600; text-transform: uppercase; letter-spacing: 2px; color: {AMBER}; margin: 0.5rem 0 0.5rem 0;">— CAPITAL POR ESTADO</p>""", unsafe_allow_html=True)
    cap_estado = df_f.groupby('estado')['capital_inmovilizado'].sum().reindex(
        ['Agotado', 'Crítico', 'Bajo', 'Saludable', 'Exceso']
    ).fillna(0)

    fig2 = go.Figure()
    fig2.add_trace(go.Pie(
        labels=cap_estado.index, values=cap_estado.values,
        hole=0.72,
        marker=dict(colors=[color_map_estado[e] for e in cap_estado.index],
                    line=dict(color=INK, width=2)),
        textfont=dict(color=CREAM, size=10, family="JetBrains Mono, monospace"),
        textinfo='percent',
        hovertemplate='<b>%{label}</b><br>$%{value:,.0f}<br>%{percent}<extra></extra>'
    ))
    fig2 = apply_chart_style(fig2, height=320)
    fig2.update_layout(
        showlegend=True,
        legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.05, font=dict(size=10))
    )
    st.plotly_chart(fig2, use_container_width=True)


# ============================================================
# SECCIÓN 03 — TOP CAPITAL INMOVILIZADO
# ============================================================
section_header("GRÁFICA 03 / RANKING",
               "Productos con mayor capital congelado",
               "Dónde está atrapado tu dinero. Reduce el sobre-stock en los primeros lugares.")

top_capital = df_f.nlargest(10, 'capital_inmovilizado')[['producto', 'capital_inmovilizado', 'estado']]

fig3 = go.Figure()
colors_top = [color_map_estado.get(e, AMBER) for e in top_capital['estado']]
fig3.add_trace(go.Bar(
    x=top_capital['capital_inmovilizado'], y=top_capital['producto'],
    orientation='h',
    marker=dict(color=colors_top, line=dict(width=0)),
    hovertemplate='<b>%{y}</b><br>$%{x:,.0f}<extra></extra>'
))
fig3 = apply_chart_style(fig3, height=400)
fig3.update_layout(
    yaxis=dict(categoryorder='total ascending', showgrid=False,
               tickfont=dict(color=CREAM, size=11, family="DM Sans, sans-serif")),
    xaxis=dict(showgrid=True, gridcolor=BORDER, gridwidth=1)
)
st.plotly_chart(fig3, use_container_width=True)


# ============================================================
# SECCIÓN 04 — DÍAS HASTA AGOTAMIENTO
# ============================================================
if 'dias_hasta_agotar' in df_f.columns and df_f['dias_hasta_agotar'].notna().any():
    section_header("GRÁFICA 04 / RIESGO",
                   "Productos próximos a agotarse",
                   "Días estimados de inventario restante según consumo promedio.")

    riesgo = df_f[df_f['dias_hasta_agotar'].notna() & (df_f['stock_actual'] > 0)].copy()
    riesgo = riesgo.nsmallest(12, 'dias_hasta_agotar')[['producto', 'dias_hasta_agotar', 'estado']]

    fig4 = go.Figure()
    colors_riesgo = [color_map_estado.get(e, AMBER) for e in riesgo['estado']]
    fig4.add_trace(go.Bar(
        x=riesgo['dias_hasta_agotar'], y=riesgo['producto'],
        orientation='h',
        marker=dict(color=colors_riesgo, line=dict(width=0)),
        text=[f"{v:.1f} d" for v in riesgo['dias_hasta_agotar']],
        textposition='outside',
        textfont=dict(color=CREAM, family="JetBrains Mono, monospace", size=10),
        hovertemplate='<b>%{y}</b><br>%{x:.1f} días<extra></extra>'
    ))
    fig4 = apply_chart_style(fig4, height=440)
    fig4.update_layout(
        yaxis=dict(categoryorder='total descending', showgrid=False,
                   tickfont=dict(color=CREAM, size=11, family="DM Sans, sans-serif")),
        xaxis=dict(title="Días de stock restante", showgrid=True, gridcolor=BORDER, gridwidth=1,
                   title_font=dict(size=10, color=MUTED))
    )
    st.plotly_chart(fig4, use_container_width=True)


# ============================================================
# SECCIÓN 05 — CAPITAL POR CATEGORÍA
# ============================================================
if 'categoria' in df_f.columns and df_f['categoria'].notna().any():
    section_header("GRÁFICA 05 / CATEGORÍAS",
                   "Capital inmovilizado por categoría",
                   "Distribución del dinero atado en cada familia de productos.")

    cap_cat = df_f.groupby('categoria')['capital_inmovilizado'].sum().reset_index().sort_values('capital_inmovilizado', ascending=True)

    fig5 = go.Figure()
    fig5.add_trace(go.Bar(
        x=cap_cat['capital_inmovilizado'], y=cap_cat['categoria'],
        orientation='h',
        marker=dict(color=AMBER, line=dict(width=0)),
        hovertemplate='<b>%{y}</b><br>$%{x:,.0f}<extra></extra>'
    ))
    fig5 = apply_chart_style(fig5, height=320)
    fig5.update_layout(
        yaxis=dict(showgrid=False, tickfont=dict(color=CREAM, size=11, family="DM Sans, sans-serif")),
        xaxis=dict(showgrid=True, gridcolor=BORDER, gridwidth=1)
    )
    st.plotly_chart(fig5, use_container_width=True)


# ============================================================
# TABLA DETALLADA
# ============================================================
st.markdown(f"""
<div class="section-block">
    <div class="section-meta">
        <span class="section-id">— ANEXO / INVENTARIO COMPLETO</span>
        <div class="section-divider"></div>
    </div>
    <p class="section-headline">Catálogo detallado</p>
    <p class="section-deck">Inventario completo con estado, alertas y pedido sugerido. Exportable a CSV.</p>
</div>
""", unsafe_allow_html=True)

cols_tabla = [c for c in [
    'sku', 'producto', 'categoria', 'proveedor',
    'stock_actual', 'stock_minimo', 'stock_maximo',
    'dias_hasta_agotar', 'estado', 'pedido_sugerido',
    'costo_unitario', 'capital_inmovilizado'
] if c in df_f.columns]

with st.expander("Abrir tabla"):
    df_tabla = df_f[cols_tabla].sort_values(
        by=['estado', 'capital_inmovilizado'],
        key=lambda s: s.map({'Agotado': 0, 'Crítico': 1, 'Bajo': 2, 'Saludable': 3, 'Exceso': 4}) if s.name == 'estado' else s,
        ascending=[True, False]
    )
    st.dataframe(df_tabla, use_container_width=True, height=420)

    csv = df_tabla.to_csv(index=False).encode('utf-8')
    st.download_button("DESCARGAR CSV", csv, "inventario_analisis.csv", "text/csv")


# ============================================================
# PIE DE PÁGINA
# ============================================================
st.markdown(f"""
<div class="colophon">
    <div>ANÁLISIS DE INVENTARIO</div>
    <div>TIPOGRAFÍA · FRAUNCES & DM SANS</div>
    <div>DESARROLLADO CON PYTHON / STREAMLIT</div>
</div>
""", unsafe_allow_html=True)
