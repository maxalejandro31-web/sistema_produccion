from django.urls import path
from . import views

urlpatterns = [
    path('producto-terminado/', views.lista_pt, name='lista_pt'),
    path('producto-terminado/<int:pt_id>/', views.detalle_pt, name='detalle_pt'),
    path('producto-terminado/<int:pt_id>/estado/<str:nuevo_estado>/', views.cambiar_estado_pt, name='cambiar_estado_pt'),
    path('salidas/', views.lista_salidas, name='lista_salidas'),
    path('salidas/nueva/', views.crear_salida, name='crear_salida'),
    path('salidas/<int:salida_id>/', views.detalle_salida, name='detalle_salida'),
]
