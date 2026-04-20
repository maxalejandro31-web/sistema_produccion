import os
import sqlite3
from pathlib import Path
from decimal import Decimal

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django
django.setup()

from inventario.models import Cliente, MateriaPrima
from produccion.models import OrdenProduccion, LineaProduccion


BASE_DIR = Path(__file__).resolve().parent
SQLITE_PATH = BASE_DIR / "db.sqlite3"


def normalizar_decimal(valor):
    if valor in (None, "", "None"):
        return None
    try:
        return Decimal(str(valor))
    except Exception:
        return None


def copiar_lineas(conn):
    print("Copiando líneas de producción...")
    conn.row_factory = sqlite3.Row
    filas = conn.execute("SELECT * FROM produccion_lineaproduccion").fetchall()

    copiados = 0
    for fila in filas:
        data = dict(fila)
        pk = data.get("id")

        defaults = {
            "nombre": data.get("nombre"),
            "descripcion": data.get("descripcion") or "",
            "activa": bool(data.get("activa", True)),
        }

        LineaProduccion.objects.update_or_create(
            id=pk,
            defaults=defaults
        )
        copiados += 1

    print(f"Líneas copiadas: {copiados}")


def copiar_clientes(conn):
    print("Copiando clientes...")
    conn.row_factory = sqlite3.Row
    filas = conn.execute("SELECT * FROM inventario_cliente").fetchall()

    copiados = 0
    for fila in filas:
        data = dict(fila)
        pk = data.get("id")

        defaults = {}
        if "codigo_cliente" in data:
            defaults["codigo_cliente"] = data.get("codigo_cliente")
        if "nombre" in data:
            defaults["nombre"] = data.get("nombre")
        if "activo" in data:
            defaults["activo"] = bool(data.get("activo"))

        Cliente.objects.update_or_create(
            id=pk,
            defaults=defaults
        )
        copiados += 1

    print(f"Clientes copiados: {copiados}")


def copiar_mp(conn):
    print("Copiando materia prima...")
    conn.row_factory = sqlite3.Row
    filas = conn.execute("SELECT * FROM inventario_materiaprima").fetchall()

    copiados = 0
    for fila in filas:
        data = dict(fila)
        pk = data.get("id")

        defaults = {}

        campos_texto = [
            "numero_mp", "tipo_mp", "origen_mp", "lote", "codigo", "descripcion",
            "material", "grado", "acabado", "unidad_espesor", "proveedor",
            "ubicacion", "estado", "archivo_pdf", "observaciones"
        ]
        for campo in campos_texto:
            if campo in data:
                defaults[campo] = data.get(campo)

        campos_decimal = [
            "espesor_valor", "ancho", "largo", "peso", "peso_restante",
            "diametro_interior", "diametro_exterior"
        ]
        for campo in campos_decimal:
            if campo in data:
                defaults[campo] = normalizar_decimal(data.get(campo))

        if "fecha_entrada" in data:
            defaults["fecha_entrada"] = data.get("fecha_entrada") or None

        cliente_id = data.get("cliente_id")
        if cliente_id:
            defaults["cliente_id"] = int(cliente_id)

        MateriaPrima.objects.update_or_create(
            id=pk,
            defaults=defaults
        )
        copiados += 1

    print(f"Materia prima copiada: {copiados}")


def copiar_ordenes(conn):
    print("Copiando órdenes...")
    conn.row_factory = sqlite3.Row
    filas = conn.execute("SELECT * FROM produccion_ordenproduccion").fetchall()

    copiados = 0
    omitidos = 0

    for fila in filas:
        data = dict(fila)
        pk = data.get("id")

        defaults = {}

        campos_texto = [
            "folio_orden", "estado", "tipo_proceso", "turno",
            "prioridad", "observaciones"
        ]
        for campo in campos_texto:
            if campo in data:
                defaults[campo] = data.get(campo)

        campos_decimal = [
            "peso_usado", "peso_producido", "scrap_total"
        ]
        for campo in campos_decimal:
            if campo in data:
                defaults[campo] = normalizar_decimal(data.get(campo))

        # fecha obligatoria
        if "fecha" in data and data.get("fecha"):
            defaults["fecha"] = data.get("fecha")
        else:
            omitidos += 1
            continue

        # foreign keys: solo cargar si existen
        cliente_id = data.get("cliente_id")
        if cliente_id and Cliente.objects.filter(id=cliente_id).exists():
            defaults["cliente_id"] = int(cliente_id)

        mp_id = data.get("mp_id")
        if mp_id and MateriaPrima.objects.filter(id=mp_id).exists():
            defaults["mp_id"] = int(mp_id)

        linea_id = data.get("linea_id")
        if linea_id and LineaProduccion.objects.filter(id=linea_id).exists():
            defaults["linea_id"] = int(linea_id)
        else:
            omitidos += 1
            continue

        operador_id = data.get("operador_id")
        if operador_id:
            defaults["operador_id"] = int(operador_id)

        OrdenProduccion.objects.update_or_create(
            id=pk,
            defaults=defaults
        )
        copiados += 1

    print(f"Órdenes copiadas: {copiados}")
    print(f"Órdenes omitidas por fecha o línea faltante: {omitidos}")


def main():
    print(f"Leyendo SQLite desde: {SQLITE_PATH}")

    if not SQLITE_PATH.exists():
        print("No se encontró db.sqlite3")
        return

    conn = sqlite3.connect(SQLITE_PATH)

    try:
        copiar_lineas(conn)
        copiar_clientes(conn)
        copiar_mp(conn)
        copiar_ordenes(conn)
        print("Copia terminada correctamente.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()