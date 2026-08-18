from django.contrib import admin

from .models import CertificadoCalidad, NoConformidad, ToleranciaProceso


@admin.register(CertificadoCalidad)
class CertificadoCalidadAdmin(admin.ModelAdmin):
    list_display = ('numero_certificado', 'tipo_documento', 'mp', 'producto_terminado', 'aprobado', 'fecha_emision')
    list_filter = ('tipo_documento', 'aprobado')
    search_fields = ('numero_certificado', 'numero_colada', 'proveedor_emisor')


@admin.register(NoConformidad)
class NoConformidadAdmin(admin.ModelAdmin):
    list_display = ('id', 'tipo', 'severidad', 'estado', 'orden', 'mp', 'producto_terminado', 'fecha_deteccion')
    list_filter = ('tipo', 'severidad', 'estado')
    search_fields = ('descripcion',)


@admin.register(ToleranciaProceso)
class ToleranciaProcesoAdmin(admin.ModelAdmin):
    list_display = ('tipo_proceso', 'material', 'tolerancia_ancho_mm', 'tolerancia_espesor_mm', 'activa')
    list_filter = ('tipo_proceso', 'activa')
