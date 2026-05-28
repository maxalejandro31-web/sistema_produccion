from django.urls import path
from .views import (
    inicio, login_view, logout_view, cargar_datos_view,
    cambiar_password,
    lista_usuarios, crear_usuario, editar_usuario,
)

urlpatterns = [
    path('', inicio, name='inicio'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('cargar-datos/', cargar_datos_view, name='cargar_datos'),
    path('cambiar-password/', cambiar_password, name='cambiar_password'),
    path('usuarios/', lista_usuarios, name='lista_usuarios'),
    path('usuarios/crear/', crear_usuario, name='crear_usuario'),
    path('usuarios/<int:user_id>/editar/', editar_usuario, name='editar_usuario'),
]
