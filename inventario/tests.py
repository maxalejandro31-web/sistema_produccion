"""Tests de inventario: ciclo de vida de MateriaPrima/MovimientoMP, conversión
de unidades de espesor, validación de formularios y permisos por rol en las
pantallas de salida/movimiento de MP.

Cubren en particular las correcciones hechas en auditorías anteriores de este
sistema (para que no se vuelvan a romper sin darnos cuenta): el TOCTOU de
dar_salida_mp, el revertir estado 'Terminado' -> 'En Proceso' con un
AJUSTE_POSITIVO, y el permiso de Capturista para dar salidas de MP.
"""
import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.factories import crear_usuario_con_rol, crear_cliente, crear_mp

from .forms import MovimientoMPForm, RegistrarMovimientoForm
from .models import MateriaPrima, MovimientoMP


class MovimientoMPLifecycleTests(TestCase):
    """MovimientoMP.save() es quien mantiene sincronizado
    MateriaPrima.peso_restante/estado — es el corazón del control de
    inventario de materia prima."""

    def setUp(self):
        self.mp = crear_mp(peso=1000)

    def test_entrada_incrementa_peso_restante(self):
        MovimientoMP.objects.create(mp=self.mp, tipo_movimiento='ENTRADA', peso=Decimal('200'))
        self.mp.refresh_from_db()
        self.assertEqual(self.mp.peso_restante, Decimal('1200.00'))

    def test_consumo_decrementa_peso_restante_y_pasa_a_en_proceso(self):
        MovimientoMP.objects.create(mp=self.mp, tipo_movimiento='CONSUMO', peso=Decimal('300'))
        self.mp.refresh_from_db()
        self.assertEqual(self.mp.peso_restante, Decimal('700.00'))
        self.assertEqual(self.mp.estado, 'En Proceso')

    def test_consumir_todo_el_peso_marca_terminado(self):
        MovimientoMP.objects.create(mp=self.mp, tipo_movimiento='CONSUMO', peso=Decimal('1000'))
        self.mp.refresh_from_db()
        self.assertEqual(self.mp.peso_restante, Decimal('0.00'))
        self.assertEqual(self.mp.estado, 'Terminado')

    def test_consumo_nunca_deja_peso_restante_negativo(self):
        MovimientoMP.objects.create(mp=self.mp, tipo_movimiento='CONSUMO', peso=Decimal('5000'))
        self.mp.refresh_from_db()
        self.assertEqual(self.mp.peso_restante, Decimal('0.00'))

    def test_ajuste_positivo_revierte_terminado_a_en_proceso(self):
        # Regresión: antes de la corrección, un AJUSTE_POSITIVO sobre una MP
        # ya 'Terminado' le devolvía peso pero la dejaba con estado
        # 'Terminado' para siempre, desapareciendo de los filtros
        # Disponible/En Proceso aunque volviera a tener material utilizable.
        MovimientoMP.objects.create(mp=self.mp, tipo_movimiento='CONSUMO', peso=Decimal('1000'))
        self.mp.refresh_from_db()
        self.assertEqual(self.mp.estado, 'Terminado')

        MovimientoMP.objects.create(mp=self.mp, tipo_movimiento='AJUSTE_POSITIVO', peso=Decimal('150'))
        self.mp.refresh_from_db()
        self.assertEqual(self.mp.peso_restante, Decimal('150.00'))
        self.assertEqual(self.mp.estado, 'En Proceso')

    def test_traspaso_actualiza_ubicacion_destino(self):
        MovimientoMP.objects.create(
            mp=self.mp, tipo_movimiento='TRASPASO', peso=Decimal('0'),
            ubicacion_destino='Patio B',
        )
        self.mp.refresh_from_db()
        self.assertEqual(self.mp.ubicacion, 'Patio B')


class EspesorConversionTests(TestCase):
    """MateriaPrima.espesor_mm es la fuente de verdad para comparar espesores
    entre distintas unidades de captura (mils/mm/pulg/calibre)."""

    def test_pulgadas_a_mm(self):
        mp = crear_mp(espesor_valor=Decimal('0.035'), unidad_espesor='pulg')
        self.assertAlmostEqual(mp.espesor_mm, 0.889, places=3)

    def test_mils_a_mm(self):
        mp = crear_mp(espesor_valor=Decimal('35'), unidad_espesor='mils')
        self.assertAlmostEqual(mp.espesor_mm, 0.889, places=3)

    def test_mm_se_queda_igual(self):
        mp = crear_mp(espesor_valor=Decimal('0.89'), unidad_espesor='mm')
        self.assertEqual(mp.espesor_mm, 0.89)

    def test_espesor_mils_calculado_desde_mm_sin_importar_unidad_original(self):
        mp = crear_mp(espesor_valor=Decimal('0.889'), unidad_espesor='mm')
        self.assertAlmostEqual(mp.espesor_mils, 35.0, places=0)


class MovimientoFormsValidationTests(TestCase):
    """clean_peso en ambos formularios: un peso <= 0 debe rechazarse, porque
    si se cuela invierte el efecto del movimiento (una 'salida' negativa le
    SUMA peso a la MP en vez de restarle)."""

    def setUp(self):
        self.mp = crear_mp(peso=500)

    def test_movimientomp_form_rechaza_peso_negativo(self):
        form = MovimientoMPForm(data={
            'mp': self.mp.pk, 'tipo_movimiento': 'CONSUMO', 'peso': '-10',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('peso', form.errors)

    def test_movimientomp_form_rechaza_peso_cero(self):
        form = MovimientoMPForm(data={
            'mp': self.mp.pk, 'tipo_movimiento': 'CONSUMO', 'peso': '0',
        })
        self.assertFalse(form.is_valid())

    def test_movimientomp_form_acepta_peso_positivo(self):
        form = MovimientoMPForm(data={
            'mp': self.mp.pk, 'tipo_movimiento': 'CONSUMO', 'peso': '10',
        })
        self.assertTrue(form.is_valid())

    def test_registrarmovimiento_form_rechaza_peso_negativo(self):
        form = RegistrarMovimientoForm(data={'tipo_movimiento': 'MERMA', 'peso': '-5'})
        self.assertFalse(form.is_valid())


class DarSalidaMPPermisosTests(TestCase):
    """Quién puede entrar a /mp/<id>/salida/. Cubre el permiso que se le
    dio a Capturista y confirma que registrar_movimiento (más amplio) NO se
    tocó de más."""

    def setUp(self):
        self.mp = crear_mp(peso=500)

    def _get_salida(self, user):
        self.client.force_login(user)
        return self.client.get(reverse('dar_salida_mp', args=[self.mp.id]))

    def test_capturista_puede_entrar_a_dar_salida(self):
        user = crear_usuario_con_rol('capturista1', 'Capturista')
        resp = self._get_salida(user)
        self.assertEqual(resp.status_code, 200)

    def test_almacen_puede_entrar_a_dar_salida(self):
        user = crear_usuario_con_rol('almacen1', 'Almacen')
        resp = self._get_salida(user)
        self.assertEqual(resp.status_code, 200)

    def test_operador_no_puede_entrar_a_dar_salida(self):
        user = crear_usuario_con_rol('operador1', 'Operador')
        resp = self._get_salida(user)
        self.assertEqual(resp.status_code, 302)  # redirige a detalle_mp con error

    def test_capturista_no_puede_entrar_a_registrar_movimiento(self):
        user = crear_usuario_con_rol('capturista2', 'Capturista')
        self.client.force_login(user)
        resp = self.client.get(reverse('registrar_movimiento', args=[self.mp.id]))
        self.assertEqual(resp.status_code, 302)

    def test_capturista_puede_ver_detalle_mp(self):
        user = crear_usuario_con_rol('capturista3', 'Capturista')
        self.client.force_login(user)
        resp = self.client.get(reverse('detalle_mp', args=[self.mp.id]))
        self.assertEqual(resp.status_code, 200)


class DarSalidaMPFlujoTests(TestCase):
    """El registro real de una salida de MP: valida peso, descuenta
    peso_restante, y no deja pasar un peso mayor al disponible."""

    def setUp(self):
        self.mp = crear_mp(peso=500)
        self.user = crear_usuario_con_rol('almacen_flujo', 'Almacen')
        self.client.force_login(self.user)

    def test_salida_exitosa_descuenta_peso_restante(self):
        resp = self.client.post(
            reverse('dar_salida_mp', args=[self.mp.id]),
            {'peso': '120', 'cliente_id': '', 'fecha_salida': '', 'observaciones': ''},
            follow=True,
        )
        self.mp.refresh_from_db()
        self.assertEqual(self.mp.peso_restante, Decimal('380.00'))
        self.assertTrue(MovimientoMP.objects.filter(mp=self.mp, tipo_movimiento='SALIDA').exists())

    def test_salida_no_puede_superar_peso_restante(self):
        resp = self.client.post(
            reverse('dar_salida_mp', args=[self.mp.id]),
            {'peso': '9999', 'cliente_id': '', 'fecha_salida': '', 'observaciones': ''},
        )
        self.mp.refresh_from_db()
        self.assertEqual(self.mp.peso_restante, Decimal('500.00'))
        self.assertFalse(MovimientoMP.objects.filter(mp=self.mp, tipo_movimiento='SALIDA').exists())

    def test_salida_rechaza_peso_no_positivo(self):
        resp = self.client.post(
            reverse('dar_salida_mp', args=[self.mp.id]),
            {'peso': '0', 'cliente_id': '', 'fecha_salida': '', 'observaciones': ''},
        )
        self.mp.refresh_from_db()
        self.assertEqual(self.mp.peso_restante, Decimal('500.00'))


class ListaMpFiltroCobroTests(TestCase):
    """El filtro `?cobro=vencido`/`?cobro=por_vencer` de lista_mp es a donde
    llevan los links "Ver MP" de las alertas de cobro por estancia — antes
    solo el CONTEO de la alerta excluía el material propio de la maquila,
    pero la lista filtrada sí lo incluía, así que el número de la alerta no
    coincidía con lo que se veía al hacer clic."""

    def setUp(self):
        self.user = User.objects.create_user('lista_mp_user', password='pass12345')
        self.client.force_login(self.user)
        self.propia = crear_cliente(nombre='MAQUILAS Y SERVICIOS JC')
        self.externo = crear_cliente(nombre='Cliente Externo SA')

    def test_cobro_vencido_excluye_material_propio(self):
        hace_40_dias = timezone.localdate() - datetime.timedelta(days=40)
        crear_mp(numero_mp='MP-PROPIA-V', cliente=self.propia, fecha_entrada=hace_40_dias)
        crear_mp(numero_mp='MP-CLIENTE-V', cliente=self.externo, fecha_entrada=hace_40_dias)

        resp = self.client.get(reverse('lista_mp'), {'cobro': 'vencido'})
        numeros = [mp.numero_mp for mp in resp.context['materias_primas']]
        self.assertIn('MP-CLIENTE-V', numeros)
        self.assertNotIn('MP-PROPIA-V', numeros)

    def test_cobro_por_vencer_excluye_material_propio(self):
        hace_25_dias = timezone.localdate() - datetime.timedelta(days=25)
        crear_mp(numero_mp='MP-PROPIA-PV', cliente=self.propia, fecha_entrada=hace_25_dias)
        crear_mp(numero_mp='MP-CLIENTE-PV', cliente=self.externo, fecha_entrada=hace_25_dias)

        resp = self.client.get(reverse('lista_mp'), {'cobro': 'por_vencer'})
        numeros = [mp.numero_mp for mp in resp.context['materias_primas']]
        self.assertIn('MP-CLIENTE-PV', numeros)
        self.assertNotIn('MP-PROPIA-PV', numeros)
