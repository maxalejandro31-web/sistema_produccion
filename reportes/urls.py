from django.urls import path
from . import views

urlpatterns = [
    path("reportes/", views.reportes_index, name="reportes_index"),
    path("reportes/inventario-mp/", views.reporte_inventario_mp, name="reporte_inventario_mp"),
    path("reportes/movimientos-mp/", views.reporte_movimientos_mp, name="reporte_movimientos_mp"),
    path("reportes/ordenes-produccion/", views.reporte_ordenes_produccion, name="reporte_ordenes_produccion"),
    path("reportes/detalles-slitter/", views.reporte_detalles_slitter, name="reporte_detalles_slitter"),
    path("reportes/producto-terminado/", views.reporte_producto_terminado, name="reporte_producto_terminado"),
    path("reportes/clientes/", views.reporte_clientes, name="reporte_clientes"),
    path("reportes/cobros-estancia/", views.reporte_cobros_estancia, name="reporte_cobros_estancia"),
]
