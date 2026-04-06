from django.urls import path
from .views import inicio, exportar_excel, login_view, logout_view

urlpatterns = [
    path('', inicio, name='inicio'),
    path('exportar/', exportar_excel, name='exportar_excel'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
]