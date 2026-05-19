from django.db import models
from inventario.models import Cliente


class ProductoTerminado(models.Model):
    ESTADO_CHOICES = [
        ('en_almacen', 'En Almacén'),
        ('vendido', 'Vendido'),
        ('embarcado', 'Embarcado'),
    ]

    orden = models.OneToOneField(
        'produccion.OrdenProduccion',
        on_delete=models.CASCADE,
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
