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

from .forms import MateriaPrimaForm, MovimientoMPForm, RegistrarMovimientoForm
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


class BajaRolloSinPesoTests(TestCase):
    """Rollos que quedaron sin peso (nunca se capturó, o quedó en 0) no se
    podían dar de salida: el peso era obligatorio y no podía superar un
    restante vacío/0. Ahora se pueden dar de baja sin peso, con motivo
    obligatorio, y quedan 'Terminado'."""

    def setUp(self):
        self.user = crear_usuario_con_rol('capt_baja', 'Capturista')
        self.client.force_login(self.user)

    def _mp_sin_peso(self, numero='MP-SINPESO-1', peso=None):
        # Se crea "a la antigua" (directo en BD) porque el formulario ya no
        # deja capturar MP sin peso.
        mp = MateriaPrima.objects.create(numero_mp=numero, cliente=crear_cliente(), peso=peso)
        if peso == 0:
            MateriaPrima.objects.filter(pk=mp.pk).update(peso_restante=0)
            mp.refresh_from_db()
        return mp

    def _post(self, mp, **datos):
        datos.setdefault('fecha_salida', '')
        datos.setdefault('cliente_id', '')
        return self.client.post(reverse('dar_salida_mp', args=[mp.id]), datos)

    def test_sin_peso_se_detecta(self):
        self.assertTrue(self._mp_sin_peso().sin_peso)
        self.assertTrue(self._mp_sin_peso('MP-CERO', peso=0).sin_peso)
        self.assertFalse(crear_mp(peso=500).sin_peso)

    def test_pantalla_de_baja_no_exige_peso(self):
        mp = self._mp_sin_peso()
        resp = self.client.get(reverse('dar_salida_mp', args=[mp.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Rollo sin peso registrado')
        self.assertContains(resp, 'Motivo de la baja')

    def test_baja_sin_peso_con_motivo_deja_terminado(self):
        mp = self._mp_sin_peso()
        resp = self._post(mp, peso='', observaciones='Consumido en planta, no se registró el peso')
        self.assertEqual(resp.status_code, 302)
        mp.refresh_from_db()
        self.assertEqual(mp.estado, 'Terminado')
        self.assertEqual(mp.peso_restante, Decimal('0.00'))
        mov = MovimientoMP.objects.get(mp=mp, tipo_movimiento='SALIDA')
        self.assertEqual(mov.peso, Decimal('0.00'))
        self.assertIn('Baja sin peso registrado', mov.observaciones)
        self.assertEqual(mov.usuario, self.user)

    def test_baja_de_rollo_en_cero_tambien_funciona(self):
        mp = self._mp_sin_peso('MP-CERO-2', peso=0)
        self._post(mp, peso='', observaciones='Se regresó al cliente')
        mp.refresh_from_db()
        self.assertEqual(mp.estado, 'Terminado')

    def test_baja_sin_peso_exige_motivo(self):
        mp = self._mp_sin_peso()
        resp = self._post(mp, peso='', observaciones='   ')
        self.assertEqual(resp.status_code, 200)
        mp.refresh_from_db()
        self.assertNotEqual(mp.estado, 'Terminado')
        self.assertFalse(MovimientoMP.objects.filter(mp=mp).exists())

    def test_si_se_conoce_el_peso_queda_guardado(self):
        mp = self._mp_sin_peso()
        self._post(mp, peso='842.5', observaciones='Peso de la etiqueta')
        mp.refresh_from_db()
        self.assertEqual(mp.peso, Decimal('842.50'))
        self.assertEqual(mp.peso_restante, Decimal('0.00'))
        self.assertEqual(mp.estado, 'Terminado')
        self.assertEqual(MovimientoMP.objects.get(mp=mp).peso, Decimal('842.50'))

    def test_rollo_con_peso_sigue_exigiendo_peso(self):
        mp = crear_mp(peso=500)
        resp = self._post(mp, peso='', observaciones='intento sin peso')
        self.assertEqual(resp.status_code, 200)
        mp.refresh_from_db()
        self.assertEqual(mp.peso_restante, Decimal('500.00'))
        self.assertFalse(MovimientoMP.objects.filter(mp=mp).exists())

    def test_rollo_ya_terminado_no_se_puede_dar_de_baja_otra_vez(self):
        mp = self._mp_sin_peso()
        self._post(mp, peso='', observaciones='Primera baja')
        resp = self._post(mp, peso='', observaciones='Segunda baja')
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(MovimientoMP.objects.filter(mp=mp).count(), 1)

    def test_operador_no_puede_dar_de_baja(self):
        mp = self._mp_sin_peso()
        self.client.force_login(crear_usuario_con_rol('oper_baja', 'Operador'))
        self._post(mp, peso='', observaciones='No debería poder')
        mp.refresh_from_db()
        self.assertNotEqual(mp.estado, 'Terminado')

    def test_lista_filtra_sin_peso(self):
        sin = self._mp_sin_peso('MP-SIN-LISTA')
        con = crear_mp(numero_mp='MP-CON-LISTA', peso=300)
        resp = self.client.get(reverse('lista_mp'), {'sin_peso': '1'})
        numeros = [m.numero_mp for m in resp.context['materias_primas']]
        self.assertIn(sin.numero_mp, numeros)
        self.assertNotIn(con.numero_mp, numeros)
        self.assertEqual(resp.context['sin_peso_count'], 1)


class PesoObligatorioEnCapturaTests(TestCase):
    """La restricción para que no vuelvan a quedar rollos sin peso."""

    def _datos(self, **extra):
        datos = {
            'numero_mp': 'MP-NUEVA-1', 'tipo_mp': 'Rollo', 'origen_mp': 'Interna',
            'unidad_espesor': 'mils', 'ubicacion': 'Almacén 1', 'estado': 'Disponible',
        }
        datos.update(extra)
        return datos

    def test_captura_sin_peso_se_rechaza(self):
        form = MateriaPrimaForm(data=self._datos())
        self.assertFalse(form.is_valid())
        self.assertIn('peso', form.errors)

    def test_captura_con_peso_cero_o_negativo_se_rechaza(self):
        for peso in ['0', '-5']:
            form = MateriaPrimaForm(data=self._datos(peso=peso))
            self.assertFalse(form.is_valid(), peso)
            self.assertIn('peso', form.errors)

    def test_captura_con_peso_valido_pasa(self):
        form = MateriaPrimaForm(data=self._datos(peso='1250.5'))
        self.assertTrue(form.is_valid(), form.errors)

    def test_vista_de_captura_no_guarda_mp_sin_peso(self):
        self.client.force_login(crear_usuario_con_rol('capt_cap', 'Capturista'))
        self.client.post(reverse('captura_mp'), self._datos())
        self.assertFalse(MateriaPrima.objects.filter(numero_mp='MP-NUEVA-1').exists())

    def test_editar_no_permite_borrar_el_peso(self):
        mp = crear_mp(numero_mp='MP-EDIT-1', peso=500)
        form = MateriaPrimaForm(data=self._datos(numero_mp='MP-EDIT-1'), instance=mp)
        self.assertFalse(form.is_valid())
        self.assertIn('peso', form.errors)

    def test_rollo_ya_dado_de_baja_sin_peso_se_puede_editar(self):
        mp = MateriaPrima.objects.create(numero_mp='MP-HIST-1', estado='Terminado', peso=None)
        form = MateriaPrimaForm(data=self._datos(numero_mp='MP-HIST-1', estado='Terminado',
                                                 observaciones='nota'), instance=mp)
        self.assertTrue(form.is_valid(), form.errors)

    def test_completar_peso_a_rollo_sin_peso_actualiza_restante(self):
        admin = crear_usuario_con_rol('admin_edit', 'Administrador')
        self.client.force_login(admin)
        mp = MateriaPrima.objects.create(numero_mp='MP-COMPLETAR', peso=None)
        self.client.post(reverse('editar_mp', args=[mp.id]), self._datos(numero_mp='MP-COMPLETAR', peso='900'))
        mp.refresh_from_db()
        self.assertEqual(mp.peso, Decimal('900.00'))
        self.assertEqual(mp.peso_restante, Decimal('900.00'))
        self.assertFalse(mp.sin_peso)

    def test_admin_de_django_tambien_exige_peso(self):
        from .forms import MateriaPrimaAdminForm
        form = MateriaPrimaAdminForm(data=self._datos())
        self.assertFalse(form.is_valid())
        self.assertIn('peso', form.errors)


class EditarPesoActualizaRestanteTests(TestCase):
    """Corregir el peso de un rollo (p. ej. 213000 mal capturado → 21300)
    antes solo cambiaba `peso`; el peso restante —lo que muestra la lista y
    suman el dashboard/reportes— se quedaba con el valor equivocado."""

    def setUp(self):
        self.client.force_login(crear_usuario_con_rol('admin_peso', 'Administrador'))

    def _editar(self, mp, peso, **extra):
        datos = {
            'numero_mp': mp.numero_mp, 'tipo_mp': 'Rollo', 'origen_mp': 'Interna',
            'unidad_espesor': 'mils', 'ubicacion': 'Almacén 1', 'estado': mp.estado,
            'peso': peso,
        }
        datos.update(extra)
        return self.client.post(reverse('editar_mp', args=[mp.id]), datos)

    def test_corregir_peso_sin_consumo_actualiza_restante(self):
        mp = crear_mp(numero_mp='4A626499PDT00', peso=213000)
        self._editar(mp, '21300')
        mp.refresh_from_db()
        self.assertEqual(mp.peso, Decimal('21300.00'))
        self.assertEqual(mp.peso_restante, Decimal('21300.00'))

    def test_corregir_peso_respeta_lo_ya_consumido(self):
        mp = crear_mp(numero_mp='MP-CONS', peso=213000)
        MovimientoMP.objects.create(mp=mp, tipo_movimiento='CONSUMO', peso=Decimal('5000'))
        mp.refresh_from_db()
        self._editar(mp, '21300')
        mp.refresh_from_db()
        self.assertEqual(mp.peso_restante, Decimal('16300.00'))

    def test_peso_menor_a_lo_consumido_se_rechaza(self):
        mp = crear_mp(numero_mp='MP-MENOR', peso=1000)
        MovimientoMP.objects.create(mp=mp, tipo_movimiento='CONSUMO', peso=Decimal('800'))
        resp = self._editar(mp, '500')
        self.assertEqual(resp.status_code, 200)
        mp.refresh_from_db()
        self.assertEqual(mp.peso, Decimal('1000.00'))
        self.assertEqual(mp.peso_restante, Decimal('200.00'))

    def test_registro_ya_danado_se_corrige_al_guardar(self):
        # El caso real: ya se había corregido el peso a 21300 pero el
        # restante se quedó en 213000. Abrir Editar y Guardar lo arregla.
        mp = crear_mp(numero_mp='MP-DANADO', peso=21300)
        MateriaPrima.objects.filter(pk=mp.pk).update(peso_restante=Decimal('213000'))
        mp.refresh_from_db()
        self._editar(mp, '21300')
        mp.refresh_from_db()
        self.assertEqual(mp.peso_restante, Decimal('21300.00'))

    def test_registro_danado_con_consumo_se_recalcula_con_movimientos(self):
        mp = crear_mp(numero_mp='MP-DANADO-2', peso=21300)
        MovimientoMP.objects.create(mp=mp, tipo_movimiento='CONSUMO', peso=Decimal('1300'))
        MateriaPrima.objects.filter(pk=mp.pk).update(peso_restante=Decimal('211700'))
        mp.refresh_from_db()
        self._editar(mp, '21300')
        mp.refresh_from_db()
        self.assertEqual(mp.peso_restante, Decimal('20000.00'))

    def test_editar_otro_dato_no_toca_el_restante(self):
        mp = crear_mp(numero_mp='MP-OTRO', peso=1000)
        MovimientoMP.objects.create(mp=mp, tipo_movimiento='CONSUMO', peso=Decimal('300'))
        mp.refresh_from_db()
        self._editar(mp, '1000', observaciones='solo una nota')
        mp.refresh_from_db()
        self.assertEqual(mp.peso_restante, Decimal('700.00'))

    def test_correccion_queda_en_historial(self):
        from dashboard.models import HistorialCambio
        mp = crear_mp(numero_mp='MP-HIST-PESO', peso=213000)
        self._editar(mp, '21300')
        h = HistorialCambio.objects.filter(tipo_objeto='MateriaPrima', objeto_id=mp.id, accion='EDITAR').last()
        self.assertIn('213000', h.descripcion)
        self.assertIn('21300', h.descripcion)


class ListaMpOcultaTerminadosTests(TestCase):
    """Una MP a la que ya se le dio salida completa (queda 'Terminado') ya no
    está en planta: no debe seguir saliendo en la lista por defecto ni
    contando para las alertas de cobro por estancia."""

    def setUp(self):
        self.client.force_login(crear_usuario_con_rol('lista_term', 'Capturista'))
        self.activa = crear_mp(numero_mp='MP-ACTIVA', peso=500)
        self.salio = crear_mp(numero_mp='MP-SALIO', peso=500)
        MovimientoMP.objects.create(mp=self.salio, tipo_movimiento='SALIDA', peso=Decimal('500'))
        self.salio.refresh_from_db()

    def _numeros(self, **params):
        resp = self.client.get(reverse('lista_mp'), params)
        return [m.numero_mp for m in resp.context['materias_primas']], resp

    def test_salida_completa_deja_terminado(self):
        self.assertEqual(self.salio.estado, 'Terminado')

    def test_por_defecto_no_aparece_la_que_ya_salio(self):
        numeros, resp = self._numeros()
        self.assertIn('MP-ACTIVA', numeros)
        self.assertNotIn('MP-SALIO', numeros)
        self.assertEqual(resp.context['terminados_count'], 1)

    def test_filtro_terminado_y_todos_si_la_muestran(self):
        self.assertEqual(self._numeros(estado='Terminado')[0], ['MP-SALIO'])
        self.assertIn('MP-SALIO', self._numeros(estado='todos')[0])

    def test_buscar_por_numero_la_encuentra_aunque_este_terminada(self):
        self.assertEqual(self._numeros(q='MP-SALIO')[0], ['MP-SALIO'])

    def test_salida_parcial_sigue_apareciendo(self):
        mp = crear_mp(numero_mp='MP-PARCIAL', peso=500)
        MovimientoMP.objects.create(mp=mp, tipo_movimiento='SALIDA', peso=Decimal('200'))
        self.assertIn('MP-PARCIAL', self._numeros()[0])

    def test_terminada_no_cuenta_para_alerta_de_cobro(self):
        import datetime
        from django.utils import timezone
        from dashboard.alertas import obtener_alertas
        hace_40 = timezone.localdate() - datetime.timedelta(days=40)
        MateriaPrima.objects.filter(pk__in=[self.activa.pk, self.salio.pk]).update(fecha_entrada=hace_40)
        criticas = [a for a in obtener_alertas() if a['tipo'] == 'critica']
        self.assertEqual(criticas[0]['count'], 1)
        numeros, resp = self._numeros(cobro='vencido')
        self.assertEqual(numeros, ['MP-ACTIVA'])
        self.assertEqual(resp.context['mp_vencidas_count'], 1)
