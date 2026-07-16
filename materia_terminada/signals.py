from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

TIPO_PRODUCTO_MAP = {
    'slitter':     'cinta',
    'mini_slitter':'cinta',
    'corte_liso':  'cinta',
    'fleje':       'fleje',
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

    if hasattr(instance, 'producto_terminado'):
        return

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

    # Si es una orden de fleje con cinta origen, marcar esa cinta como embarcada
    if instance.tipo_proceso == 'fleje' and instance.pt_origen_id:
        from materia_terminada.models import ProductoTerminado as PT
        PT.objects.filter(pk=instance.pt_origen_id).update(estado='embarcado')
