from django.contrib import admin
from .models import Cliente, MateriaPrima


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'activo')
    search_fields = ('nombre',)
    list_filter = ('activo',)


@admin.register(MateriaPrima)
class MateriaPrimaAdmin(admin.ModelAdmin):
    list_display = (
        'numero_mp',
        'tipo_mp',
        'material',
        'grado',
        'acabado',
        'espesor_valor',
        'unidad_espesor',
        'espesor_mm',
        'calibre',
        'ancho',
        'largo',
        'peso',
        'peso_restante',
        'ubicacion',
        'estado',
        'fecha_entrada',
    )
    search_fields = (
        'numero_mp',
        'lote',
        'codigo',
        'descripcion',
        'material',
        'grado',
        'acabado',
    )
    list_filter = (
        'tipo_mp',
        'material',
        'estado',
        'ubicacion',
        'acabado',
    )