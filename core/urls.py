from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

handler404 = 'django.views.defaults.page_not_found'
handler500 = 'django.views.defaults.server_error'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('dashboard.urls')),
    path('', include('inventario.urls')),
    path('', include('produccion.urls')),
    path('', include('materia_terminada.urls')),
    path('', include('reportes.urls')),
]

# 👇 ESTO ES LO QUE PERMITE VER PDFs
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)