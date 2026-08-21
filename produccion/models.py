from decimal import Decimal
from django.db import models
from django.utils import timezone
from inventario.models import MateriaPrima, Cliente


class LineaProduccion(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.CharField(max_length=200, blank=True, null=True)
    activa = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre


class Operador(models.Model):
    nombre = models.CharField(max_length=120, unique=True)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre


class OrdenProduccion(models.Model):
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('proceso', 'En Proceso'),
        ('terminado', 'Terminado'),
    ]

    TURNO_CHOICES = [
        ('1', 'Turno 1'),
        ('2', 'Turno 2'),
        ('3', 'Turno 3'),
    ]

    PRIORIDAD_CHOICES = [
        ('baja', 'Baja'),
        ('media', 'Media'),
        ('alta', 'Alta'),
        ('urgente', 'Urgente'),
    ]

    TIPO_PROCESO_CHOICES = [
        ('slitter', 'Slitter'),
        ('corte_liso', 'Corte Liso'),
        ('mini_slitter', 'Mini Slitter'),
        ('fleje', 'Fleje'),
    ]

    folio_orden = models.CharField(max_length=50, null=True, blank=True)
    tipo_proceso = models.CharField(max_length=30, choices=TIPO_PROCESO_CHOICES, default='slitter')

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, null=True, blank=True)
    # PROTECT (antes CASCADE): borrar una MP no debe poder arrastrar en cascada
    # las órdenes que la consumieron (y de ahí el producto terminado y las
    # remisiones ya entregadas). Si hace falta borrar la MP, primero hay que
    # resolver/reasignar las órdenes que la referencian.
    mp = models.ForeignKey(MateriaPrima, on_delete=models.PROTECT, null=True, blank=True)
    pt_origen = models.ForeignKey(
        'materia_terminada.ProductoTerminado',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='ordenes_flejado',
    )
    linea = models.ForeignKey(LineaProduccion, on_delete=models.CASCADE)

    operador_nombre = models.CharField(max_length=120, null=True, blank=True, verbose_name='Operador')
    turno = models.CharField(max_length=10, choices=TURNO_CHOICES, null=True, blank=True)
    prioridad = models.CharField(max_length=10, choices=PRIORIDAD_CHOICES, default='media')

    fecha = models.DateField(auto_now_add=True)
    fecha_orden_corte = models.DateField(null=True, blank=True, verbose_name='Fecha de orden de corte')
    fecha_produccion_oc = models.DateField(null=True, blank=True, verbose_name='Fecha de producción de OC')
    hora_inicio = models.TimeField(null=True, blank=True)
    hora_fin = models.TimeField(null=True, blank=True)

    tiempo_preparacion_min = models.PositiveIntegerField(null=True, blank=True)
    tiempo_proceso_min = models.PositiveIntegerField(null=True, blank=True)
    tiempo_muerto_min = models.PositiveIntegerField(null=True, blank=True)

    peso_usado = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    peso_producido = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    scrap_total = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    merma_kg = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    rendimiento_porcentaje = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)

    cantidad_paquetes = models.PositiveIntegerField(null=True, blank=True)
    cantidad_piezas = models.PositiveIntegerField(null=True, blank=True)

    # ── Datos específicos de Fleje ──────────────────────────────────────────
    folio_rollo_padre = models.CharField(max_length=100, null=True, blank=True)
    espesor_rollo_padre = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    peso_rollo_padre = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    tipo_fleje = models.CharField(max_length=100, null=True, blank=True)
    temp_zona_1 = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, verbose_name='Temp. Zona 1')
    temp_zona_2 = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, verbose_name='Temp. Zona 2')
    temp_zona_3 = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, verbose_name='Temp. Zona 3')
    temp_zona_4 = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, verbose_name='Temp. Zona 4')
    temp_zona_5 = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, verbose_name='Temp. Zona 5')
    demora_hora_inicio = models.TimeField(null=True, blank=True)
    demora_hora_fin = models.TimeField(null=True, blank=True)

    observaciones = models.TextField(blank=True, null=True)

    estado = models.CharField(
        max_length=50,
        choices=ESTADO_CHOICES,
        default='pendiente'
    )

    def __str__(self):
        return f"{self.folio_orden} - {self.get_tipo_proceso_display()}"

    def save(self, *args, **kwargs):
        es_nueva = self.pk is None
        generar_folio = es_nueva and not self.folio_orden

        # Estado que tenía la orden en la BD antes de este guardado (None si
        # es nueva). Se necesita para reconciliar el consumo de MP cuando se
        # EDITA una orden que ya existía: sin esto, corregir un peso_usado
        # mal capturado o reasignar la orden a otra MP dejaba el inventario
        # de materia prima desincronizado para siempre (el peso_restante ya
        # descontado por la captura original nunca se ajustaba).
        mp_anterior_id = None
        peso_anterior = None
        if not es_nueva:
            anterior = OrdenProduccion.objects.filter(pk=self.pk).values('mp_id', 'peso_usado').first()
            if anterior:
                mp_anterior_id = anterior['mp_id']
                peso_anterior = anterior['peso_usado']

        if es_nueva and self.mp and self.peso_usado:
            if self.mp.peso_restante is not None and self.mp.peso_restante < self.peso_usado:
                raise ValueError("No hay suficiente peso disponible en la materia prima")

        if not es_nueva and self.mp_id and self.peso_usado:
            # Si se sube el peso_usado (misma MP) o se reasigna la orden a
            # una MP distinta, hay que validar que esa MP tenga peso
            # suficiente para cubrir el consumo NUEVO antes de guardar.
            if self.mp_id == mp_anterior_id:
                delta_validar = float(self.peso_usado) - float(peso_anterior or 0)
            else:
                delta_validar = float(self.peso_usado)
            if delta_validar > 0 and self.mp.peso_restante is not None and float(self.mp.peso_restante) < delta_validar:
                raise ValueError("No hay suficiente peso disponible en la materia prima para este cambio")

        if self.peso_usado and self.peso_producido is not None and float(self.peso_usado) > 0:
            valor_rendimiento = round((float(self.peso_producido) / float(self.peso_usado)) * 100, 2)
            # rendimiento_porcentaje tiene max_digits=6 (hasta 9999.99); si el
            # dato capturado da una proporción absurda, se deja en None en vez
            # de reventar el guardado con decimal.InvalidOperation.
            self.rendimiento_porcentaje = valor_rendimiento if abs(valor_rendimiento) < 10000 else None
        else:
            self.rendimiento_porcentaje = None

        super().save(*args, **kwargs)

        if generar_folio:
            año = timezone.localdate().year
            folio = f'ORD-{año}-{self.pk:04d}'
            OrdenProduccion.objects.filter(pk=self.pk).update(folio_orden=folio)
            self.folio_orden = folio

        from inventario.models import MovimientoMP

        if es_nueva and self.mp and self.peso_usado:
            MovimientoMP.objects.create(
                mp=self.mp,
                tipo_movimiento='CONSUMO',
                peso=self.peso_usado,
                ubicacion_origen=self.mp.ubicacion or '',
                ubicacion_destino='Producción',
                observaciones=f'Consumo por orden {self.folio_orden or self.pk}',
            )
        elif not es_nueva:
            if mp_anterior_id != self.mp_id:
                # La orden se reasignó a otra MP (o se le quitó/puso la MP):
                # se devuelve el consumo anterior a la MP vieja y se registra
                # el consumo nuevo contra la MP actual.
                if mp_anterior_id and peso_anterior:
                    MovimientoMP.objects.create(
                        mp_id=mp_anterior_id,
                        tipo_movimiento='AJUSTE_POSITIVO',
                        peso=peso_anterior,
                        observaciones=f'Reversión por reasignación de MP en orden {self.folio_orden or self.pk}.',
                    )
                if self.mp_id and self.peso_usado:
                    MovimientoMP.objects.create(
                        mp=self.mp,
                        tipo_movimiento='CONSUMO',
                        peso=self.peso_usado,
                        ubicacion_origen=self.mp.ubicacion or '',
                        ubicacion_destino='Producción',
                        observaciones=f'Consumo por reasignación de MP en orden {self.folio_orden or self.pk}.',
                    )
            elif self.mp_id and (self.peso_usado or peso_anterior):
                # Misma MP: si cambió el peso_usado al editar, se ajusta solo
                # la diferencia (no todo el monto) para no descontar de más.
                delta = float(self.peso_usado or 0) - float(peso_anterior or 0)
                if abs(delta) >= 0.01:
                    if delta > 0:
                        MovimientoMP.objects.create(
                            mp=self.mp,
                            tipo_movimiento='CONSUMO',
                            peso=Decimal(str(delta)),
                            ubicacion_origen=self.mp.ubicacion or '',
                            ubicacion_destino='Producción',
                            observaciones=f'Consumo adicional por edición de orden {self.folio_orden or self.pk}.',
                        )
                    else:
                        MovimientoMP.objects.create(
                            mp=self.mp,
                            tipo_movimiento='AJUSTE_POSITIVO',
                            peso=Decimal(str(abs(delta))),
                            observaciones=f'Devolución por edición de orden {self.folio_orden or self.pk}.',
                        )


class DetalleSlitter(models.Model):
    CLASIFICACION_CHOICES = [
        ('normal', 'Normal'),
        ('scrap', 'Scrap'),
        ('descarte', 'Descarte'),
    ]

    orden = models.ForeignKey(
        OrdenProduccion,
        on_delete=models.CASCADE,
        related_name='detalles_slitter'
    )

    no_corte = models.PositiveIntegerField()
    ancho = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    espesor = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    rebaba = models.CharField(max_length=100, blank=True, null=True)
    peso = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    camber = models.CharField(max_length=100, blank=True, null=True)
    clasificacion = models.CharField(max_length=20, choices=CLASIFICACION_CHOICES, default='normal')
    peso_merma = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name='Peso scrap/descarte',
        help_text='Peso real (pesado aparte) del sobrante cuando el corte se clasifica como Scrap o Descarte.',
    )
    observaciones = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        ordering = ['no_corte']
        unique_together = ('orden', 'no_corte')

    @property
    def folio_corte(self):
        """Folio tipo 'M010017075-2-1': número de rollo MP + no_corte, igual al formato de papel de planta."""
        if self.orden_id and self.orden.mp_id:
            return f"{self.orden.mp.numero_mp}-{self.no_corte}"
        return None

    def __str__(self):
        return f"{self.orden.folio_orden} - Corte {self.no_corte}"


class DetalleFleje(models.Model):
    orden = models.ForeignKey(
        OrdenProduccion,
        on_delete=models.CASCADE,
        related_name='detalles_fleje'
    )

    no_fleje = models.PositiveIntegerField()
    folio_descarga = models.CharField(max_length=100, blank=True, null=True)
    porcentaje_rebaba = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    numero_descarga = models.PositiveIntegerField(null=True, blank=True)
    peso_descarga = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    ancho = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    numero_flejes = models.PositiveIntegerField(null=True, blank=True)
    observaciones = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        ordering = ['no_fleje']
        unique_together = ('orden', 'no_fleje')

    @property
    def peso_por_fleje(self):
        """Peso individual de cada tira: peso de la descarga / número de flejes de esa descarga."""
        if self.peso_descarga is None or not self.numero_flejes:
            return None
        return round(float(self.peso_descarga) / self.numero_flejes, 3)

    def __str__(self):
        return f"{self.orden.folio_orden} - Fleje {self.no_fleje}"