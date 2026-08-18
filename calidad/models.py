from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


# ── Certificados de calidad ──────────────────────────────────────────────────
#
# Un "certificado de calidad" aquí representa tanto el certificado de molino
# (mill test certificate / MTR) que llega con la materia prima, como el
# certificado que la planta emite para un producto terminado antes de
# embarcarlo. Es el mismo tipo de documento en dos momentos de la cadena, así
# que se modela con un solo formulario que apunta a uno u otro (nunca ambos).

class CertificadoCalidad(models.Model):
    TIPO_DOCUMENTO_CHOICES = [
        ('mp', 'Materia Prima'),
        ('pt', 'Producto Terminado'),
    ]

    tipo_documento = models.CharField(max_length=10, choices=TIPO_DOCUMENTO_CHOICES)

    mp = models.ForeignKey(
        'inventario.MateriaPrima',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='certificados',
        verbose_name='Materia Prima',
    )
    producto_terminado = models.ForeignKey(
        'materia_terminada.ProductoTerminado',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='certificados',
        verbose_name='Producto Terminado',
    )

    numero_certificado = models.CharField(max_length=100, blank=True)
    numero_colada = models.CharField(
        max_length=100, blank=True,
        verbose_name='No. de colada / heat number',
    )
    norma = models.CharField(
        max_length=150, blank=True,
        help_text='Ej. ASTM A1008, ASTM A653, NOM-, etc.',
    )

    # Propiedades mecánicas más comunes en un MTR de acero plano. Todas
    # opcionales porque no todos los proveedores reportan las mismas.
    limite_fluencia_mpa = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        verbose_name='Límite de fluencia (MPa)',
    )
    resistencia_tension_mpa = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        verbose_name='Resistencia a la tensión (MPa)',
    )
    elongacion_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        verbose_name='Elongación (%)',
    )
    dureza = models.CharField(max_length=50, blank=True, verbose_name='Dureza')

    proveedor_emisor = models.CharField(max_length=150, blank=True)
    fecha_emision = models.DateField(null=True, blank=True)
    archivo_pdf = models.FileField(upload_to='certificados_calidad/', null=True, blank=True)

    aprobado = models.BooleanField(
        default=True,
        verbose_name='Aprobado por calidad',
        help_text='Desmarcar si el certificado no cumple la especificación del pedido.',
    )
    observaciones = models.TextField(blank=True)

    fecha_registro = models.DateTimeField(auto_now_add=True)
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
    )

    class Meta:
        ordering = ['-fecha_registro']
        verbose_name = 'Certificado de calidad'
        verbose_name_plural = 'Certificados de calidad'

    def clean(self):
        if bool(self.mp_id) == bool(self.producto_terminado_id):
            raise ValidationError(
                'Un certificado debe apuntar exactamente a una Materia Prima '
                'o a un Producto Terminado, no a ambos ni a ninguno.'
            )

    def __str__(self):
        objeto = self.mp or self.producto_terminado
        return f'Certificado {self.numero_certificado or self.pk} - {objeto}'


# ── No conformidades ─────────────────────────────────────────────────────────

class NoConformidad(models.Model):
    TIPO_CHOICES = [
        ('dimensional', 'Dimensional'),
        ('superficial', 'Superficial / acabado'),
        ('material', 'Material / composición'),
        ('empaque', 'Empaque / embalaje'),
        ('otro', 'Otro'),
    ]

    SEVERIDAD_CHOICES = [
        ('menor', 'Menor'),
        ('mayor', 'Mayor'),
        ('critica', 'Crítica'),
    ]

    ESTADO_CHOICES = [
        ('abierta', 'Abierta'),
        ('en_revision', 'En revisión'),
        ('cerrada', 'Cerrada'),
    ]

    # Se permite ligar la no conformidad a cualquiera de los tres puntos de la
    # cadena donde se puede detectar un defecto; ninguno es obligatorio por
    # separado, pero normalmente se llena al menos uno desde la pantalla de
    # detalle correspondiente.
    orden = models.ForeignKey(
        'produccion.OrdenProduccion',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='no_conformidades',
    )
    mp = models.ForeignKey(
        'inventario.MateriaPrima',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='no_conformidades',
        verbose_name='Materia Prima',
    )
    producto_terminado = models.ForeignKey(
        'materia_terminada.ProductoTerminado',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='no_conformidades',
        verbose_name='Producto Terminado',
    )

    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='otro')
    severidad = models.CharField(max_length=10, choices=SEVERIDAD_CHOICES, default='menor')
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='abierta')

    descripcion = models.TextField()
    accion_correctiva = models.TextField(blank=True)
    evidencia_foto = models.ImageField(upload_to='no_conformidades/', null=True, blank=True)

    detectado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='no_conformidades_detectadas',
    )
    fecha_deteccion = models.DateTimeField(auto_now_add=True)
    fecha_cierre = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-fecha_deteccion']
        verbose_name = 'No conformidad'
        verbose_name_plural = 'No conformidades'

    def save(self, *args, **kwargs):
        if self.estado == 'cerrada' and self.fecha_cierre is None:
            self.fecha_cierre = timezone.now()
        elif self.estado != 'cerrada':
            self.fecha_cierre = None
        super().save(*args, **kwargs)

    @property
    def objeto_relacionado(self):
        return self.orden or self.mp or self.producto_terminado

    def __str__(self):
        return f'NC-{self.pk} ({self.get_severidad_display()}) - {self.objeto_relacionado}'


# ── Tolerancias de proceso ───────────────────────────────────────────────────

class ToleranciaProceso(models.Model):
    """Tolerancia dimensional aceptada para un tipo de proceso (y,
    opcionalmente, un material específico). Se usa para marcar
    automáticamente cuando un corte de DetalleSlitter se sale de rango
    respecto al ancho/espesor declarados de la MP de origen."""

    TIPO_PROCESO_CHOICES = [
        ('slitter', 'Slitter'),
        ('corte_liso', 'Corte Liso'),
        ('mini_slitter', 'Mini Slitter'),
        ('fleje', 'Fleje'),
    ]

    tipo_proceso = models.CharField(max_length=30, choices=TIPO_PROCESO_CHOICES)
    material = models.CharField(
        max_length=150, blank=True,
        help_text='Déjalo vacío para que aplique a todos los materiales de este proceso.',
    )

    tolerancia_ancho_mm = models.DecimalField(
        max_digits=6, decimal_places=3, null=True, blank=True,
        verbose_name='Tolerancia de ancho (± mm)',
    )
    tolerancia_espesor_mm = models.DecimalField(
        max_digits=6, decimal_places=4, null=True, blank=True,
        verbose_name='Tolerancia de espesor (± mm)',
    )

    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ['tipo_proceso', 'material']
        unique_together = ('tipo_proceso', 'material')
        verbose_name = 'Tolerancia de proceso'
        verbose_name_plural = 'Tolerancias de proceso'

    @classmethod
    def obtener(cls, tipo_proceso, material):
        """Busca primero una tolerancia específica para ese material; si no
        existe, cae a la genérica del proceso (material vacío)."""
        material = (material or '').strip()
        qs = cls.objects.filter(tipo_proceso=tipo_proceso, activa=True)
        especifica = qs.filter(material__iexact=material).first() if material else None
        return especifica or qs.filter(material='').first()

    def __str__(self):
        material = self.material or 'todos los materiales'
        return f'{self.get_tipo_proceso_display()} - {material}'
