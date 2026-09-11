"""Tests de producción: consumo de materia prima al capturar una orden,
generación automática de Producto Terminado vía signals, reapertura segura
de una orden ya terminada, y el filtrado de "cinta origen" en el formulario
de Fleje.

Estas son exactamente las áreas donde se encontraron y corrigieron bugs
reales en auditorías anteriores de este sistema (rollos de fleje partidos en
varios lotes, reabrir una orden terminada) — los tests fijan ese
comportamiento para que no se rompa de nuevo sin darnos cuenta.
"""
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from core.factories import (
    crear_usuario_con_rol, crear_cliente, crear_linea, crear_mp,
    crear_orden_slitter, crear_orden_fleje,
)

from inventario.models import MovimientoMP
from materia_terminada.models import ProductoTerminado, Salida, SalidaDetalle
from .forms import OrdenProduccionForm
from .models import OrdenProduccion, DetalleSlitter


class ConsumoDeMPTests(TestCase):
    """OrdenProduccion.save() es quien descuenta la MP consumida — vía un
    MovimientoMP tipo CONSUMO, para que quede historial y se reutilice la
    misma lógica de MovimientoMP.save()."""

    def test_crear_orden_descuenta_peso_de_la_mp(self):
        mp = crear_mp(peso=1000)
        orden = crear_orden_slitter(mp=mp, peso_usado=300)
        mp.refresh_from_db()
        self.assertEqual(mp.peso_restante, Decimal('700.00'))
        self.assertTrue(MovimientoMP.objects.filter(mp=mp, tipo_movimiento='CONSUMO', peso=300).exists())

    def test_no_deja_consumir_mas_peso_del_disponible(self):
        mp = crear_mp(peso=100)
        with self.assertRaises(ValueError):
            crear_orden_slitter(mp=mp, peso_usado=500)

    def test_editar_peso_usado_solo_ajusta_la_diferencia(self):
        mp = crear_mp(peso=1000)
        orden = crear_orden_slitter(mp=mp, peso_usado=300)
        mp.refresh_from_db()
        self.assertEqual(mp.peso_restante, Decimal('700.00'))

        orden.peso_usado = Decimal('350')
        orden.save()
        mp.refresh_from_db()
        # Solo se descuentan los 50 kg extra, no los 350 completos de nuevo.
        self.assertEqual(mp.peso_restante, Decimal('650.00'))

    def test_reducir_peso_usado_devuelve_la_diferencia(self):
        mp = crear_mp(peso=1000)
        orden = crear_orden_slitter(mp=mp, peso_usado=300)
        orden.peso_usado = Decimal('200')
        orden.save()
        mp.refresh_from_db()
        self.assertEqual(mp.peso_restante, Decimal('800.00'))

    def test_reasignar_mp_revierte_la_anterior_y_consume_la_nueva(self):
        mp_vieja = crear_mp(numero_mp='MP-VIEJA', peso=1000)
        mp_nueva = crear_mp(numero_mp='MP-NUEVA', peso=1000)
        orden = crear_orden_slitter(mp=mp_vieja, peso_usado=300)

        orden.mp = mp_nueva
        orden.save()

        mp_vieja.refresh_from_db()
        mp_nueva.refresh_from_db()
        self.assertEqual(mp_vieja.peso_restante, Decimal('1000.00'))
        self.assertEqual(mp_nueva.peso_restante, Decimal('700.00'))


class RendimientoTests(TestCase):
    def test_rendimiento_se_calcula_desde_peso_usado_y_producido(self):
        orden = crear_orden_slitter(peso_usado=100)
        orden.peso_producido = Decimal('95')
        orden.save()
        self.assertEqual(orden.rendimiento_porcentaje, Decimal('95.00'))

    def test_rendimiento_absurdo_se_deja_en_none(self):
        mp = crear_mp(peso=100000)
        orden = crear_orden_slitter(mp=mp, peso_usado=Decimal('0.01'))
        orden.peso_producido = Decimal('99999')
        orden.save()
        self.assertIsNone(orden.rendimiento_porcentaje)


class GeneracionAutomaticaDePTTests(TestCase):
    """El signal crear_producto_terminado genera el PT en cuanto la orden
    pasa a 'terminado' — un PT por corte en slitter."""

    def test_terminar_orden_slitter_genera_un_pt_por_corte(self):
        orden = crear_orden_slitter(peso_usado=300, cortes=[
            {'no_corte': 1, 'peso': 150}, {'no_corte': 2, 'peso': 150},
        ], terminar=True)
        pts = ProductoTerminado.objects.filter(orden=orden)
        self.assertEqual(pts.count(), 2)
        self.assertEqual(set(pts.values_list('peso_kg', flat=True)), {Decimal('150.00'), Decimal('150.00')})

    def test_terminar_dos_veces_no_duplica_el_pt(self):
        orden = crear_orden_slitter(peso_usado=100, terminar=True)
        self.assertEqual(ProductoTerminado.objects.filter(orden=orden).count(), 1)
        orden.observaciones = 'tocar la orden de nuevo sin cambiar estado'
        orden.save()
        self.assertEqual(ProductoTerminado.objects.filter(orden=orden).count(), 1)


class RolloFlejePartidoEnLotesTests(TestCase):
    """Regresión del bug "rollos de fleje partidos en 2+ lotes": una cinta
    se puede procesar en varias órdenes de fleje distintas hasta agotarla,
    y solo debe marcarse 'embarcado' cuando ya no le queda peso disponible
    (no en cuanto termina el PRIMER lote)."""

    def _crear_cinta(self, peso_kg=100):
        orden_origen = crear_orden_slitter(peso_usado=peso_kg, terminar=True)
        return ProductoTerminado.objects.get(orden=orden_origen)

    def test_cinta_no_se_marca_embarcada_si_queda_peso_disponible(self):
        cinta = self._crear_cinta(peso_kg=100)
        crear_orden_fleje(pt_origen=cinta, peso_usado=40, terminar=True)
        cinta.refresh_from_db()
        self.assertEqual(cinta.estado, 'en_almacen')
        self.assertEqual(cinta.peso_disponible_fleje, 60)

    def test_cinta_se_marca_embarcada_cuando_se_agota_en_varios_lotes(self):
        cinta = self._crear_cinta(peso_kg=100)
        crear_orden_fleje(pt_origen=cinta, peso_usado=40, terminar=True)
        crear_orden_fleje(pt_origen=cinta, peso_usado=60, terminar=True)
        cinta.refresh_from_db()
        self.assertEqual(cinta.estado, 'embarcado')
        self.assertEqual(cinta.peso_disponible_fleje, 0)

    def test_peso_consumido_fleje_suma_todas_las_ordenes(self):
        cinta = self._crear_cinta(peso_kg=100)
        crear_orden_fleje(pt_origen=cinta, peso_usado=30, terminar=True)
        crear_orden_fleje(pt_origen=cinta, peso_usado=20, terminar=False)  # pendiente, también cuenta
        self.assertEqual(cinta.peso_consumido_fleje, 50)


class ReabrirOrdenTerminadaTests(TestCase):
    """cambiar_estado view: reabrir una orden 'terminado' debe limpiar el PT
    auto-generado (y revertir la cinta origen si aplica), pero SOLO si ese
    PT todavía no se movió de verdad."""

    def setUp(self):
        self.user = crear_usuario_con_rol('admin_reabrir', 'Administrador')
        self.client.force_login(self.user)

    def test_reabrir_borra_el_pt_no_tocado(self):
        orden = crear_orden_slitter(peso_usado=100, terminar=True)
        pt = ProductoTerminado.objects.get(orden=orden)

        resp = self.client.get(reverse('cambiar_estado', args=[orden.id, 'proceso']), follow=True)
        orden.refresh_from_db()
        self.assertEqual(orden.estado, 'proceso')
        self.assertFalse(ProductoTerminado.objects.filter(pk=pt.pk).exists())

    def test_reabrir_bloqueado_si_el_pt_ya_se_vendio(self):
        orden = crear_orden_slitter(peso_usado=100, terminar=True)
        pt = ProductoTerminado.objects.get(orden=orden)
        pt.estado = 'vendido'
        pt.save()

        self.client.get(reverse('cambiar_estado', args=[orden.id, 'proceso']), follow=True)
        orden.refresh_from_db()
        # Sigue terminada: el reabrir se bloqueó.
        self.assertEqual(orden.estado, 'terminado')
        self.assertTrue(ProductoTerminado.objects.filter(pk=pt.pk).exists())

    def test_reabrir_bloqueado_si_el_pt_ya_esta_en_una_salida(self):
        orden = crear_orden_slitter(peso_usado=100, terminar=True)
        pt = ProductoTerminado.objects.get(orden=orden)
        salida = Salida.objects.create(tipo='maquila')
        SalidaDetalle.objects.create(salida=salida, producto_terminado=pt, peso_kg=pt.peso_kg)

        self.client.get(reverse('cambiar_estado', args=[orden.id, 'proceso']), follow=True)
        orden.refresh_from_db()
        self.assertEqual(orden.estado, 'terminado')

    def test_reabrir_revierte_cinta_a_en_almacen_cuando_libera_peso_real(self):
        # Dos órdenes de fleje comparten la misma cinta de 100kg (40 + 60):
        # al terminar la segunda, la cinta queda 'embarcado' (0kg
        # disponibles). Simplemente reabrir una de las dos NO libera peso
        # por sí solo (la orden reabierta sigue reclamando su peso_usado
        # mientras esté en la BD) — hace falta que el peso realmente
        # capturado en alguna de las órdenes se corrija/reduzca. Aquí se
        # corrige el peso de la orden B (edición normal, sigue 'terminado')
        # y ENTONCES se reabre la orden A: en ese momento el cálculo de
        # peso_disponible_fleje ya ve el peso reducido de B y sí libera lo
        # suficiente para regresar la cinta a 'en_almacen'.
        cinta_orden = crear_orden_slitter(peso_usado=100, terminar=True)
        cinta = ProductoTerminado.objects.get(orden=cinta_orden)
        orden_a = crear_orden_fleje(pt_origen=cinta, peso_usado=40, terminar=True)
        orden_b = crear_orden_fleje(pt_origen=cinta, peso_usado=60, terminar=True)
        cinta.refresh_from_db()
        self.assertEqual(cinta.estado, 'embarcado')

        orden_b.peso_usado = Decimal('20')
        orden_b.save()

        self.client.get(reverse('cambiar_estado', args=[orden_a.id, 'proceso']), follow=True)
        cinta.refresh_from_db()
        self.assertEqual(cinta.estado, 'en_almacen')
        self.assertEqual(cinta.peso_disponible_fleje, 40)


class PtOrigenQuerysetTests(TestCase):
    """OrdenProduccionForm: el combo de "cinta origen" para una orden de
    Fleje debe excluir solo cintas con una orden de fleje ACTIVA
    (pendiente/proceso), no cualquier cinta que alguna vez tuvo una."""

    def test_cinta_con_orden_fleje_pendiente_no_aparece(self):
        cinta_orden = crear_orden_slitter(peso_usado=100, terminar=True)
        cinta = ProductoTerminado.objects.get(orden=cinta_orden)
        crear_orden_fleje(pt_origen=cinta, peso_usado=30, terminar=False)  # pendiente

        form = OrdenProduccionForm()
        self.assertNotIn(cinta, form.fields['pt_origen'].queryset)

    def test_cinta_con_orden_fleje_terminada_y_peso_libre_si_aparece(self):
        cinta_orden = crear_orden_slitter(peso_usado=100, terminar=True)
        cinta = ProductoTerminado.objects.get(orden=cinta_orden)
        crear_orden_fleje(pt_origen=cinta, peso_usado=30, terminar=True)  # terminada, quedan 70kg

        form = OrdenProduccionForm()
        self.assertIn(cinta, form.fields['pt_origen'].queryset)


class ListaOrdenesFiltroAlertasTests(TestCase):
    """`?urgentes=1` y `?anomalia=bajo` son a donde llevan los links de las
    alertas de dashboard/alertas.py — deben filtrar exactamente al mismo
    subconjunto que generó el conteo de esa alerta."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.user = crear_usuario_con_rol('lista_ordenes_user', 'Administrador')
        self.client.force_login(self.user)

    def test_urgentes_filtra_solo_pendientes_y_en_proceso_con_prioridad_urgente(self):
        urgente_pendiente = crear_orden_slitter(peso_usado=50)
        urgente_pendiente.prioridad = 'urgente'
        urgente_pendiente.save()

        urgente_terminada = crear_orden_slitter(peso_usado=50, terminar=True)
        urgente_terminada.prioridad = 'urgente'
        urgente_terminada.save()

        normal_pendiente = crear_orden_slitter(peso_usado=50)  # prioridad='media' por defecto

        resp = self.client.get(reverse('lista_ordenes'), {'urgentes': '1'})
        ids = [o.id for o in resp.context['ordenes']]
        self.assertIn(urgente_pendiente.id, ids)
        self.assertNotIn(urgente_terminada.id, ids)
        self.assertNotIn(normal_pendiente.id, ids)

    def test_anomalia_bajo_filtra_solo_ordenes_con_rendimiento_anomalo(self):
        cliente = crear_cliente()
        for i in range(5):
            mp_base = crear_mp(cliente=cliente, peso=1000, material='Acero Galvanizado')
            orden_base = crear_orden_slitter(mp=mp_base, cliente=cliente, peso_usado=500)
            orden_base.peso_producido = 490  # 98%
            orden_base.estado = 'terminado'
            orden_base.save()

        mp_mala = crear_mp(cliente=cliente, peso=1000, material='Acero Galvanizado')
        orden_mala = crear_orden_slitter(mp=mp_mala, cliente=cliente, peso_usado=500)
        orden_mala.peso_producido = 350  # 70%, muy por debajo del promedio (~98%)
        orden_mala.estado = 'terminado'
        orden_mala.save()

        resp = self.client.get(reverse('lista_ordenes'), {'anomalia': 'bajo'})
        ids = [o.id for o in resp.context['ordenes']]
        self.assertEqual(ids, [orden_mala.id])
