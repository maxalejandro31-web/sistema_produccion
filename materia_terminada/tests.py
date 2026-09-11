"""Tests de materia_terminada: bloqueo de no-conformidades críticas al
embarcar, permisos por rol para crear salidas (incluyendo el permiso que se
le dio a Capturista), y que crear_salida no ofrezca para embarcar una cinta
que sigue comprometida con una orden de fleje activa.
"""
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from core.factories import crear_usuario_con_rol, crear_orden_slitter, crear_orden_fleje

from calidad.models import NoConformidad
from .models import ProductoTerminado, Salida


class TieneNCCriticaAbiertaTests(TestCase):
    def setUp(self):
        orden = crear_orden_slitter(peso_usado=100, terminar=True)
        self.pt = ProductoTerminado.objects.get(orden=orden)

    def test_sin_no_conformidades_no_bloquea(self):
        self.assertFalse(self.pt.tiene_nc_critica_abierta)

    def test_nc_menor_no_bloquea(self):
        NoConformidad.objects.create(producto_terminado=self.pt, severidad='menor', estado='abierta', descripcion='rayón leve')
        self.assertFalse(self.pt.tiene_nc_critica_abierta)

    def test_nc_critica_abierta_bloquea(self):
        NoConformidad.objects.create(producto_terminado=self.pt, severidad='critica', estado='abierta', descripcion='fuera de norma')
        self.assertTrue(self.pt.tiene_nc_critica_abierta)

    def test_nc_critica_cerrada_no_bloquea(self):
        NoConformidad.objects.create(producto_terminado=self.pt, severidad='critica', estado='cerrada', descripcion='ya resuelta')
        self.assertFalse(self.pt.tiene_nc_critica_abierta)


class CambiarEstadoPTPermisosYBloqueoTests(TestCase):
    def setUp(self):
        orden = crear_orden_slitter(peso_usado=100, terminar=True)
        self.pt = ProductoTerminado.objects.get(orden=orden)

    def test_capturista_no_puede_cambiar_estado_pt(self):
        user = crear_usuario_con_rol('capturista_cep', 'Capturista')
        self.client.force_login(user)
        resp = self.client.get(reverse('cambiar_estado_pt', args=[self.pt.id, 'vendido']))
        self.assertEqual(resp.status_code, 403)

    def test_admin_puede_marcar_vendido(self):
        user = crear_usuario_con_rol('admin_cep', 'Administrador')
        self.client.force_login(user)
        self.client.get(reverse('cambiar_estado_pt', args=[self.pt.id, 'vendido']), follow=True)
        self.pt.refresh_from_db()
        self.assertEqual(self.pt.estado, 'vendido')

    def test_no_conformidad_critica_bloquea_marcar_vendido(self):
        NoConformidad.objects.create(producto_terminado=self.pt, severidad='critica', estado='abierta', descripcion='defecto')
        user = crear_usuario_con_rol('admin_cep2', 'Administrador')
        self.client.force_login(user)
        self.client.get(reverse('cambiar_estado_pt', args=[self.pt.id, 'vendido']), follow=True)
        self.pt.refresh_from_db()
        self.assertEqual(self.pt.estado, 'en_almacen')


class CrearSalidaPermisosTests(TestCase):
    def test_capturista_puede_entrar_a_crear_salida(self):
        user = crear_usuario_con_rol('capturista_cs', 'Capturista')
        self.client.force_login(user)
        resp = self.client.get(reverse('crear_salida'))
        self.assertEqual(resp.status_code, 200)

    def test_operador_no_puede_entrar_a_crear_salida(self):
        user = crear_usuario_con_rol('operador_cs', 'Operador')
        self.client.force_login(user)
        resp = self.client.get(reverse('crear_salida'))
        self.assertEqual(resp.status_code, 403)


class CrearSalidaFlujoTests(TestCase):
    def setUp(self):
        self.user = crear_usuario_con_rol('coord_cs', 'Coordinador')
        self.client.force_login(self.user)

    def _pt_disponible(self, peso=100):
        orden = crear_orden_slitter(peso_usado=peso, terminar=True)
        return ProductoTerminado.objects.get(orden=orden)

    def test_crear_salida_marca_pt_embarcado_y_calcula_peso_total(self):
        pt = self._pt_disponible(peso=120)
        resp = self.client.post(reverse('crear_salida'), {
            'tipo': 'maquila', 'cliente': '', 'fecha_salida': '', 'observaciones': '',
            'pt_seleccionados': [str(pt.id)],
        }, follow=True)
        pt.refresh_from_db()
        self.assertEqual(pt.estado, 'embarcado')
        salida = Salida.objects.latest('id')
        self.assertEqual(salida.peso_total, Decimal('120.00'))

    def test_cinta_con_orden_fleje_activa_no_se_puede_dar_de_salida(self):
        pt = self._pt_disponible(peso=100)
        crear_orden_fleje(pt_origen=pt, peso_usado=30, terminar=False)  # orden pendiente/activa

        resp = self.client.get(reverse('crear_salida'))
        self.assertNotIn(pt, resp.context['pt_disponibles'])

        resp = self.client.post(reverse('crear_salida'), {
            'tipo': 'maquila', 'cliente': '', 'fecha_salida': '', 'observaciones': '',
            'pt_seleccionados': [str(pt.id)],
        }, follow=True)
        pt.refresh_from_db()
        self.assertEqual(pt.estado, 'en_almacen')
        self.assertFalse(Salida.objects.exists())

    def test_pt_con_nc_critica_no_se_incluye_en_la_salida(self):
        pt = self._pt_disponible(peso=100)
        NoConformidad.objects.create(producto_terminado=pt, severidad='critica', estado='abierta', descripcion='defecto')

        resp = self.client.get(reverse('crear_salida'))
        self.assertNotIn(pt, resp.context['pt_disponibles'])
        self.assertIn(pt, resp.context['pt_bloqueados_nc'])

        self.client.post(reverse('crear_salida'), {
            'tipo': 'maquila', 'cliente': '', 'fecha_salida': '', 'observaciones': '',
            'pt_seleccionados': [str(pt.id)],
        }, follow=True)
        pt.refresh_from_db()
        self.assertEqual(pt.estado, 'en_almacen')
        self.assertFalse(Salida.objects.exists())
