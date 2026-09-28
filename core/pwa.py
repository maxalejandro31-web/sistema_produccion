"""Soporte para instalar el sistema como programa de escritorio (PWA).

Con esto, desde Edge o Chrome aparece la opción "Instalar aplicación": el
sistema queda con su ícono en el escritorio / menú Inicio / barra de tareas y
se abre en su propia ventana, sin pestañas ni barra de dirección. Por dentro
sigue siendo exactamente el mismo sistema en Render (no hay nada que
actualizar en cada computadora).

Son tres vistas públicas (el navegador las pide SIN sesión iniciada, así que
no pueden llevar @login_required) y ninguna expone datos del negocio:

- manifest: nombre, colores, íconos y accesos directos de la app.
- service_worker: solo sirve para mostrar una pantalla amable de "sin
  conexión" en vez del error del navegador. NO guarda en caché ninguna
  pantalla del sistema (siempre se piden en vivo al servidor), para que
  nunca se muestren datos viejos ni queden datos de un usuario guardados
  en la computadora.
- offline: esa pantalla de "sin conexión".
"""
import os

from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.templatetags.static import static
from django.urls import reverse
from django.views.decorators.cache import cache_control

COLOR_TEMA = '#1f2d3d'    # mismo azul marino del navbar
COLOR_FONDO = '#f4f6f8'   # mismo fondo gris claro del sistema

# Cambia en cada deploy de Render (RENDER_GIT_COMMIT es una variable que
# Render pone sola). Así el navegador detecta que hay una versión nueva del
# service worker y vuelve a guardar la pantalla de "sin conexión".
VERSION = (os.getenv('RENDER_GIT_COMMIT') or 'local')[:12]


def _nombre_empresa():
    try:
        from dashboard.models import ConfiguracionEmpresa
        return ConfiguracionEmpresa.get().nombre_empresa
    except Exception:
        return 'Sistema Control de Producción'


@cache_control(max_age=3600, public=True)
def manifest(request):
    nombre = _nombre_empresa()
    data = {
        'id': '/',
        'name': nombre,
        'short_name': nombre if len(nombre) <= 20 else 'Producción',
        'description': 'Control de materia prima, producción, producto terminado y reportes.',
        'lang': 'es-MX',
        'dir': 'ltr',
        'start_url': reverse('inicio'),
        'scope': '/',
        'display': 'standalone',
        'background_color': COLOR_FONDO,
        'theme_color': COLOR_TEMA,
        'icons': [
            {'src': static('pwa/icon-192.png'), 'sizes': '192x192', 'type': 'image/png', 'purpose': 'any'},
            {'src': static('pwa/icon-512.png'), 'sizes': '512x512', 'type': 'image/png', 'purpose': 'any'},
            {'src': static('pwa/icon-maskable-512.png'), 'sizes': '512x512', 'type': 'image/png', 'purpose': 'maskable'},
        ],
        # Aparecen al dar clic derecho sobre el ícono en la barra de tareas
        # de Windows (y en el menú Inicio), como en cualquier programa.
        'shortcuts': [
            {'name': 'Capturar orden', 'url': reverse('captura_orden'),
             'icons': [{'src': static('pwa/icon-192.png'), 'sizes': '192x192'}]},
            {'name': 'Capturar materia prima', 'url': reverse('captura_mp'),
             'icons': [{'src': static('pwa/icon-192.png'), 'sizes': '192x192'}]},
            {'name': 'Producto terminado', 'url': reverse('lista_pt'),
             'icons': [{'src': static('pwa/icon-192.png'), 'sizes': '192x192'}]},
            {'name': 'Reportes', 'url': reverse('reportes_index'),
             'icons': [{'src': static('pwa/icon-192.png'), 'sizes': '192x192'}]},
        ],
    }
    response = JsonResponse(data, json_dumps_params={'ensure_ascii': False})
    response['Content-Type'] = 'application/manifest+json; charset=utf-8'
    return response


# no-cache: el navegador siempre revisa si hay un service worker nuevo en
# cada visita, así los cambios de un deploy llegan sin esperar.
@cache_control(no_cache=True, max_age=0)
def service_worker(request):
    # render_to_string SIN request a propósito: así no corren los context
    # processors (el de alertas hace varias consultas) cada vez que el
    # navegador revisa si hay versión nueva de este archivo.
    js = render_to_string('pwa/sw.js', {
        'version': VERSION,
        'offline_url': reverse('pwa_offline'),
        'precache': [
            reverse('pwa_offline'),
            static('pwa/icon-192.png'),
        ],
    })
    response = HttpResponse(js, content_type='application/javascript; charset=utf-8')
    # El archivo vive en /sw.js (raíz), así que ya controla todo el sitio;
    # esto solo lo deja explícito.
    response['Service-Worker-Allowed'] = '/'
    return response


def offline(request):
    html = render_to_string('pwa/offline.html', {'nombre_empresa': _nombre_empresa()})
    return HttpResponse(html)
