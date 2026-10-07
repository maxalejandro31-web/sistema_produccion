"""Quita, una sola vez, los cortes y tiras VACÍOS que se guardaron por error.

La pantalla de captura pre-llena el No. de corte (Slitter) y el No./# de
descarga (Fleje) de los renglones extra; al guardar, esos renglones sin
ningún otro dato se guardaban como cortes/tiras reales. Ensuciaban el
detalle y la impresión de la orden, y hacían que el siguiente proceso del
mismo rollo se brincara esos números de corte. La captura ya los descarta;
aquí se limpian los que ya existen.

Solo se borra un renglón si NO tiene ningún dato (peso, medidas, rebaba,
observaciones...) y no tiene Producto Terminado ligado.
"""
from django.db import migrations
from django.db.models import Q


def _vacio(*campos_texto, campos_num=()):
    q = Q()
    for c in campos_num:
        q &= Q(**{f'{c}__isnull': True})
    for c in campos_texto:
        q &= (Q(**{f'{c}__isnull': True}) | Q(**{c: ''}))
    return q


def limpiar(apps, schema_editor):
    DetalleSlitter = apps.get_model('produccion', 'DetalleSlitter')
    DetalleFleje = apps.get_model('produccion', 'DetalleFleje')

    cortes = DetalleSlitter.objects.filter(
        _vacio('rebaba', 'camber', 'observaciones',
               campos_num=('peso', 'peso_merma', 'ancho', 'espesor')),
        producto_terminado__isnull=True,
    )
    cortes.delete()

    tiras = DetalleFleje.objects.filter(
        _vacio('folio_descarga', 'observaciones',
               campos_num=('peso_descarga', 'porcentaje_rebaba', 'ancho', 'numero_flejes')),
        producto_terminado__isnull=True,
    )
    tiras.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('produccion', '0015_scrap_no_cuenta_como_producido'),
        ('materia_terminada', '0006_alter_productoterminado_orden_and_more'),
    ]

    operations = [
        migrations.RunPython(limpiar, migrations.RunPython.noop),
    ]
