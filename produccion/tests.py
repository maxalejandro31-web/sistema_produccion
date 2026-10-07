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


class RendimientoCapturaTests(TestCase):
    """Cálculo de rendimiento al capturar/editar órdenes."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.user = crear_usuario_con_rol('rend_admin', 'Administrador')
        self.client.force_login(self.user)
        self.cliente = crear_cliente()
        self.linea = crear_linea()

    def _datos(self, tipo, cortes=(), descargas=(), **orden):
        datos = {
            'tipo_proceso': tipo, 'linea': self.linea.id, 'cliente': self.cliente.id,
            'prioridad': 'media', 'estado': 'pendiente',
            'detalles-TOTAL_FORMS': str(len(cortes)), 'detalles-INITIAL_FORMS': '0',
            'detalles-MIN_NUM_FORMS': '0', 'detalles-MAX_NUM_FORMS': '1000',
            'detalles_fleje-TOTAL_FORMS': str(len(descargas)), 'detalles_fleje-INITIAL_FORMS': '0',
            'detalles_fleje-MIN_NUM_FORMS': '0', 'detalles_fleje-MAX_NUM_FORMS': '1000',
        }
        for i, c in enumerate(cortes):
            datos[f'detalles-{i}-no_corte'] = str(c['no'])
            datos[f'detalles-{i}-peso'] = str(c['peso'])
            datos[f'detalles-{i}-clasificacion'] = c.get('clasif', 'normal')
            if c.get('merma') is not None:
                datos[f'detalles-{i}-peso_merma'] = str(c['merma'])
        for i, d in enumerate(descargas):
            datos[f'detalles_fleje-{i}-no_fleje'] = str(i + 1)
            datos[f'detalles_fleje-{i}-peso_descarga'] = str(d)
            datos[f'detalles_fleje-{i}-numero_flejes'] = '1'
        datos.update({k: str(v) for k, v in orden.items()})
        return datos

    def _ultima(self):
        return OrdenProduccion.objects.order_by('-id').first()

    # ── Slitter: scrap/descarte no es producto ──────────────────────────
    def test_cortes_scrap_y_descarte_no_cuentan_como_producido(self):
        mp = crear_mp(cliente=self.cliente, peso=1000)
        self.client.post(reverse('captura_orden'), self._datos('slitter', mp=mp.id, peso_usado=1000, cortes=[
            {'no': 1, 'peso': 450}, {'no': 2, 'peso': 450},
            {'no': 3, 'peso': 60, 'clasif': 'scrap'}, {'no': 4, 'peso': 30, 'clasif': 'descarte'},
        ]))
        orden = self._ultima()
        self.assertEqual(orden.peso_producido, Decimal('900.00'))
        self.assertEqual(orden.rendimiento_porcentaje, Decimal('90.00'))
        self.assertEqual(orden.scrap_total, Decimal('100.00'))

    def test_al_terminar_no_se_crea_pt_de_los_cortes_scrap(self):
        mp = crear_mp(cliente=self.cliente, peso=1000)
        self.client.post(reverse('captura_orden'), self._datos('slitter', mp=mp.id, peso_usado=1000, cortes=[
            {'no': 1, 'peso': 900}, {'no': 2, 'peso': 80, 'clasif': 'scrap'},
        ]))
        orden = self._ultima()
        orden.estado = 'terminado'
        orden.save()
        pts = ProductoTerminado.objects.filter(orden=orden)
        self.assertEqual(pts.count(), 1)
        self.assertEqual(pts.first().peso_kg, Decimal('900.00'))

    def test_cambiar_corte_a_scrap_quita_su_pt_si_no_se_ha_movido(self):
        orden = crear_orden_slitter(peso_usado=500, cortes=[{'no_corte': 1, 'peso': 400}, {'no_corte': 2, 'peso': 90}], terminar=True)
        self.assertEqual(ProductoTerminado.objects.filter(orden=orden).count(), 2)
        d2 = orden.detalles_slitter.get(no_corte=2)
        d2.clasificacion = 'scrap'
        d2.save()
        self.assertEqual(ProductoTerminado.objects.filter(orden=orden).count(), 1)

    # ── Producido > usado ──────────────────────────────────────────────
    def test_producido_mayor_a_usado_se_rechaza(self):
        mp = crear_mp(cliente=self.cliente, peso=5000)
        resp = self.client.post(reverse('captura_orden'), self._datos('slitter', mp=mp.id, peso_usado=1000, cortes=[
            {'no': 1, 'peso': 1200},
        ]))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(OrdenProduccion.objects.exists())
        mp.refresh_from_db()
        self.assertEqual(mp.peso_restante, Decimal('5000.00'))

    def test_diferencia_de_bascula_menor_a_1_por_ciento_se_acepta(self):
        mp = crear_mp(cliente=self.cliente, peso=5000)
        self.client.post(reverse('captura_orden'), self._datos('slitter', mp=mp.id, peso_usado=1000, cortes=[
            {'no': 1, 'peso': 1005},
        ]))
        self.assertTrue(OrdenProduccion.objects.exists())

    def test_corte_liso_producido_mayor_se_rechaza(self):
        mp = crear_mp(cliente=self.cliente, peso=5000)
        self.client.post(reverse('captura_orden'), self._datos('corte_liso', mp=mp.id, peso_usado=1000, peso_producido=1500))
        self.assertFalse(OrdenProduccion.objects.exists())

    def test_editar_con_producido_mayor_no_guarda_nada_a_medias(self):
        orden = crear_orden_slitter(peso_usado=500, cortes=[{'no_corte': 1, 'peso': 480}])
        d = orden.detalles_slitter.get()
        datos = self._datos('slitter', mp=orden.mp_id, peso_usado=500)
        datos.update({
            'detalles-TOTAL_FORMS': '1', 'detalles-INITIAL_FORMS': '1',
            'detalles-0-id': str(d.id), 'detalles-0-orden': str(orden.id),
            'detalles-0-no_corte': '1', 'detalles-0-peso': '900', 'detalles-0-clasificacion': 'normal',
        })
        resp = self.client.post(reverse('editar_orden', args=[orden.id]), datos)
        self.assertEqual(resp.status_code, 200)
        d.refresh_from_db()
        orden.refresh_from_db()
        self.assertEqual(d.peso, Decimal('480.00'))       # el corte no se quedó guardado
        self.assertEqual(orden.peso_producido, Decimal('500.00'))  # la orden tampoco cambió

    # ── Fleje por lotes ────────────────────────────────────────────────
    def _cinta(self, peso=3000):
        orden = crear_orden_slitter(cliente=self.cliente, peso_usado=peso, cortes=[{'no_corte': 1, 'peso': peso}], terminar=True)
        return ProductoTerminado.objects.get(orden=orden)

    def test_fleje_respeta_el_peso_usado_del_lote(self):
        cinta = self._cinta(3000)
        self.client.post(reverse('captura_orden'), self._datos(
            'fleje', pt_origen=cinta.id, peso_rollo_padre=3000, peso_usado=1500, descargas=[1470]))
        lote = self._ultima()
        self.assertEqual(lote.peso_usado, Decimal('1500.00'))
        self.assertEqual(lote.rendimiento_porcentaje, Decimal('98.00'))

    def test_fleje_sin_peso_usado_toma_lo_que_le_queda_a_la_cinta(self):
        cinta = self._cinta(3000)
        self.client.post(reverse('captura_orden'), self._datos(
            'fleje', pt_origen=cinta.id, peso_rollo_padre=3000, peso_usado=1000, descargas=[990], estado='terminado'))
        self.client.post(reverse('captura_orden'), self._datos(
            'fleje', pt_origen=cinta.id, peso_rollo_padre=3000, descargas=[1960]))
        lote2 = self._ultima()
        self.assertEqual(lote2.peso_usado, Decimal('2000.00'))
        self.assertEqual(lote2.rendimiento_porcentaje, Decimal('98.00'))

    def test_cinta_no_se_agota_con_el_primer_lote(self):
        cinta = self._cinta(3000)
        self.client.post(reverse('captura_orden'), self._datos(
            'fleje', pt_origen=cinta.id, peso_rollo_padre=3000, peso_usado=1000, descargas=[990], estado='terminado'))
        cinta.refresh_from_db()
        self.assertEqual(cinta.estado, 'en_almacen')
        self.assertEqual(cinta.peso_disponible_fleje, 2000)

    def test_lote_mayor_a_lo_que_queda_se_rechaza(self):
        cinta = self._cinta(3000)
        self.client.post(reverse('captura_orden'), self._datos(
            'fleje', pt_origen=cinta.id, peso_rollo_padre=3000, peso_usado=2500, descargas=[2450], estado='terminado'))
        antes = OrdenProduccion.objects.count()
        self.client.post(reverse('captura_orden'), self._datos(
            'fleje', pt_origen=cinta.id, peso_rollo_padre=3000, peso_usado=1000, descargas=[490]))
        self.assertEqual(OrdenProduccion.objects.count(), antes)

    def test_api_cinta_devuelve_peso_disponible(self):
        cinta = self._cinta(3000)
        self.client.post(reverse('captura_orden'), self._datos(
            'fleje', pt_origen=cinta.id, peso_rollo_padre=3000, peso_usado=1200, descargas=[1180], estado='terminado'))
        data = self.client.get(reverse('api_datos_pt_origen', args=[cinta.id])).json()
        self.assertEqual(data['peso_disponible'], '1800')
        self.assertEqual(data['peso_rollo_padre'], '3000')


class RendimientoDashboardYPromedioTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()

    def test_rendimiento_mensual_solo_cuenta_ordenes_terminadas(self):
        user = crear_usuario_con_rol('dash_rend', 'Administrador')
        self.client.force_login(user)
        terminada = crear_orden_slitter(peso_usado=1000, terminar=True)
        OrdenProduccion.objects.filter(pk=terminada.pk).update(peso_producido=Decimal('950'))
        # Orden pendiente con lo producido todavía vacío: antes bajaba el %.
        pendiente = crear_orden_slitter(peso_usado=1000)
        OrdenProduccion.objects.filter(pk=pendiente.pk).update(peso_producido=None)
        resp = self.client.get(reverse('inicio'))
        self.assertEqual(resp.context['rendimiento_mes_actual'], 95.0)

    def test_rendimientos_imposibles_no_entran_al_promedio(self):
        from .analitica import mapear_baselines_rendimiento
        for i in range(5):
            o = crear_orden_slitter(mp=crear_mp(peso=1000, material='Acero X'), peso_usado=500, terminar=True)
            OrdenProduccion.objects.filter(pk=o.pk).update(rendimiento_porcentaje=Decimal('98'))
        malo = crear_orden_slitter(mp=crear_mp(peso=1000, material='Acero X'), peso_usado=500, terminar=True)
        OrdenProduccion.objects.filter(pk=malo.pk).update(rendimiento_porcentaje=Decimal('950'))
        stats = mapear_baselines_rendimiento(usar_cache=False)[('slitter', 'Acero X')]
        self.assertEqual(stats['promedio'], 98.0)
        self.assertEqual(stats['muestra'], 5)


class CerosRealesSeMuestranTests(TestCase):
    """Un scrap o rendimiento real de 0 se mostraba como "—"/"-", igual que
    un dato no capturado."""

    def test_scrap_cero_y_rendimiento_cero_se_ven(self):
        self.client.force_login(crear_usuario_con_rol('ceros_admin', 'Administrador'))
        orden = crear_orden_slitter(peso_usado=500)
        OrdenProduccion.objects.filter(pk=orden.pk).update(
            scrap_total=Decimal('0'), merma_kg=Decimal('0'), rendimiento_porcentaje=Decimal('0'),
        )
        detalle = self.client.get(reverse('detalle_orden', args=[orden.id])).content.decode()
        self.assertIn('Scrap total:</strong> 0.00', detalle)
        self.assertIn('Rendimiento:</strong> 0.00', detalle)
        lista = self.client.get(reverse('lista_ordenes')).content.decode()
        self.assertIn('0.00%', lista)


class CapturaProcesosTests(TestCase):
    """Registro correcto de los 4 procesos (reutiliza los helpers de
    RendimientoCapturaTests sin volver a correr sus pruebas)."""
    setUp = RendimientoCapturaTests.setUp
    _datos = RendimientoCapturaTests._datos
    _ultima = RendimientoCapturaTests._ultima
    _cinta = RendimientoCapturaTests._cinta

    def _renglones_vacios(self, datos, prefijo, campo, desde, hasta):
        # Imita la pantalla: los renglones extra llegan con el No. pre-llenado.
        datos[f'{prefijo}-TOTAL_FORMS'] = str(hasta)
        for i in range(desde, hasta):
            datos[f'{prefijo}-{i}-{campo}'] = str(i + 1)
            if prefijo == 'detalles':
                datos[f'{prefijo}-{i}-clasificacion'] = 'normal'
        return datos

    def test_slitter_no_guarda_renglones_vacios(self):
        mp = crear_mp(cliente=self.cliente, peso=1000)
        datos = self._datos('slitter', mp=mp.id, peso_usado=1000, cortes=[{'no': 1, 'peso': 490}, {'no': 2, 'peso': 490}])
        self._renglones_vacios(datos, 'detalles', 'no_corte', 2, 5)
        self.client.post(reverse('captura_orden'), datos)
        self.assertEqual(list(self._ultima().detalles_slitter.values_list('no_corte', flat=True)), [1, 2])

    def test_fleje_no_guarda_tiras_vacias(self):
        cinta = self._cinta(1000)
        datos = self._datos('fleje', pt_origen=cinta.id, peso_usado=500, descargas=[245, 245])
        self._renglones_vacios(datos, 'detalles_fleje', 'no_fleje', 2, 15)
        self.client.post(reverse('captura_orden'), datos)
        self.assertEqual(self._ultima().detalles_fleje.count(), 2)

    def test_mini_slitter_guarda_cortes_y_una_cinta_por_corte(self):
        mp = crear_mp(cliente=self.cliente, peso=1000)
        self.client.post(reverse('captura_orden'), self._datos(
            'mini_slitter', mp=mp.id, peso_usado=800, estado='terminado',
            cortes=[{'no': 1, 'peso': 390}, {'no': 2, 'peso': 390}]))
        orden = self._ultima()
        self.assertEqual(orden.detalles_slitter.count(), 2)
        self.assertEqual(orden.peso_producido, Decimal('780.00'))
        pts = sorted(ProductoTerminado.objects.filter(orden=orden).values_list('numero_pt', flat=True))
        self.assertEqual(pts, [f'PT-{orden.folio_orden}-C1', f'PT-{orden.folio_orden}-C2'])

    def test_corte_liso_capturado_terminado_nombra_bien_su_cinta(self):
        mp = crear_mp(cliente=self.cliente, peso=1000)
        self.client.post(reverse('captura_orden'), self._datos(
            'corte_liso', mp=mp.id, peso_usado=600, peso_producido=590, estado='terminado'))
        orden = self._ultima()
        self.assertEqual(ProductoTerminado.objects.get(orden=orden).numero_pt, f'PT-{orden.folio_orden}')

    def test_editar_quita_renglones_vacios_que_ya_existian(self):
        orden = crear_orden_slitter(peso_usado=500, cortes=[{'no_corte': 1, 'peso': 480}])
        vacio = DetalleSlitter.objects.create(orden=orden, no_corte=2)
        d = orden.detalles_slitter.get(no_corte=1)
        datos = self._datos('slitter', mp=orden.mp_id, peso_usado=500)
        datos.update({
            'detalles-TOTAL_FORMS': '2', 'detalles-INITIAL_FORMS': '2',
            'detalles-0-id': str(d.id), 'detalles-0-orden': str(orden.id), 'detalles-0-no_corte': '1',
            'detalles-0-peso': '480', 'detalles-0-clasificacion': 'normal',
            'detalles-1-id': str(vacio.id), 'detalles-1-orden': str(orden.id), 'detalles-1-no_corte': '2',
            'detalles-1-clasificacion': 'normal',
        })
        self.client.post(reverse('editar_orden', args=[orden.id]), datos)
        self.assertEqual(list(orden.detalles_slitter.values_list('no_corte', flat=True)), [1])
