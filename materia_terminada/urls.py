from django.urls import path
from . import views

urlpatterns = [
    path('producto-terminado/', views.lista_pt, name='lista_pt'),
    path('producto-terminado/<int:pt_id>/', views.detalle_pt, name='detalle_pt'),
    path('producto-terminado/<int:pt_id>/estado/<str:nuevo_estado>/', views.cambiar_estado_pt, name='cambiar_estado_pt'),
]
