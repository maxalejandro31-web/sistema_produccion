"""Tests de la instalación como programa de escritorio (core/pwa.py) y del
regreso a la pantalla pedida después del login (lo usan los accesos directos
de la app instalada)."""
import json

from django.contrib.auth.models import User
from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse

from dashboard.models import ConfiguracionEmpresa


class ManifestTests(TestCase):
    def test_manifest_es_publico_y_valido(self):
        # El navegador pide el manifest SIN la sesión del usuario: si
        # llevara login_required, la app nunca sería instalable.
        resp = self.client.get(reverse('pwa_manifest'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('application/manifest+json', resp['Content-Type'])
        data = json.loads(resp.content.decode('utf-8'))
        self.assertEqual(data['display'], 'standalone')
        self.assertEqual(data['start_url'], reverse('inicio'))
        self.assertEqual(data['scope'], '/')
        tamanos = {i['sizes'] for i in data['icons']}
        self.assertIn('192x192', tamanos)
        self.assertIn('512x512', tamanos)

    def test_manifest_usa_nombre_de_la_configuracion_de_empresa(self):
        config = ConfiguracionEmpresa.get()
        config.nombre_empresa = 'MAQUILAS Y SERVICIOS JC'
        config.save()
        data = json.loads(self.client.get(reverse('pwa_manifest')).content.decode('utf-8'))
        self.assertEqual(data['name'], 'MAQUILAS Y SERVICIOS JC')
        self.assertLessEqual(len(data['short_name']), 20)

    def test_iconos_del_manifest_existen(self):
        for nombre in ['pwa/icon-192.png', 'pwa/icon-512.png', 'pwa/icon-maskable-512.png',
                       'pwa/favicon.ico', 'pwa/favicon-32.png', 'pwa/apple-touch-icon.png']:
            self.assertIsNotNone(finders.find(nombre), nombre)

    def test_accesos_directos_apuntan_a_pantallas_reales(self):
        data = json.loads(self.client.get(reverse('pwa_manifest')).content.decode('utf-8'))
        for atajo in data['shortcuts']:
            resp = self.client.get(atajo['url'])
            # Sin sesión deben mandar al login (302), nunca un 404.
            self.assertEqual(resp.status_code, 302, atajo['url'])


class ServiceWorkerTests(TestCase):
    def test_sw_es_publico_javascript_en_la_raiz_y_sin_cache(self):
        resp = self.client.get(reverse('pwa_sw'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(reverse('pwa_sw'), '/sw.js')
        self.assertIn('application/javascript', resp['Content-Type'])
        self.assertIn('no-cache', resp['Cache-Control'])
        js = resp.content.decode('utf-8')
        self.assertIn(reverse('pwa_offline'), js)

    def test_sw_solo_intercepta_navegaciones_get(self):
        # Garantía de seguridad: formularios (POST), descargas, polling,
        # etc. nunca pasan por la caché del service worker.
        js = self.client.get(reverse('pwa_sw')).content.decode('utf-8')
        self.assertIn("req.mode !== 'navigate' || req.method !== 'GET'", js)

    def test_pagina_sin_conexion_es_publica(self):
        resp = self.client.get(reverse('pwa_offline'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Sin conexión')


class EtiquetasPwaEnPantallasTests(TestCase):
    def test_login_incluye_manifest_y_registro_del_sw(self):
        resp = self.client.get(reverse('login'))
        self.assertContains(resp, 'rel="manifest"')
        self.assertContains(resp, reverse('pwa_sw'))

    def test_pantallas_internas_incluyen_manifest_y_boton_instalar(self):
        user = User.objects.create_user('pwa_user', password='pass12345', is_superuser=True)
        self.client.force_login(user)
        resp = self.client.get(reverse('inicio'))
        self.assertContains(resp, 'rel="manifest"')
        self.assertContains(resp, 'id="btnInstalarApp"')


class LoginRegresaAPantallaPedidaTests(TestCase):
    def setUp(self):
        User.objects.create_user('login_next', password='pass12345', is_superuser=True)

    def test_login_regresa_a_next_interno(self):
        resp = self.client.post(reverse('login') + '?next=/captura/',
                                {'username': 'login_next', 'password': 'pass12345'})
        self.assertRedirects(resp, '/captura/', fetch_redirect_response=False)

    def test_login_ignora_next_externo(self):
        resp = self.client.post(reverse('login') + '?next=https://sitio-malicioso.com/',
                                {'username': 'login_next', 'password': 'pass12345'})
        self.assertRedirects(resp, reverse('inicio'), fetch_redirect_response=False)

    def test_login_sin_next_va_al_dashboard(self):
        resp = self.client.post(reverse('login'), {'username': 'login_next', 'password': 'pass12345'})
        self.assertRedirects(resp, reverse('inicio'), fetch_redirect_response=False)
