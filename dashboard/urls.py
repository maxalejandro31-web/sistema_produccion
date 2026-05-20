from django.urls import path
from .views import inicio, login_view, logout_view, cargar_datos_view

urlpatterns = [
    path('', inicio, name='inicio'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('cargar-datos/', cargar_datos_view, name='cargar_datos'),
]