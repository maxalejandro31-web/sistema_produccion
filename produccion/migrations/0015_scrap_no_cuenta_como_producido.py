"""Corrige, una sola vez, las órdenes de Slitter capturadas con cortes
marcados Scrap o Descarte.

Antes, el peso de esos cortes se sumaba como PESO PRODUCIDO (el rendimiento
salía inflado) y además cada uno se daba de alta como cinta en Producto
Terminado. La captura ya se corrigió (solo cuentan los cortes 'normal'); esta
migración arregla lo que ya estaba guardado:

1. Órdenes de slitter con algún corte Scrap/Descarte con peso: se recalcula
   peso producido (solo cortes normales), scrap, merma y rendimiento. No se
   tocan cortes, pesos usados ni inventario de MP.
2. Producto Terminado generado de un corte Scrap/Descarte: se quita SOLO si
   nunca se movió (sigue en almacén, sin salida, sin usarse en fleje y sin
   registros de calidad). Si ya se movió se deja tal cual.

Todo queda anotado en el Historial de cada orden.
"""
from decimal import Decimal

from django.db import migrations


def corregir(apps, schema_editor):
    OrdenProduccion = apps.get_model('produccion', 'OrdenProduccion')
    DetalleSlitter = apps.get_model('produccion', 'DetalleSlitter')
    ProductoTerminado = apps.get_model('materia_terminada', 'ProductoTerminado')
    HistorialCambio = apps.get_model('dashboard', 'HistorialCambio')

    ordenes_ids = set(
        DetalleSlitter.objects
        .exclude(clasificacion='normal')
        .filter(peso__gt=0, orden__tipo_proceso='slitter')
        .values_list('orden_id', flat=True)
    )

    for orden in OrdenProduccion.objects.filter(pk__in=ordenes_ids):
        detalles = list(DetalleSlitter.objects.filter(orden_id=orden.pk))
        producido = sum(
            (d.peso for d in detalles if d.peso and (d.clasificacion or 'normal') == 'normal'),
            Decimal('0'),
        )
        usado = orden.peso_usado
        cambios = {'peso_producido': producido}
        if usado is not None:
            diferencia = usado - producido
            diferencia = diferencia if diferencia > 0 else Decimal('0')
            cambios['scrap_total'] = diferencia
            cambios['merma_kg'] = diferencia
            if usado > 0:
                rend = round(producido / usado * 100, 2)
                cambios['rendimiento_porcentaje'] = rend if abs(rend) < 10000 else None

        antes = (orden.peso_producido, orden.rendimiento_porcentaje)
        OrdenProduccion.objects.filter(pk=orden.pk).update(**cambios)

        notas = [
            f'Corrección automática: los cortes marcados Scrap/Descarte ya no cuentan como producido. '
            f'Peso producido {antes[0]} → {producido} kg; rendimiento {antes[1]} → '
            f'{cambios.get("rendimiento_porcentaje")}%.'
        ]

        for d in detalles:
            if (d.clasificacion or 'normal') == 'normal':
                continue
            for pt in ProductoTerminado.objects.filter(detalle_slitter_id=d.pk):
                movido = (
                    pt.estado != 'en_almacen'
                    or pt.salida_detalle.exists()
                    or pt.ordenes_flejado.exists()
                    or pt.certificados.exists()
                    or pt.no_conformidades.exists()
                )
                if movido:
                    notas.append(f'El PT {pt.numero_pt} (corte {d.no_corte}, {d.clasificacion}) ya se había '
                                 f'movido; se dejó sin cambios para revisión.')
                else:
                    notas.append(f'Se quitó el PT {pt.numero_pt} (corte {d.no_corte}, {d.clasificacion}): '
                                 f'era scrap, no cinta.')
                    pt.delete()

        HistorialCambio.objects.create(
            tipo_objeto='OrdenProduccion', objeto_id=orden.pk,
            objeto_str=orden.folio_orden or str(orden.pk),
            accion='EDITAR', descripcion=' '.join(notas), usuario=None,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('produccion', '0014_alter_ordenproduccion_mp'),
        ('materia_terminada', '0006_alter_productoterminado_orden_and_more'),
        ('calidad', '0001_initial'),
        ('dashboard', '0009_alter_historialcambio_accion'),
    ]

    operations = [
        migrations.RunPython(corregir, migrations.RunPython.noop),
    ]
