from django.db import models
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

    folio_orden = models.CharField(max_length=50, unique=True, null=True, blank=True)
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, null=True, blank=True)
    mp = models.ForeignKey(MateriaPrima, on_delete=models.CASCADE, null=True, blank=True)
    linea = models.ForeignKey(LineaProduccion, on_delete=models.CASCADE)

    operador = models.ForeignKey(Operador, on_delete=models.SET_NULL, null=True, blank=True)
    turno = models.CharField(max_length=10, choices=TURNO_CHOICES, null=True, blank=True)
    prioridad = models.CharField(max_length=10, choices=PRIORIDAD_CHOICES, default='media')

    hora_inicio = models.TimeField(null=True, blank=True)
    hora_fin = models.TimeField(null=True, blank=True)

    tiempo_preparacion_min = models.PositiveIntegerField(null=True, blank=True)
    tiempo_proceso_min = models.PositiveIntegerField(null=True, blank=True)
    tiempo_muerto_min = models.PositiveIntegerField(null=True, blank=True)

    peso_usado = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    peso_producido = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    cantidad_paquetes = models.PositiveIntegerField(null=True, blank=True)
    cantidad_piezas = models.PositiveIntegerField(null=True, blank=True)
    rendimiento_porcentaje = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    merma_kg = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    observaciones = models.TextField(blank=True, null=True)
    fecha = models.DateTimeField(auto_now_add=True)

    estado = models.CharField(
        max_length=50,
        choices=ESTADO_CHOICES,
        default='pendiente'
    )

    def __str__(self):
        return f"{self.folio_orden} - {self.mp} → {self.linea}"

    def save(self, *args, **kwargs):
        # Solo descontar inventario la primera vez
        if self.pk is None:
            if self.peso_usado is not None and self.mp.peso_restante is not None:
                if self.mp.peso_restante < self.peso_usado:
                    raise ValueError("No hay suficiente peso disponible en la materia prima")

                self.mp.peso_restante -= self.peso_usado

                if self.mp.peso_restante == 0:
                    self.mp.estado = "Terminado"
                else:
                    self.mp.estado = "En Proceso"

                self.mp.save()

        super().save(*args, **kwargs)


class DetalleSlitter(models.Model):
    orden = models.ForeignKey(OrdenProduccion, on_delete=models.CASCADE, related_name='detalles_slitter')
    no_corte = models.PositiveIntegerField()
    ancho = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    espesor = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    rebaba = models.CharField(max_length=100, blank=True, null=True)
    peso = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    camber = models.CharField(max_length=100, blank=True, null=True)
    material_ok = models.BooleanField(default=True)
    observaciones = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"Orden {self.orden.folio_orden} - Corte {self.no_corte}"