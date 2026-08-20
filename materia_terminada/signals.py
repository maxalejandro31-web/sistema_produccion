from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

TIPO_PRODUCTO_MAP = {
    'slitter':      'cinta',
    'mini_slitter': 'cinta',
    'corte_liso':   'cinta',
    'fleje':        'fleje',
}


@receiver(pre_save, sender='produccion.OrdenProduccion')
def capturar_estado_anterior(sender, instance, **kwargs):
    if instance.pk:
        try:
            instance._estado_anterior = sender.objects.get(pk=instance.pk).estado
        except sender.DoesNotExist:
            instance._estado_anterior = None
    else:
        instance._estado_anterior = None


@receiver(post_save, sender='produccion.OrdenProduccion')
def crear_producto_terminado(sender, instance, created, **kwargs):
    estado_anterior = getattr(instance, '_estado_anterior', None)
    if instance.estado != 'terminado' or estado_anterior == 'terminado':
        return

    from materia_terminada.models import ProductoTerminado

    if instance.productos_terminados.exists():
        return

    if instance.tipo_proceso == 'slitter':
        # Un PT por cada corte del detalle slitter
        for detalle in instance.detalles_slitter.all():
            if not detalle.peso:
                continue
            numero_pt = f"PT-{instance.folio_orden}-C{detalle.no_corte}"
            ProductoTerminado.objects.create(
                orden=instance,
                detalle_slitter=detalle,
                cliente=instance.cliente,
                numero_pt=numero_pt,
                tipo_proceso=instance.tipo_proceso,
                tipo_producto='cinta',
                peso_kg=detalle.peso,
            )
    elif instance.tipo_proceso == 'fleje':
        # Un PT por cada tira/fleje del detalle
        for detalle in instance.detalles_fleje.all():
            if not detalle.peso_descarga:
                continue
            numero_pt = f"PT-{instance.folio_orden}-F{detalle.no_fleje}"
            ProductoTerminado.objects.create(
                orden=instance,
                detalle_fleje=detalle,
                cliente=instance.cliente,
                numero_pt=numero_pt,
                tipo_proceso=instance.tipo_proceso,
                tipo_producto='fleje',
                peso_kg=detalle.peso_descarga,
            )
    else:
        # Para corte_liso, mini_slitter y otros: un PT por orden
        numero_pt = f"PT-{instance.folio_orden}" if instance.folio_orden else f"PT-{instance.pk}"
        tipo_producto = TIPO_PRODUCTO_MAP.get(instance.tipo_proceso, 'otro')

        ProductoTerminado.objects.create(
            orden=instance,
            cliente=instance.cliente,
            numero_pt=numero_pt,
            tipo_proceso=instance.tipo_proceso,
            tipo_producto=tipo_producto,
            peso_kg=instance.peso_producido or 0,
            cantidad_paquetes=instance.cantidad_paquetes,
            cantidad_piezas=instance.cantidad_piezas,
        )

    # Marcar la cinta origen como embarcada cuando se termina el fleje
    if instance.tipo_proceso == 'fleje' and instance.pt_origen_id:
        ProductoTerminado.objects.filter(pk=instance.pt_origen_id).update(estado='embarcado')


@receiver(post_save, sender='produccion.DetalleSlitter')
def sincronizar_pt_desde_detalle_slitter(sender, instance, **kwargs):
    """Mantiene sincronizado el ProductoTerminado de este corte con el
    detalle de la orden, sin importar en qué orden se guarden las cosas:

    - Si el corte ya tiene su PT generado, actualiza el peso (cubre el caso
      de corregir un peso mal capturado en una orden ya terminada).
    - Si el corte todavía NO tiene PT pero la orden ya está 'terminada' y el
      corte ya tiene peso, lo crea. Esto cubre dos huecos reales: (1) se
      agregó un corte nuevo al editar una orden que ya estaba terminada, y
      (2) el corte se capturó originalmente con peso en blanco/0 -y por eso
      se saltó al generar el PT la primera vez- y luego se corrigió el peso.
    """
    from materia_terminada.models import ProductoTerminado

    if not instance.peso:
        return

    pt = ProductoTerminado.objects.filter(detalle_slitter=instance).first()
    if pt:
        if pt.peso_kg != instance.peso:
            ProductoTerminado.objects.filter(pk=pt.pk).update(peso_kg=instance.peso)
        return

    orden = instance.orden
    if orden.estado != 'terminado':
        return

    numero_pt = f"PT-{orden.folio_orden}-C{instance.no_corte}"
    if ProductoTerminado.objects.filter(numero_pt=numero_pt).exists():
        return
    ProductoTerminado.objects.create(
        orden=orden,
        detalle_slitter=instance,
        cliente=orden.cliente,
        numero_pt=numero_pt,
        tipo_proceso=orden.tipo_proceso,
        tipo_producto='cinta',
        peso_kg=instance.peso,
    )


@receiver(post_save, sender='produccion.DetalleFleje')
def sincronizar_pt_desde_detalle_fleje(sender, instance, **kwargs):
    """Ídem sincronizar_pt_desde_detalle_slitter, pero para flejes."""
    from materia_terminada.models import ProductoTerminado

    if not instance.peso_descarga:
        return

    pt = ProductoTerminado.objects.filter(detalle_fleje=instance).first()
    if pt:
        if pt.peso_kg != instance.peso_descarga:
            ProductoTerminado.objects.filter(pk=pt.pk).update(peso_kg=instance.peso_descarga)
        return

    orden = instance.orden
    if orden.estado != 'terminado':
        return

    numero_pt = f"PT-{orden.folio_orden}-F{instance.no_fleje}"
    if ProductoTerminado.objects.filter(numero_pt=numero_pt).exists():
        return
    ProductoTerminado.objects.create(
        orden=orden,
        detalle_fleje=instance,
        cliente=orden.cliente,
        numero_pt=numero_pt,
        tipo_proceso=orden.tipo_proceso,
        tipo_producto='fleje',
        peso_kg=instance.peso_descarga,
    )
