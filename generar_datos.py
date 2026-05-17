"""
Generador de datos de inventario para una tienda de abarrotes / minisuper.
Crea un archivo Excel (.xlsx) con catálogo, stock actual, reglas de
reabastecimiento, precios y un historial corto de movimientos.
"""

import pandas as pd
import random
from datetime import datetime, timedelta

random.seed(42)

# ============================================================
# CATÁLOGO BASE
# ============================================================
catalogo = [
    # (sku, producto, categoria, proveedor, costo, precio_venta, lead_time_dias, consumo_diario_aprox)
    ("ABR-001", "Arroz 1kg",                "Abarrotes",  "Distribuidora La Merced",   28, 42, 4,  18),
    ("ABR-002", "Frijol negro 1kg",         "Abarrotes",  "Distribuidora La Merced",   34, 52, 4,  14),
    ("ABR-003", "Aceite vegetal 1L",        "Abarrotes",  "Distribuidora La Merced",   42, 65, 5,  12),
    ("ABR-004", "Azúcar 1kg",               "Abarrotes",  "Distribuidora La Merced",   24, 38, 4,  15),
    ("ABR-005", "Sal de mesa 1kg",          "Abarrotes",  "Distribuidora La Merced",   12, 22, 5,   6),
    ("ABR-006", "Atún en lata 140g",        "Abarrotes",  "Marca Propia SA",           18, 28, 6,  22),
    ("ABR-007", "Sopa instantánea Maruchan","Abarrotes",  "Marca Propia SA",           11, 18, 3,  35),
    ("ABR-008", "Pasta para sopa 200g",     "Abarrotes",  "Marca Propia SA",            8, 14, 4,  20),
    ("BEB-001", "Coca-Cola 600ml",          "Bebidas",    "Coca-Cola FEMSA",           14, 22, 2,  60),
    ("BEB-002", "Coca-Cola 2L",             "Bebidas",    "Coca-Cola FEMSA",           28, 42, 2,  18),
    ("BEB-003", "Agua Ciel 1L",             "Bebidas",    "Coca-Cola FEMSA",            9, 16, 2,  45),
    ("BEB-004", "Café soluble Nescafé 50g", "Bebidas",    "Nestlé Distribuidora",      52, 78, 7,   8),
    ("BEB-005", "Cerveza Corona 355ml",     "Bebidas",    "Cervecería Modelo",         18, 28, 3,  55),
    ("BEB-006", "Jugo del Valle 1L",        "Bebidas",    "Coca-Cola FEMSA",           22, 32, 3,  14),
    ("BOT-001", "Sabritas original 45g",    "Botanas",    "PepsiCo México",            16, 25, 2,  40),
    ("BOT-002", "Doritos nacho 62g",        "Botanas",    "PepsiCo México",            18, 28, 2,  32),
    ("BOT-003", "Galletas Marías 170g",     "Botanas",    "Marinela Distribuidora",    13, 22, 4,  18),
    ("BOT-004", "Cacahuates japoneses 100g","Botanas",    "Marca Propia SA",           11, 19, 5,  12),
    ("LAC-001", "Leche Lala entera 1L",     "Lácteos",    "Grupo Lala",                22, 32, 2,  38),
    ("LAC-002", "Yogurt natural 1kg",       "Lácteos",    "Grupo Lala",                38, 55, 2,  10),
    ("LAC-003", "Queso panela 400g",        "Lácteos",    "Grupo Lala",                62, 92, 3,   8),
    ("LAC-004", "Huevo San Juan 18 piezas", "Lácteos",    "Granja San Juan",           68, 92, 2,  22),
    ("PAN-001", "Pan Bimbo blanco grande",  "Panadería",  "Grupo Bimbo",               42, 58, 1,  18),
    ("PAN-002", "Tortillas de maíz 1kg",    "Panadería",  "Tortillería local",         18, 25, 1,  85),
    ("LIM-001", "Detergente Ariel 1kg",     "Limpieza",   "Procter & Gamble",          48, 72, 5,  12),
    ("LIM-002", "Papel higiénico 4 rollos", "Limpieza",   "Kimberly Clark",            38, 58, 4,  20),
    ("LIM-003", "Jabón Zote en barra",      "Limpieza",   "Fábrica de Jabón La Corona",12, 20, 6,  16),
    ("LIM-004", "Cloro Cloralex 1L",        "Limpieza",   "Alen del Norte",            22, 35, 5,   9),
    ("HIG-001", "Pasta dental Colgate",     "Higiene",    "Colgate-Palmolive",         28, 45, 6,   8),
    ("HIG-002", "Shampoo H&S 400ml",        "Higiene",    "Procter & Gamble",          58, 89, 7,   5),
    ("HIG-003", "Jabón de baño Palmolive",  "Higiene",    "Colgate-Palmolive",         10, 18, 6,  15),
]

hoy = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

# ============================================================
# CONSTRUCCIÓN DEL INVENTARIO
# ============================================================
inventario = []
for sku, producto, categoria, proveedor, costo, venta, lead, consumo in catalogo:
    # Stock mínimo: lo que se consume durante el tiempo de entrega + colchón de seguridad
    stock_minimo = int(consumo * lead * 1.3)
    # Stock máximo: lo que aguanta entre 2 y 3 semanas
    stock_maximo = int(consumo * random.randint(18, 28))

    # Simulamos distintos estados del inventario para que el dashboard sea interesante
    estado = random.choices(
        ["agotado", "critico", "bajo", "normal", "alto", "exceso"],
        weights=[3, 12, 18, 45, 15, 7]
    )[0]

    if estado == "agotado":
        stock_actual = 0
    elif estado == "critico":
        stock_actual = random.randint(1, max(1, int(stock_minimo * 0.4)))
    elif estado == "bajo":
        stock_actual = random.randint(int(stock_minimo * 0.4), stock_minimo)
    elif estado == "normal":
        stock_actual = random.randint(stock_minimo + 1, int(stock_maximo * 0.7))
    elif estado == "alto":
        stock_actual = random.randint(int(stock_maximo * 0.7), stock_maximo)
    else:  # exceso
        stock_actual = random.randint(stock_maximo, int(stock_maximo * 1.5))

    # Última entrada y última venta
    dias_desde_compra = random.randint(1, 45)
    dias_desde_venta = random.choices([0, 1, 2, 3, 5, 10, 20], weights=[40, 25, 15, 8, 5, 5, 2])[0]
    if stock_actual == 0:
        dias_desde_venta = random.randint(3, 15)

    inventario.append({
        "sku": sku,
        "producto": producto,
        "categoria": categoria,
        "proveedor": proveedor,
        "stock_actual": stock_actual,
        "stock_minimo": stock_minimo,
        "stock_maximo": stock_maximo,
        "costo_unitario": costo,
        "precio_venta": venta,
        "consumo_diario_promedio": consumo,
        "tiempo_entrega_dias": lead,
        "ultima_entrada": (hoy - timedelta(days=dias_desde_compra)).date(),
        "ultima_venta": (hoy - timedelta(days=dias_desde_venta)).date(),
    })

df_inv = pd.DataFrame(inventario)

# ============================================================
# HISTORIAL DE MOVIMIENTOS (últimos 60 días)
# ============================================================
movimientos = []
mov_id = 1
for dia in range(60):
    fecha = hoy - timedelta(days=60 - dia)
    # Cada día se venden entre 30 y 70 unidades de productos al azar
    num_eventos = random.randint(30, 70)
    for _ in range(num_eventos):
        prod = random.choice(catalogo)
        sku = prod[0]
        cantidad = random.randint(1, 5)
        movimientos.append({
            "id_movimiento": mov_id,
            "fecha": fecha.date(),
            "sku": sku,
            "producto": prod[1],
            "tipo": "salida",
            "cantidad": cantidad,
            "costo_unitario": prod[4],
            "valor_total": cantidad * prod[4],
        })
        mov_id += 1
    # Algunas entradas (compras) cada 3-5 días
    if dia % 4 == 0:
        for prod in random.sample(catalogo, k=random.randint(2, 5)):
            cantidad = random.randint(20, 80)
            movimientos.append({
                "id_movimiento": mov_id,
                "fecha": fecha.date(),
                "sku": prod[0],
                "producto": prod[1],
                "tipo": "entrada",
                "cantidad": cantidad,
                "costo_unitario": prod[4],
                "valor_total": cantidad * prod[4],
            })
            mov_id += 1

df_mov = pd.DataFrame(movimientos)

# ============================================================
# GUARDADO EN EXCEL — UN ARCHIVO, DOS PESTAÑAS
# ============================================================
salida = "inventario.xlsx"
with pd.ExcelWriter(salida, engine="openpyxl") as writer:
    df_inv.to_excel(writer, sheet_name="inventario", index=False)
    df_mov.to_excel(writer, sheet_name="movimientos", index=False)

print(f"[OK] Archivo '{salida}' generado")
print(f"     - Inventario: {len(df_inv)} productos")
print(f"     - Movimientos: {len(df_mov)} registros (60 dias)")
print(f"     - Capital inmovilizado: ${(df_inv['stock_actual'] * df_inv['costo_unitario']).sum():,.2f}")
