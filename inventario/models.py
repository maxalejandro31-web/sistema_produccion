from decimal import Decimal
from django.db import models
from django.utils import timezone


class Cliente(models.Model):
    nombre = models.CharField(max_length=150, unique=True)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre


class MateriaPrima(models.Model):
    TIPO_MP_CHOICES = [
        ('Rollo', 'Rollo'),
        ('Cinta', 'Cinta'),
        ('Placa', 'Placa'),
    ]

    ORIGEN_MP_CHOICES = [
        ('Propia', 'Propia'),
        ('Cliente', 'Cliente'),
    ]

    MATERIAL_CHOICES = [
        ('Galvanizado', 'Galvanizado'),
        ('Crudo', 'Crudo'),
        ('Recocido RFR', 'Recocido RFR'),
        ('Aluminizado', 'Aluminizado'),
        ('Decapado', 'Decapado'),
        ('Rolado en caliente', 'Rolado en caliente'),
    ]

    ESTADO_CHOICES = [
        ('Disponible', 'Disponible'),
        ('En Proceso', 'En Proceso'),
        ('Terminado', 'Terminado'),
    ]

    UBICACION_CHOICES = [
        ('Patio A', 'Patio A'),
        ('Patio B', 'Patio B'),
        ('Almacen 1', 'Almacén 1'),
        ('Almacen 2', 'Almacén 2'),
        ('Produccion', 'Producción'),
    ]

    UNIDAD_ESPESOR_CHOICES = [
        ('mm', 'mm'),
        ('pulg', 'Pulgadas'),
        ('calibre', 'Calibre'),
    ]

    numero_mp = models.CharField(max_length=50, unique=True)
    tipo_mp = models.CharField(max_length=20, choices=TIPO_MP_CHOICES, default='Rollo')

    cliente = models.ForeignKey(Cliente, on_delete=models.SET_NULL, null=True, blank=True)
    origen_mp = models.CharField(max_length=20, choices=ORIGEN_MP_CHOICES, default='Propia')

    lote = models.CharField(max_length=50, blank=True, null=True)
    codigo = models.CharField(max_length=50, blank=True, null=True)
    descripcion = models.CharField(max_length=200, blank=True, null=True)

    material = models.CharField(max_length=100, choices=MATERIAL_CHOICES)
    grado = models.CharField(max_length=50, blank=True, null=True)
    acabado = models.CharField(max_length=50, blank=True, null=True)

    espesor_valor = models.DecimalField(max_digits=10, decimal_places=4)
    unidad_espesor = models.CharField(max_length=10, choices=UNIDAD_ESPESOR_CHOICES, default='mm')

    espesor_mm = models.DecimalField(max_digits=10, decimal_places=4, blank=True, null=True)
    espesor_pulg = models.DecimalField(max_digits=10, decimal_places=4, blank=True, null=True)
    calibre = models.CharField(max_length=20, blank=True, null=True)

    ancho = models.DecimalField(max_digits=10, decimal_places=3, blank=True, null=True)
    largo = models.DecimalField(max_digits=10, decimal_places=3, blank=True, null=True)

    peso = models.DecimalField(max_digits=10, decimal_places=2)
    peso_restante = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

    diametro_interior = models.DecimalField(max_digits=10, decimal_places=3, blank=True, null=True)
    diametro_exterior = models.DecimalField(max_digits=10, decimal_places=3, blank=True, null=True)

    proveedor = models.CharField(max_length=150, blank=True, null=True)
    ubicacion = models.CharField(max_length=100, choices=UBICACION_CHOICES, blank=True, null=True)
    estado = models.CharField(max_length=50, choices=ESTADO_CHOICES, default='Disponible')

    archivo_pdf = models.FileField(upload_to='ordenes_mp/', blank=True, null=True)

    fecha_entrada = models.DateField(auto_now_add=True)
    observaciones = models.TextField(blank=True, null=True)

    def convertir_espesor(self):
        MM_POR_PULGADA = Decimal('25.4')

        tabla_calibres_mm = {
            '7': Decimal('4.5500'),
            '8': Decimal('4.1800'),
            '9': Decimal('3.8000'),
            '10': Decimal('3.4200'),
            '11': Decimal('3.0400'),
            '12': Decimal('2.6600'),
            '13': Decimal('2.2800'),
            '14': Decimal('1.9000'),
            '15': Decimal('1.7100'),
            '16': Decimal('1.5200'),
            '18': Decimal('1.2140'),
            '20': Decimal('0.9120'),
            '22': Decimal('0.7600'),
            '24': Decimal('0.6070'),
            '26': Decimal('0.4550'),
            '28': Decimal('0.3800'),
            '30': Decimal('0.3050'),
        }

        self.espesor_mm = None
        self.espesor_pulg = None

        if self.unidad_espesor == 'mm':
            self.espesor_mm = self.espesor_valor
            self.espesor_pulg = self.espesor_valor / MM_POR_PULGADA

        elif self.unidad_espesor == 'pulg':
            self.espesor_pulg = self.espesor_valor
            self.espesor_mm = self.espesor_valor * MM_POR_PULGADA

        elif self.unidad_espesor == 'calibre':
            valor = str(self.espesor_valor).replace('.0000', '').replace('.0', '')
            mm = tabla_calibres_mm.get(valor)
            if mm:
                self.espesor_mm = mm
                self.espesor_pulg = mm / MM_POR_PULGADA
                self.calibre = valor

        if self.espesor_mm and not self.calibre:
            diferencia_min = None
            calibre_mas_cercano = None

            for cal, mm in tabla_calibres_mm.items():
                diferencia = abs(self.espesor_mm - mm)
                if diferencia_min is None or diferencia < diferencia_min:
                    diferencia_min = diferencia
                    calibre_mas_cercano = cal

            self.calibre = calibre_mas_cercano

    def save(self, *args, **kwargs):
        self.convertir_espesor()

        if self.peso_restante is None:
            self.peso_restante = self.peso

        super().save(*args, **kwargs)

    def tiempo_en_fabrica(self):
        hoy = timezone.now().date()
        dias = (hoy - self.fecha_entrada).days

        if dias < 7:
            return f"{dias} día{'s' if dias != 1 else ''}"
        elif dias < 30:
            semanas = dias // 7
            return f"{semanas} semana{'s' if semanas != 1 else ''}"
        elif dias < 365:
            meses = dias // 30
            return f"{meses} mes{'es' if meses != 1 else ''}"
        else:
            anios = dias // 365
            return f"{anios} año{'s' if anios != 1 else ''}"

    def __str__(self):
        cliente_txt = f" / {self.cliente}" if self.cliente else ""
        return f"{self.numero_mp} - {self.tipo_mp} - {self.material}{cliente_txt}"