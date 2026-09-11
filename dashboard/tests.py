"""Tests de dashboard: que las acciones administrativas sensibles (crear/
editar usuario, cambiar rol, cambiar contraseña, activar/desactivar,
configuración de empresa) queden registradas en HistorialCambio — antes de
esta corrección no quedaba ningún rastro de quién hizo estos cambios.

También cubre `dashboard/alertas.py::obtener_alertas()`, la fuente única de
las alertas que muestran tanto las tarjetas del dashboard como la campanita
del navbar (antes cada una las calculaba por su cuenta y se desincronizaban),
y el endpoint `alertas_json` que usa el polling de la campanita.
"""
import datetime

from django.contrib.auth.models import User, Group
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.factories import crear_usuario_con_rol, crear_cliente, crear_mp, crear_orden_slitter

from .alertas import obtener_alertas
from .models import ConfiguracionEmpresa, HistorialCambio


class HistorialDeAccionesDeUsuarioTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user('admin_hist', password='pass12345', is_superuser=True, is_staff=True)
        self.client.force_login(self.admin)

    def test_crear_usuario_queda_en_historial(self):
        self.client.post(reverse('crear_usuario'), {
            'username': 'nuevo1', 'password': 'clave12345', 'password2': 'clave12345',
        })
        nuevo = User.objects.get(username='nuevo1')
        self.assertTrue(
            HistorialCambio.objects.filter(tipo_objeto='Usuario', objeto_id=nuevo.id, accion='CREAR').exists()
        )

    def test_cambiar_rol_queda_en_historial(self):
        grupo, _ = Group.objects.get_or_create(name='Operador')
        otro = User.objects.create_user('otro1', password='pass12345')
        self.client.post(reverse('editar_usuario', args=[otro.id]), {
            'accion': 'cambiar_rol', 'grupo': str(grupo.id), 'es_admin': '',
        })
        self.assertTrue(
            HistorialCambio.objects.filter(tipo_objeto='Usuario', objeto_id=otro.id, accion='EDITAR').exists()
        )

    def test_cambiar_password_queda_en_historial_sin_guardar_la_password(self):
        otro = User.objects.create_user('otro2', password='pass12345')
        self.client.post(reverse('editar_usuario', args=[otro.id]), {
            'accion': 'cambiar_password', 'nueva_password': 'nuevaclave1', 'confirmar_password': 'nuevaclave1',
        })
        registro = HistorialCambio.objects.filter(tipo_objeto='Usuario', objeto_id=otro.id, accion='EDITAR').first()
        self.assertIsNotNone(registro)
        self.assertNotIn('nuevaclave1', registro.descripcion)

    def test_toggle_activo_queda_en_historial(self):
        otro = User.objects.create_user('otro3', password='pass12345')
        self.client.post(reverse('editar_usuario', args=[otro.id]), {'accion': 'toggle_activo'})
        self.assertTrue(
            HistorialCambio.objects.filter(tipo_objeto='Usuario', objeto_id=otro.id, accion='ESTADO').exists()
        )

    def test_configuracion_empresa_queda_en_historial(self):
        config = ConfiguracionEmpresa.get()
        self.client.post(reverse('configuracion_empresa'), {
            'nombre_empresa': 'Nuevo Nombre S.A.', 'slogan': '', 'logo_url': '',
        })
        self.assertTrue(
            HistorialCambio.objects.filter(tipo_objeto='ConfiguracionEmpresa', objeto_id=config.id, accion='EDITAR').exists()
        )


class ObtenerAlertasTests(TestCase):
    """`obtener_alertas()` es ahora la única fuente de las 5 categorías de
    alerta (antes la campanita del navbar calculaba solo 3 por su cuenta, de
    forma independiente, y se desincronizaba de las tarjetas del dashboard).
    Cada test cubre una categoría: que dispare con el dato correcto, que NO
    dispare cuando no aplica, y que la URL generada realmente filtre al mismo
    subconjunto que generó el conteo."""

    def setUp(self):
        # mapear_baselines_rendimiento() cachea su resultado (settings.py no
        # define CACHES, así que es el LocMemCache de proceso, compartido
        # entre tests) — sin este clear(), un test de anomalías podría leer
        # el baseline calculado por el test anterior.
        cache.clear()

    def test_sin_datos_no_hay_alertas(self):
        self.assertEqual(obtener_alertas(), [])

    def test_mp_cobro_vencido_excluye_material_propio(self):
        propia = crear_cliente(nombre='MAQUILAS Y SERVICIOS JC')
        externo = crear_cliente(nombre='Cliente Externo SA')
        hace_40_dias = timezone.localdate() - datetime.timedelta(days=40)
        crear_mp(numero_mp='MP-PROPIA-1', cliente=propia, fecha_entrada=hace_40_dias)
        crear_mp(numero_mp='MP-CLIENTE-1', cliente=externo, fecha_entrada=hace_40_dias)

        alertas = obtener_alertas()
        criticas = [a for a in alertas if a['tipo'] == 'critica']
        self.assertEqual(len(criticas), 1)
        self.assertEqual(criticas[0]['count'], 1)
        self.assertIn('cobro=vencido', criticas[0]['url'])

    def test_mp_por_vencer_dentro_de_7_dias(self):
        externo = crear_cliente(nombre='Cliente Externo SA')
        hace_25_dias = timezone.localdate() - datetime.timedelta(days=25)
        crear_mp(numero_mp='MP-POR-VENCER-1', cliente=externo, fecha_entrada=hace_25_dias)

        alertas = obtener_alertas()
        avisos = [a for a in alertas if a['tipo'] == 'aviso']
        self.assertEqual(len(avisos), 1)
        self.assertEqual(avisos[0]['count'], 1)
        self.assertIn('cobro=por_vencer', avisos[0]['url'])

    def test_mp_recien_entrada_no_genera_ninguna_alerta_de_cobro(self):
        externo = crear_cliente(nombre='Cliente Externo SA')
        crear_mp(numero_mp='MP-NUEVA-1', cliente=externo, fecha_entrada=timezone.localdate())

        alertas = obtener_alertas()
        self.assertFalse(any(a['tipo'] in ('critica', 'aviso') for a in alertas))

    def test_orden_urgente_pendiente_genera_alerta_info(self):
        orden = crear_orden_slitter()
        orden.prioridad = 'urgente'
        orden.save()

        alertas = obtener_alertas()
        infos = [a for a in alertas if a['tipo'] == 'info']
        self.assertEqual(len(infos), 1)
        self.assertEqual(infos[0]['count'], 1)
        self.assertIn('urgentes=1', infos[0]['url'])

    def test_orden_urgente_terminada_no_cuenta(self):
        orden = crear_orden_slitter(terminar=True)
        orden.prioridad = 'urgente'
        orden.save()

        alertas = obtener_alertas()
        self.assertFalse(any(a['tipo'] == 'info' for a in alertas))

    def test_rollo_terminado_con_rendimiento_bajo_genera_alerta_rendimiento(self):
        cliente = crear_cliente()
        mp = crear_mp(cliente=cliente, peso=1000)
        orden = crear_orden_slitter(mp=mp, cliente=cliente, peso_usado=1000)
        # crear_orden_slitter() deja peso_producido = peso_usado (100%) por
        # defecto — se fuerza aquí un rendimiento total bajo (80%, por
        # debajo del umbral de 96.5% en analitica.py) y se marca el rollo
        # como Terminado, que es lo único que mapa_rendimiento_rollos_
        # terminados() considera.
        orden.peso_producido = 800
        orden.save()
        mp.__class__.objects.filter(pk=mp.pk).update(estado='Terminado')

        alertas = obtener_alertas()
        rendimiento = [a for a in alertas if a['tipo'] == 'rendimiento' and 'rendimiento_bajo=1' in a['url']]
        self.assertEqual(len(rendimiento), 1)
        self.assertEqual(rendimiento[0]['count'], 1)

    def test_rollo_terminado_con_buen_rendimiento_no_genera_alerta(self):
        cliente = crear_cliente()
        mp = crear_mp(cliente=cliente, peso=1000)
        orden = crear_orden_slitter(mp=mp, cliente=cliente, peso_usado=1000)
        orden.peso_producido = 995
        orden.save()
        mp.__class__.objects.filter(pk=mp.pk).update(estado='Terminado')

        alertas = obtener_alertas()
        self.assertFalse(any(a['tipo'] == 'rendimiento' and 'rendimiento_bajo=1' in a['url'] for a in alertas))

    def test_orden_con_rendimiento_anomalo_vs_su_historico(self):
        cliente = crear_cliente()
        # Baseline: 5 órdenes terminadas, mismo tipo_proceso + material,
        # todas al 98% (MUESTRA_MINIMA en analitica.py es 5).
        for i in range(5):
            mp_base = crear_mp(cliente=cliente, peso=1000, material='Acero Galvanizado')
            orden_base = crear_orden_slitter(mp=mp_base, cliente=cliente, peso_usado=500)
            orden_base.peso_producido = 490  # 98%
            orden_base.estado = 'terminado'
            orden_base.save()
        # La orden anómala: mismo tipo_proceso/material, muy por debajo del
        # promedio histórico (~98%) y dentro de los últimos 30 días.
        mp_mala = crear_mp(cliente=cliente, peso=1000, material='Acero Galvanizado')
        orden_mala = crear_orden_slitter(mp=mp_mala, cliente=cliente, peso_usado=500)
        orden_mala.peso_producido = 350  # 70%
        orden_mala.estado = 'terminado'
        orden_mala.save()

        alertas = obtener_alertas()
        anomalas = [a for a in alertas if a['tipo'] == 'rendimiento' and 'anomalia=bajo' in a['url']]
        self.assertEqual(len(anomalas), 1)
        self.assertEqual(anomalas[0]['count'], 1)

    def test_orden_dentro_del_promedio_no_es_anomalia(self):
        cliente = crear_cliente()
        for i in range(6):
            mp_base = crear_mp(cliente=cliente, peso=1000, material='Acero Galvanizado')
            orden_base = crear_orden_slitter(mp=mp_base, cliente=cliente, peso_usado=500)
            orden_base.peso_producido = 490  # 98%, todas iguales
            orden_base.estado = 'terminado'
            orden_base.save()

        alertas = obtener_alertas()
        self.assertFalse(any(a['tipo'] == 'rendimiento' and 'anomalia=bajo' in a['url'] for a in alertas))


class AlertasJsonEndpointTests(TestCase):
    """El endpoint que usa el polling de la campanita (`/alertas/actuales/`)
    — debe exigir sesión iniciada y devolver exactamente la misma cuenta que
    `obtener_alertas()`, para que lo que se ve al abrir la campana en vivo
    coincida con lo que se calculó al cargar la página."""

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user('alertas_user', password='pass12345')

    def test_requiere_login(self):
        resp = self.client.get(reverse('alertas_json'))
        self.assertNotEqual(resp.status_code, 200)

    def test_devuelve_count_y_items_consistentes_con_obtener_alertas(self):
        externo = crear_cliente(nombre='Cliente Externo SA')
        crear_mp(numero_mp='MP-1', cliente=externo, fecha_entrada=timezone.localdate() - datetime.timedelta(days=40))

        self.client.force_login(self.user)
        resp = self.client.get(reverse('alertas_json'))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        esperado = obtener_alertas()
        self.assertEqual(data['count'], sum(a['count'] for a in esperado))
        self.assertEqual(len(data['items']), len(esperado))
        for item, alerta in zip(data['items'], esperado):
            self.assertEqual(item['tipo'], alerta['tipo'])
            self.assertEqual(item['url'], alerta['url'])
