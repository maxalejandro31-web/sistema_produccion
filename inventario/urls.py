from django.urls import path
from .views import captura_mp, lista_mp, editar_mp, detalle_mp

urlpatterns = [
    path('captura-mp/', captura_mp, name='captura_mp'),
    path('lista-mp/', lista_mp, name='lista_mp'),
    path('editar-mp/<int:mp_id>/', editar_mp, name='editar_mp'),
    path('detalle-mp/<int:mp_id>/', detalle_mp, name='detalle_mp'),
]