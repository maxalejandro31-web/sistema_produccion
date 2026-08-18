from django.urls import path
from . import views

urlpatterns = [
    path('calidad/', views.index, name='calidad_index'),

    path('calidad/certificados/', views.lista_certificados, name='lista_certificados'),
    path('calidad/certificados/nuevo/<str:tipo>/<int:objeto_id>/', views.crear_certificado, name='crear_certificado'),
    path('calidad/certificados/<int:certificado_id>/', views.detalle_certificado, name='detalle_certificado'),
    path('calidad/certificados/<int:certificado_id>/eliminar/', views.eliminar_certificado, name='eliminar_certificado'),

    path('calidad/no-conformidades/', views.lista_no_conformidades, name='lista_no_conformidades'),
    path('calidad/no-conformidades/nueva/<str:origen>/<int:objeto_id>/', views.crear_no_conformidad, name='crear_no_conformidad'),
    path('calidad/no-conformidades/<int:nc_id>/', views.detalle_no_conformidad, name='detalle_no_conformidad'),

    path('calidad/tolerancias/', views.lista_tolerancias, name='lista_tolerancias'),
    path('calidad/tolerancias/nueva/', views.crear_tolerancia, name='crear_tolerancia'),
    path('calidad/tolerancias/<int:tolerancia_id>/editar/', views.editar_tolerancia, name='editar_tolerancia'),
]
