from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from core import pwa

handler404 = 'django.views.defaults.page_not_found'
handler500 = 'django.views.defaults.server_error'

urlpatterns = [
    path('admin/', admin.site.urls),
    # Instalación como programa de escritorio (ver core/pwa.py). sw.js tiene
    # que estar en la raíz del sitio para poder cubrir todas las pantallas.
    path('manifest.webmanifest', pwa.manifest, name='pwa_manifest'),
    path('sw.js', pwa.service_worker, name='pwa_sw'),
    path('offline/', pwa.offline, name='pwa_offline'),
    path('', include('dashboard.urls')),
    path('', include('inventario.urls')),
    path('', include('produccion.urls')),
    path('', include('materia_terminada.urls')),
    path('', include('reportes.urls')),
    path('', include('calidad.urls')),
]

# 👇 ESTO ES LO QUE PERMITE VER PDFs
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)