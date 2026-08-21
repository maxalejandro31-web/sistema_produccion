from django.urls import path
from .views import (
    captura_mp,
    lista_mp,
    editar_mp,
    eliminar_mp,
    detalle_mp,
    reporte_rollo,
    reporte_rollo_excel,
    lista_clientes,
    captura_cliente,
    editar_cliente,
    api_datos_mp,
    registrar_movimiento,
    dar_salida_mp,
    lista_salidas_mp,
)

urlpatterns = [
    path('captura-mp/', captura_mp, name='captura_mp'),
    path('lista-mp/', lista_mp, name='lista_mp'),
    path('editar-mp/<int:mp_id>/', editar_mp, name='editar_mp'),
    path('eliminar-mp/<int:mp_id>/', eliminar_mp, name='eliminar_mp'),
    path('detalle-mp/<int:mp_id>/', detalle_mp, name='detalle_mp'),
    path('reporte-rollo/<int:mp_id>/', reporte_rollo, name='reporte_rollo'),
    path('reporte-rollo/<int:mp_id>/excel/', reporte_rollo_excel, name='reporte_rollo_excel'),
    path('salidas-mp/', lista_salidas_mp, name='lista_salidas_mp'),

    path('clientes/', lista_clientes, name='lista_clientes'),
    path('captura-cliente/', captura_cliente, name='captura_cliente'),
    path('editar-cliente/<int:cliente_id>/', editar_cliente, name='editar_cliente'),
    path('api/mp/<int:mp_id>/', api_datos_mp, name='api_datos_mp'),
    path('mp/<int:mp_id>/movimiento/', registrar_movimiento, name='registrar_movimiento'),
    path('mp/<int:mp_id>/salida/', dar_salida_mp, name='dar_salida_mp'),
]