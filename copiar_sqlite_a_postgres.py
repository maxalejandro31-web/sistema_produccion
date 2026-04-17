import os
import sqlite3
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django
django.setup()

from inventario.models import Cliente, MateriaPrima

BASE_DIR = Path(__file__).resolve().parent
SQLITE_PATH = BASE_DIR / "db.sqlite3"


def obtener_columnas_sqlite(conn, tabla):
    cursor = conn.execute(f"PRAGMA table_info({tabla})")
    return [fila[1] for fila in cursor.fetchall()]


def copiar_clientes(conn):
    print("Copiando clientes...")
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT * FROM inventario_cliente")
    filas = cursor.fetchall()

    columnas_modelo = {f.column for f in Cliente._meta.concrete_fields}

    copiados = 0
    for fila in filas:
        data = {k: fila[k] for k in fila.keys() if k in columnas_modelo}
        pk = data.pop("id", None)

        if pk is not None:
            Cliente.objects.update_or_create(id=pk, defaults=data)
        else:
            Cliente.objects.update_or_create(
                nombre=data.get("nombre"),
                defaults=data
            )
        copiados += 1

    print(f"Clientes copiados: {copiados}")


def copiar_mp(conn):
    print("Copiando materia prima...")
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT * FROM inventario_materiaprima")
    filas = cursor.fetchall()

    columnas_modelo = {f.column for f in MateriaPrima._meta.concrete_fields}

    copiados = 0
    for fila in filas:
        data = {k: fila[k] for k in fila.keys() if k in columnas_modelo}
        pk = data.pop("id", None)

        if pk is not None:
            MateriaPrima.objects.update_or_create(id=pk, defaults=data)
        else:
            numero_mp = data.get("numero_mp")
            if numero_mp:
                MateriaPrima.objects.update_or_create(
                    numero_mp=numero_mp,
                    defaults=data
                )
            else:
                MateriaPrima.objects.create(**data)

        copiados += 1

    print(f"Materia prima copiada: {copiados}")


def main():
    print(f"Leyendo SQLite desde: {SQLITE_PATH}")

    if not SQLITE_PATH.exists():
        print("No se encontró db.sqlite3")
        return

    conn = sqlite3.connect(SQLITE_PATH)

    try:
        copiar_clientes(conn)
        copiar_mp(conn)
        print("Copia terminada correctamente.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()