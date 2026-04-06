from django.urls import path
from .views import captura_orden, lista_ordenes, cambiar_estado, editar_orden, detalle_orden

urlpatterns = [
    path('captura/', captura_orden, name='captura_orden'),
    path('ordenes/', lista_ordenes, name='lista_ordenes'),
    path('orden/<int:orden_id>/<str:nuevo_estado>/', cambiar_estado, name='cambiar_estado'),
    path('editar-orden/<int:orden_id>/', editar_orden, name='editar_orden'),
    path('detalle-orden/<int:orden_id>/', detalle_orden, name='detalle_orden'),
]