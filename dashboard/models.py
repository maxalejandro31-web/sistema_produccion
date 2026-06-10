from django.db import models
from django.conf import settings


class ConfiguracionEmpresa(models.Model):
    nombre_empresa = models.CharField(max_length=120, default='Sistema Control de Producción')
    slogan         = models.CharField(max_length=200, blank=True, default='')
    logo_url       = models.URLField(blank=True, default='', verbose_name='URL del logo')

    class Meta:
        verbose_name = 'Configuración de Empresa'

    def __str__(self):
        return self.nombre_empresa

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1, defaults={
            'nombre_empresa': 'Sistema Control de Producción'
        })
        return obj


class HistorialCambio(models.Model):
    ACCION_CHOICES = [
        ('CREAR', 'Creado'),
        ('EDITAR', 'Editado'),
        ('ESTADO', 'Cambio de estado'),
        ('MOVIMIENTO', 'Movimiento registrado'),
    ]

    tipo_objeto = models.CharField(max_length=50)
    objeto_id   = models.PositiveIntegerField()
    objeto_str  = models.CharField(max_length=200, blank=True)
    accion      = models.CharField(max_length=20, choices=ACCION_CHOICES)
    descripcion = models.TextField(blank=True)
    usuario     = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
    )
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha']
        verbose_name = 'Historial de cambio'

    def __str__(self):
        return f'{self.tipo_objeto} #{self.objeto_id} — {self.accion}'


def registrar_historial(request, tipo_objeto, objeto_id, objeto_str, accion, descripcion=''):
    HistorialCambio.objects.create(
        tipo_objeto=tipo_objeto,
        objeto_id=objeto_id,
        objeto_str=objeto_str,
        accion=accion,
        descripcion=descripcion,
        usuario=request.user if request and request.user.is_authenticated else None,
    )