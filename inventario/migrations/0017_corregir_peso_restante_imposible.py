"""Corrige, una sola vez, las MP cuyo peso restante quedó MAYOR que su peso.

Pasaba porque al corregir el peso desde "Editar" solo se cambiaba `peso` y
`peso_restante` se quedaba con el valor mal capturado (ej. 4A626499PDT00:
peso corregido a 21,300 kg pero restante en 213,000 kg, inflando más de 200
toneladas el inventario). La vista de edición ya se corrigió para que no
vuelva a pasar; esta migración arregla los registros que ya quedaron mal,
sin que nadie tenga que abrirlos uno por uno.

Solo toca registros en estado imposible: peso_restante > peso + todo lo que
le ha entrado (ENTRADA + AJUSTE_POSITIVO). A esos se les recalcula:
    peso_restante = peso + entradas − salidas/consumos   (mínimo 0)
y queda la corrección en el Historial de cada MP. Ningún otro registro se
modifica.
"""
from decimal import Decimal

from django.db import migrations
from django.db.models import Sum

ENTRADAS = ('ENTRADA', 'AJUSTE_POSITIVO')
SALIDAS = ('CONSUMO', 'AJUSTE_NEGATIVO', 'MERMA', 'SALIDA')


def corregir(apps, schema_editor):
    MateriaPrima = apps.get_model('inventario', 'MateriaPrima')
    MovimientoMP = apps.get_model('inventario', 'MovimientoMP')
    HistorialCambio = apps.get_model('dashboard', 'HistorialCambio')

    candidatas = MateriaPrima.objects.filter(peso__isnull=False, peso_restante__isnull=False)
    for mp in candidatas.iterator():
        totales = dict(
            MovimientoMP.objects.filter(mp_id=mp.pk)
            .values_list('tipo_movimiento')
            .annotate(t=Sum('peso'))
        )
        entradas = sum((totales.get(t) or Decimal('0') for t in ENTRADAS), Decimal('0'))
        salidas = sum((totales.get(t) or Decimal('0') for t in SALIDAS), Decimal('0'))

        if mp.peso_restante <= mp.peso + entradas:
            continue  # registro coherente: no se toca

        anterior = mp.peso_restante
        nuevo = max(mp.peso + entradas - salidas, Decimal('0'))
        mp.peso_restante = nuevo
        estado_anterior = mp.estado
        if nuevo == 0:
            mp.estado = 'Terminado'
        elif mp.estado == 'Terminado':
            mp.estado = 'En Proceso' if (entradas or salidas) else 'Disponible'
        mp.save(update_fields=['peso_restante', 'estado'])

        desc = (f'Corrección automática: el peso restante ({anterior} kg) era mayor que el peso '
                f'del rollo ({mp.peso} kg) por una corrección de peso anterior que no lo había '
                f'actualizado. Recalculado con sus movimientos: {nuevo} kg.')
        if mp.estado != estado_anterior:
            desc += f' Estado: {estado_anterior} → {mp.estado}.'
        HistorialCambio.objects.create(
            tipo_objeto='MateriaPrima', objeto_id=mp.pk, objeto_str=mp.numero_mp,
            accion='EDITAR', descripcion=desc, usuario=None,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('inventario', '0016_alter_materiaprima_unidad_espesor'),
        ('dashboard', '0009_alter_historialcambio_accion'),
    ]

    operations = [
        migrations.RunPython(corregir, migrations.RunPython.noop),
    ]
