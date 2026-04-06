from django.contrib import admin
from .models import LineaProduccion, Operador, OrdenProduccion, DetalleSlitter


@admin.register(LineaProduccion)
class LineaProduccionAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'descripcion', 'activa')
    search_fields = ('nombre',)
    list_filter = ('activa',)


@admin.register(Operador)
class OperadorAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'activo')
    search_fields = ('nombre',)
    list_filter = ('activo',)


class DetalleSlitterInline(admin.TabularInline):
    model = DetalleSlitter
    extra = 1


@admin.register(OrdenProduccion)
class OrdenProduccionAdmin(admin.ModelAdmin):
    list_display = (
        'folio_orden',
        'cliente',
        'mp',
        'linea',
        'operador',
        'turno',
        'prioridad',
        'peso_usado',
        'peso_producido',
        'estado',
        'fecha',
    )
    search_fields = (
        'folio_orden',
        'cliente__nombre',
        'mp__numero_mp',
        'linea__nombre',
        'operador__nombre',
    )
    list_filter = (
        'estado',
        'turno',
        'prioridad',
        'linea',
        'fecha',
    )
    inlines = [DetalleSlitterInline]


@admin.register(DetalleSlitter)
class DetalleSlitterAdmin(admin.ModelAdmin):
    list_display = (
        'orden',
        'no_corte',
        'ancho',
        'espesor',
        'peso',
        'material_ok',
    )
    search_fields = (
        'orden__folio_orden',
        'orden__mp__numero_mp',
    )
    list_filter = ('material_ok',)