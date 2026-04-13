from django.urls import path
from .views import inicio, login_view, logout_view

urlpatterns = [
    path('', inicio, name='inicio'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
]