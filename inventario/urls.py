from django.urls import path
from .views import (
    captura_mp,
    lista_mp,
    editar_mp,
    detalle_mp,
    lista_clientes,
    captura_cliente,
    editar_cliente,
)

urlpatterns = [
    path('captura-mp/', captura_mp, name='captura_mp'),
    path('lista-mp/', lista_mp, name='lista_mp'),
    path('editar-mp/<int:mp_id>/', editar_mp, name='editar_mp'),
    path('detalle-mp/<int:mp_id>/', detalle_mp, name='detalle_mp'),

    path('clientes/', lista_clientes, name='lista_clientes'),
    path('captura-cliente/', captura_cliente, name='captura_cliente'),
    path('editar-cliente/<int:cliente_id>/', editar_cliente, name='editar_cliente'),
]