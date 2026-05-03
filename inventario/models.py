from django.db import models, transaction
from django.conf import settings
from django.utils import timezone
from decimal import Decimal


class Cliente(models.Model):
    codigo_cliente = models.CharField(max_length=50, unique=True, null=True, blank=True)
    nombre = models.CharField(max_length=150, unique=True)
    activo = models.BooleanField(default=True)

    def __str__(self):
        if self.codigo_cliente:
            return f"{self.codigo_cliente} - {self.nombre}"
        return self.nombre


class MateriaPrima(models.Model):
    TIPO_MP_CHOICES = [
        ('Rollo', 'Rollo'),
        ('Placa', 'Placa'),
        ('Cinta', 'Cinta'),
    ]

    ORIGEN_MP_CHOICES = [
        ('Cliente', 'Cliente'),
        ('Interna', 'Interna'),
    ]

    MATERIAL_CHOICES = [
        ('Galvanizado', 'Galvanizado'),
        ('Crudo', 'Crudo'),
        ('Recocido RFR', 'Recocido RFR'),
        ('Aluminizado', 'Aluminizado'),
        ('Decapado', 'Decapado'),
        ('Rolado en caliente', 'Rolado en caliente'),
        ('Galvanizado y pintado', 'Galvanizado y pintado'),
    ]

    UBICACION_CHOICES = [
        ('Patio A', 'Patio A'),
        ('Patio B', 'Patio B'),
        ('Almacén 1', 'Almacén 1'),
        ('Almacén 2', 'Almacén 2'),
        ('Producción', 'Producción'),
    ]

    ESTADO_CHOICES = [
        ('Disponible', 'Disponible'),
        ('En Proceso', 'En Proceso'),
        ('Terminado', 'Terminado'),
    ]

    UNIDAD_ESPESOR_CHOICES = [
        ('mm', 'mm'),
        ('pulg', 'pulg'),
        ('calibre', 'calibre'),
    ]

    numero_mp = models.CharField(max_length=100, unique=True)
    tipo_mp = models.CharField(max_length=20, choices=TIPO_MP_CHOICES, default='Rollo')
    cliente = models.ForeignKey(Cliente, on_delete=models.SET_NULL, null=True, blank=True)
    origen_mp = models.CharField(max_length=20, choices=ORIGEN_MP_CHOICES, default='Interna')

    lote = models.CharField(max_length=100, blank=True, null=True)
    codigo = models.CharField(max_length=100, blank=True, null=True)
    descripcion = models.CharField(max_length=255, blank=True, null=True)

    material = models.CharField(max_length=50, choices=MATERIAL_CHOICES, blank=True, null=True)
    grado = models.CharField(max_length=100, blank=True, null=True)
    acabado = models.CharField(max_length=100, blank=True, null=True)

    espesor_valor = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    unidad_espesor = models.CharField(max_length=20, choices=UNIDAD_ESPESOR_CHOICES, default='mm', blank=True, null=True)

    ancho = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    largo = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    peso = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    peso_restante = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    diametro_interior = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    diametro_exterior = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    proveedor = models.CharField(max_length=150, blank=True, null=True)
    ubicacion = models.CharField(max_length=50, choices=UBICACION_CHOICES, default='Almacén 1', blank=True, null=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='Disponible', blank=True, null=True)

    fecha_entrada = models.DateField(null=True, blank=True)
    observaciones = models.TextField(blank=True, null=True)

    def save(self, *args, **kwargs):
        if self.peso_restante is None and self.peso is not None:
            self.peso_restante = self.peso
        super().save(*args, **kwargs)

    @property
    def espesor_mm(self):
        if self.espesor_valor is None:
            return None
        if self.unidad_espesor == 'mm':
            return round(float(self.espesor_valor), 4)
        elif self.unidad_espesor == 'pulg':
            return round(float(self.espesor_valor) * 25.4, 4)
        elif self.unidad_espesor == 'calibre':
            try:
                return round(0.1495 * (92 ** ((36 - float(self.espesor_valor)) / 39)), 4)
            except Exception:
                return None
        return None

    @property
    def espesor_pulg(self):
        mm = self.espesor_mm
        if mm is None:
            return None
        return round(mm / 25.4, 4)

    @property
    def calibre(self):
        if self.unidad_espesor == 'calibre' and self.espesor_valor is not None:
            return round(float(self.espesor_valor), 2)
        return None

    @property
    def tiempo_en_fabrica(self):
        if not self.fecha_entrada:
            return "Sin fecha"
        hoy = timezone.localdate()
        dias = (hoy - self.fecha_entrada).days
        if dias < 7:
            return f"{dias} día(s)"
        elif dias < 30:
            semanas = dias // 7
            return f"{semanas} semana(s)"
        else:
            meses = dias // 30
            return f"{meses} mes(es)"

    def __str__(self):
        return self.numero_mp


class MovimientoMP(models.Model):
    TIPO_MOVIMIENTO_CHOICES = [
        ('ENTRADA', 'Entrada'),
        ('CONSUMO', 'Consumo'),
        ('AJUSTE_POSITIVO', 'Ajuste positivo'),
        ('AJUSTE_NEGATIVO', 'Ajuste negativo'),
        ('MERMA', 'Merma'),
        ('TRASPASO', 'Traspaso'),
        ('SALIDA', 'Salida'),
    ]

    mp = models.ForeignKey(
        MateriaPrima,
        on_delete=models.CASCADE,
        related_name='movimientos'
    )
    fecha = models.DateTimeField(auto_now_add=True)
    tipo_movimiento = models.CharField(max_length=30, choices=TIPO_MOVIMIENTO_CHOICES)
    peso = models.DecimalField(max_digits=12, decimal_places=2)
    ubicacion_origen = models.CharField(max_length=100, blank=True, null=True)
    ubicacion_destino = models.CharField(max_length=100, blank=True, null=True)
    observaciones = models.TextField(blank=True, null=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    def __str__(self):
        return f"{self.mp.numero_mp} - {self.tipo_movimiento} - {self.peso}"

    def save(self, *args, **kwargs):
        es_nuevo = self.pk is None

        with transaction.atomic():
            super().save(*args, **kwargs)

            if es_nuevo:
                mp = self.mp
                peso_actual = mp.peso_restante if mp.peso_restante is not None else mp.peso
                if peso_actual is None:
                    peso_actual = Decimal("0.00")

                if self.tipo_movimiento in ['ENTRADA', 'AJUSTE_POSITIVO']:
                    nuevo_peso = peso_actual + self.peso
                elif self.tipo_movimiento in ['CONSUMO', 'AJUSTE_NEGATIVO', 'MERMA', 'SALIDA']:
                    nuevo_peso = peso_actual - self.peso
                else:
                    nuevo_peso = peso_actual

                if nuevo_peso < 0:
                    nuevo_peso = Decimal("0.00")

                mp.peso_restante = nuevo_peso

                if self.tipo_movimiento == 'TRASPASO' and self.ubicacion_destino:
                    mp.ubicacion = self.ubicacion_destino

                if mp.peso_restante == 0:
                    mp.estado = 'Terminado'
                elif mp.estado == 'Disponible' and self.tipo_movimiento in ['CONSUMO', 'MERMA', 'TRASPASO']:
                    mp.estado = 'En Proceso'

                mp.save()