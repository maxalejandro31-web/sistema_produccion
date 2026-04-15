from django.db import models
from django.utils import timezone


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

    material = models.CharField(max_length=50, choices=MATERIAL_CHOICES)
    grado = models.CharField(max_length=100, blank=True, null=True)
    acabado = models.CharField(max_length=100, blank=True, null=True)

    espesor_valor = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    unidad_espesor = models.CharField(max_length=20, choices=UNIDAD_ESPESOR_CHOICES, default='mm')

    ancho = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    largo = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    peso = models.DecimalField(max_digits=10, decimal_places=2)
    peso_restante = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    diametro_interior = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    diametro_exterior = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    proveedor = models.CharField(max_length=150, blank=True, null=True)
    ubicacion = models.CharField(max_length=50, choices=UBICACION_CHOICES, default='Almacén 1')
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='Disponible')

    fecha_entrada = models.DateField(null=True, blank=True)

    archivo_pdf = models.FileField(upload_to='ordenes_mp/', null=True, blank=True)
    observaciones = models.TextField(blank=True, null=True)

    def save(self, *args, **kwargs):
        if self.peso_restante is None:
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
            return round(0.1495 * (92 ** ((36 - float(self.espesor_valor)) / 39)), 4)
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