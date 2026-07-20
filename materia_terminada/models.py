from django.db import models
from django.utils import timezone
from inventario.models import Cliente


class ProductoTerminado(models.Model):
    ESTADO_CHOICES = [
        ('en_almacen', 'En Almacén'),
        ('vendido', 'Vendido'),
        ('embarcado', 'Embarcado'),
    ]

    TIPO_PRODUCTO_CHOICES = [
        ('cinta', 'Cinta'),
        ('fleje', 'Fleje'),
        ('otro', 'Otro'),
    ]

    orden = models.ForeignKey(
        'produccion.OrdenProduccion',
        on_delete=models.CASCADE,
        related_name='productos_terminados',
    )
    detalle_slitter = models.ForeignKey(
        'produccion.DetalleSlitter',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='producto_terminado',
    )
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    numero_pt = models.CharField(max_length=100, unique=True)
    tipo_proceso = models.CharField(max_length=30)
    tipo_producto = models.CharField(max_length=20, choices=TIPO_PRODUCTO_CHOICES, default='cinta')

    peso_kg = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cantidad_paquetes = models.PositiveIntegerField(null=True, blank=True)
    cantidad_piezas = models.PositiveIntegerField(null=True, blank=True)

    fecha_ingreso = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='en_almacen')
    ubicacion = models.CharField(max_length=100, default='Almacén PT', blank=True)
    observaciones = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-fecha_ingreso']
        verbose_name = 'Producto Terminado'
        verbose_name_plural = 'Productos Terminados'

    def __str__(self):
        return self.numero_pt


class Salida(models.Model):
    TIPO_CHOICES = [
        ('maquila', 'Maquila (al cliente)'),
        ('interno', 'Interno (Centro de Servicio)'),
    ]

    folio_remision = models.CharField(max_length=50, unique=True, blank=True)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    cliente = models.ForeignKey(Cliente, on_delete=models.SET_NULL, null=True, blank=True)
    fecha_salida = models.DateTimeField(default=timezone.now)
    peso_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    observaciones = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-fecha_salida']
        verbose_name = 'Salida'
        verbose_name_plural = 'Salidas'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.folio_remision:
            año = timezone.localdate().year
            self.folio_remision = f'SAL-{año}-{self.pk:04d}'
            Salida.objects.filter(pk=self.pk).update(folio_remision=self.folio_remision)

    def __str__(self):
        return self.folio_remision or f'Salida #{self.pk}'


class SalidaDetalle(models.Model):
    salida = models.ForeignKey(Salida, on_delete=models.CASCADE, related_name='detalles')
    producto_terminado = models.ForeignKey(ProductoTerminado, on_delete=models.CASCADE, related_name='salida_detalle')
    peso_kg = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cantidad_piezas = models.PositiveIntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.salida} - {self.producto_terminado}"
