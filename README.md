# Análisis de Inventario con Alertas

> ### 🚀 Probar la app en vivo
>
> **https://inventario-alertas.streamlit.app**

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://inventario-alertas.streamlit.app)


Dashboard interactivo de control de inventario para tiendas y pequeños negocios. Detecta productos por agotarse, calcula cuándo reabastecer y mide el capital "congelado" en stock. Construido en Python con Streamlit y Plotly, acepta archivos Excel (.xlsx) o CSV con detección automática de columnas.

## Problema que resuelve

Los dueños de tienda suelen tener dos problemas opuestos al mismo tiempo:

1. **Productos agotados** → se pierden ventas que ya estaban garantizadas
2. **Sobre-stock** → hay dinero atrapado en productos que rotan lento

Este dashboard cruza el stock actual contra el mínimo, el consumo diario promedio y el tiempo de entrega del proveedor para responder tres preguntas concretas: *qué pedir, cuánto pedir y cuánto dinero tengo congelado*.

## Características

- **Carga de Excel o CSV** con detección automática de columnas (SKU, producto, stock, costo, etc.)
- **Mapeo manual** desde el panel lateral para archivos con nombres no estándar
- **Indicadores clave**: capital inmovilizado, productos agotados, productos en alerta, capital en exceso
- **Tarjetas de alerta accionables** ordenadas por prioridad (Agotado → Crítico → Bajo)
- **Pedido sugerido** por producto, calculado hasta el stock máximo o el doble del mínimo
- **Días estimados hasta agotamiento** según el consumo diario promedio
- **Análisis visual**:
  - Distribución de productos por estado (semáforo)
  - Capital congelado por estado
  - Top 10 productos con más dinero atrapado
  - Productos con menos días de stock restante
  - Capital por categoría
- **Filtros** por categoría, proveedor y estado
- **Exportación** del análisis filtrado a CSV
- **Diseño editorial** consistente con el resto del portafolio

## Tecnologías

- Python 3.10+
- Streamlit
- Pandas
- Plotly
- openpyxl (lectura de archivos Excel)

## Instalación local

```bash
git clone https://github.com/israel44moran/analisis-inventario.git
cd analisis-inventario
pip install -r requirements.txt
```

## Ejecución

Generar el archivo Excel de demostración:
```bash
python generar_datos.py
```

Lanzar el dashboard:
```bash
streamlit run inventario.py
```

El dashboard estará disponible en `http://localhost:8501`

## Estructura del proyecto

```
analisis-inventario/
├── inventario.py         # Aplicación principal de Streamlit
├── generar_datos.py      # Generador de datos de demostración (Excel)
├── inventario.xlsx       # Dataset de demostración (catálogo + movimientos)
├── requirements.txt      # Dependencias del proyecto
└── README.md
```

## Formato esperado del archivo

El archivo de entrada (Excel o CSV) debe contener una hoja con productos. El sistema detecta automáticamente columnas comunes en español e inglés:

| Campo | Nombres detectados | Requerido |
|-------|--------------------|-----------|
| Producto | producto, product, item, descripcion | Sí |
| Stock actual | stock_actual, stock, existencia, inventario, qty | Sí |
| Stock mínimo | stock_minimo, minimo, punto_reorden, reorder_point | Sí |
| SKU | sku, codigo, clave, id_producto | No |
| Categoría | categoria, category, tipo, familia | No |
| Proveedor | proveedor, supplier, vendor | No |
| Stock máximo | stock_maximo, maximo, capacidad | No |
| Costo unitario | costo_unitario, costo, precio_compra | No |
| Precio de venta | precio_venta, precio, sale_price | No |
| Consumo diario | consumo_diario_promedio, venta_diaria, demanda_diaria | No |
| Tiempo de entrega | tiempo_entrega_dias, lead_time | No |

Si las columnas tienen otros nombres, pueden ajustarse manualmente desde el panel lateral.

## Lógica de clasificación

Cada producto recibe automáticamente un estado:

- **Agotado** — Stock = 0
- **Crítico** — Stock < 50% del mínimo
- **Bajo** — Stock entre 50% y 100% del mínimo
- **Saludable** — Stock entre mínimo y máximo
- **Exceso** — Stock por encima del máximo

El **pedido sugerido** se calcula para llevar el stock hasta el máximo (si está definido) o hasta el doble del mínimo.

## Autor

Israel Morán
