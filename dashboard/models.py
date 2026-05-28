from django.db import models


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