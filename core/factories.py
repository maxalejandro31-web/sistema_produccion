"""Helpers compartidos para armar datos de prueba rápido en los tests de las
distintas apps (inventario, produccion, materia_terminada, calidad).

No es una app de Django ni contiene TestCase — son solo funciones factory
para no repetir el mismo boilerplate (crear Cliente, MateriaPrima, usuario
con un rol, etc.) en cada archivo de tests. El nombre del archivo empieza
con "factories" (no "test") a propósito, para que el test runner de Django
no intente descubrir tests aquí dentro.
"""
from django.contrib.auth.models import User, Group

from inventario.models import Cliente, MateriaPrima
from produccion.models import LineaProduccion, OrdenProduccion, DetalleSlitter, DetalleFleje


def crear_usuario_con_rol(username, *roles, password='pass12345', is_superuser=False):
    """Crea un usuario y lo mete en los grupos (roles) indicados, creando el
    grupo si todavía no existe (get_or_create — varios roles ya se crean
    automáticamente vía migración, no hay que asumir que ya existen o que
    no existen)."""
    user = User.objects.create_user(username, password=password, is_superuser=is_superuser)
    for rol in roles:
        grupo, _ = Group.objects.get_or_create(name=rol)
        user.groups.add(grupo)
    return user


def crear_cliente(nombre=None, **kwargs):
    if nombre is None:
        nombre = f'Cliente de prueba {Cliente.objects.count() + 1}'
    kwargs.setdefault('activo', True)
    return Cliente.objects.create(nombre=nombre, **kwargs)


def crear_linea(nombre='Línea de prueba'):
    linea, _ = LineaProduccion.objects.get_or_create(nombre=nombre)
    return linea


def crear_mp(numero_mp=None, cliente=None, peso=1000, **kwargs):
    if numero_mp is None:
        numero_mp = f'MP-TEST-{MateriaPrima.objects.count() + 1}'
    if cliente is None:
        cliente = crear_cliente()
    kwargs.setdefault('estado', 'Disponible')
    kwargs.setdefault('peso_restante', peso)
    return MateriaPrima.objects.create(numero_mp=numero_mp, cliente=cliente, peso=peso, **kwargs)


def crear_orden_slitter(mp=None, cliente=None, linea=None, peso_usado=100, cortes=None, terminar=False):
    """Crea una OrdenProduccion tipo slitter con sus DetalleSlitter. `cortes`
    es una lista de dicts {no_corte, peso, [espesor], [ancho]}; si no se da,
    se crea un solo corte con todo el peso_usado. Si terminar=True, la deja
    en estado 'terminado' (dispara el signal que genera ProductoTerminado)."""
    if cliente is None:
        cliente = crear_cliente()
    if mp is None:
        mp = crear_mp(cliente=cliente, peso=max(peso_usado * 2, 500))
    if linea is None:
        linea = crear_linea()

    orden = OrdenProduccion.objects.create(
        tipo_proceso='slitter', mp=mp, cliente=cliente, linea=linea,
        peso_usado=peso_usado, peso_producido=peso_usado,
    )

    if cortes is None:
        cortes = [{'no_corte': 1, 'peso': peso_usado}]

    for c in cortes:
        DetalleSlitter.objects.create(
            orden=orden,
            no_corte=c['no_corte'],
            peso=c.get('peso'),
            espesor=c.get('espesor'),
            ancho=c.get('ancho'),
        )

    if terminar:
        orden.estado = 'terminado'
        orden.save()

    return orden


def crear_orden_fleje(pt_origen, cliente=None, linea=None, peso_usado=50, flejes=None, terminar=False):
    if cliente is None:
        cliente = pt_origen.cliente or crear_cliente()
    if linea is None:
        linea = crear_linea()

    orden = OrdenProduccion.objects.create(
        tipo_proceso='fleje', pt_origen=pt_origen, cliente=cliente, linea=linea,
        peso_usado=peso_usado, peso_producido=peso_usado,
    )

    if flejes is None:
        flejes = [{'no_fleje': 1, 'peso_descarga': peso_usado, 'numero_flejes': 1}]

    for f in flejes:
        DetalleFleje.objects.create(
            orden=orden,
            no_fleje=f['no_fleje'],
            peso_descarga=f.get('peso_descarga'),
            numero_flejes=f.get('numero_flejes'),
        )

    if terminar:
        orden.estado = 'terminado'
        orden.save()

    return orden
