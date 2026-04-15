from django.contrib import admin
from .models import Cliente, MateriaPrima


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('codigo_cliente', 'nombre', 'activo')
    search_fields = ('codigo_cliente', 'nombre')
    list_filter = ('activo',)


@admin.register(MateriaPrima)
class MateriaPrimaAdmin(admin.ModelAdmin):
    list_display = (
        'numero_mp',
        'tipo_mp',
        'cliente',
        'origen_mp',
        'material',
        'peso',
        'peso_restante',
        'ubicacion',
        'estado',
        'fecha_entrada',
    )
    search_fields = (
        'numero_mp',
        'cliente__nombre',
        'material',
        'descripcion',
    )
    list_filter = (
        'tipo_mp',
        'origen_mp',
        'material',
        'estado',
        'ubicacion',
        'fecha_entrada',
    )