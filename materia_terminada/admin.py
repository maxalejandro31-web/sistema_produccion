from django.contrib import admin
from .models import ProductoTerminado


@admin.register(ProductoTerminado)
class ProductoTerminadoAdmin(admin.ModelAdmin):
    list_display = ('numero_pt', 'tipo_proceso', 'cliente', 'peso_kg', 'estado', 'ubicacion', 'fecha_ingreso')
    list_filter = ('estado', 'tipo_proceso', 'fecha_ingreso')
    search_fields = ('numero_pt', 'cliente__nombre', 'orden__folio_orden')
    readonly_fields = ('numero_pt', 'tipo_proceso', 'peso_kg', 'cantidad_paquetes', 'cantidad_piezas', 'fecha_ingreso', 'orden', 'cliente')
