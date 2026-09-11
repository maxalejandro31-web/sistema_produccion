"""Tests de calidad: conversión de unidades al evaluar tolerancias
dimensionales (el bug real era comparar pulgadas contra milímetros sin
convertir), ciclo de vida de NoConformidad, y el fallback de
ToleranciaProceso a la tolerancia genérica del proceso.
"""
from decimal import Decimal

from django.test import TestCase

from core.factories import crear_mp, crear_orden_slitter

from produccion.models import DetalleSlitter
from .models import NoConformidad, ToleranciaProceso
from .utils import evaluar_tolerancia_detalle


class EvaluarToleranciaDetalleTests(TestCase):
    def setUp(self):
        # mp.espesor_mm queda directo en 0.889 mm (unidad_espesor='mm').
        self.mp = crear_mp(
            material='Acero A36', ancho=Decimal('100.00'),
            espesor_valor=Decimal('0.889'), unidad_espesor='mm',
        )
        self.orden = crear_orden_slitter(mp=self.mp, peso_usado=100, cortes=[])

    def test_sin_tolerancia_configurada_devuelve_none(self):
        detalle = DetalleSlitter.objects.create(
            orden=self.orden, no_corte=1, ancho=Decimal('100.00'), espesor=Decimal('0.035'),
        )
        self.assertIsNone(evaluar_tolerancia_detalle(detalle))

    def test_espesor_en_pulgadas_se_convierte_a_mm_antes_de_comparar(self):
        # DetalleSlitter.espesor se captura en PULGADAS; mp.espesor_mm ya
        # está en mm. 0.035 pulg == 0.889 mm — deben salir prácticamente
        # iguales (diferencia ~0), no "fuera de tolerancia" por comparar
        # 0.035 contra 0.889 directamente sin convertir.
        ToleranciaProceso.objects.create(
            tipo_proceso='slitter', material='Acero A36',
            tolerancia_espesor_mm=Decimal('0.01'),
        )
        detalle = DetalleSlitter.objects.create(
            orden=self.orden, no_corte=1, espesor=Decimal('0.035'),
        )
        resultado = evaluar_tolerancia_detalle(detalle)
        self.assertIsNotNone(resultado)
        self.assertTrue(resultado['espesor_ok'])
        self.assertLess(resultado['diferencia_espesor'], 0.01)

    def test_espesor_fuera_de_tolerancia_real_se_detecta(self):
        ToleranciaProceso.objects.create(
            tipo_proceso='slitter', material='Acero A36',
            tolerancia_espesor_mm=Decimal('0.01'),
        )
        # 0.05 pulg = 1.27 mm, muy lejos de los 0.889 mm de la MP.
        detalle = DetalleSlitter.objects.create(
            orden=self.orden, no_corte=1, espesor=Decimal('0.05'),
        )
        resultado = evaluar_tolerancia_detalle(detalle)
        self.assertFalse(resultado['espesor_ok'])
        self.assertTrue(resultado['fuera_de_tolerancia'])

    def test_ancho_fuera_de_tolerancia(self):
        ToleranciaProceso.objects.create(
            tipo_proceso='slitter', material='Acero A36',
            tolerancia_ancho_mm=Decimal('0.5'),
        )
        detalle = DetalleSlitter.objects.create(
            orden=self.orden, no_corte=1, ancho=Decimal('105.00'),
        )
        resultado = evaluar_tolerancia_detalle(detalle)
        self.assertFalse(resultado['ancho_ok'])
        self.assertTrue(resultado['fuera_de_tolerancia'])


class ToleranciaProcesoObtenerTests(TestCase):
    def test_cae_a_la_tolerancia_generica_si_no_hay_especifica(self):
        generica = ToleranciaProceso.objects.create(tipo_proceso='slitter', material='', tolerancia_ancho_mm=Decimal('1'))
        encontrada = ToleranciaProceso.obtener('slitter', 'Acero Inoxidable 304')
        self.assertEqual(encontrada, generica)

    def test_prefiere_la_tolerancia_especifica_del_material(self):
        ToleranciaProceso.objects.create(tipo_proceso='slitter', material='', tolerancia_ancho_mm=Decimal('1'))
        especifica = ToleranciaProceso.objects.create(tipo_proceso='slitter', material='Acero A36', tolerancia_ancho_mm=Decimal('0.3'))
        encontrada = ToleranciaProceso.obtener('slitter', 'Acero A36')
        self.assertEqual(encontrada, especifica)

    def test_tolerancia_inactiva_no_se_usa(self):
        ToleranciaProceso.objects.create(tipo_proceso='slitter', material='', tolerancia_ancho_mm=Decimal('1'), activa=False)
        self.assertIsNone(ToleranciaProceso.obtener('slitter', 'cualquier material'))


class NoConformidadCicloDeVidaTests(TestCase):
    def setUp(self):
        orden = crear_orden_slitter(peso_usado=100, terminar=True)
        from materia_terminada.models import ProductoTerminado
        self.pt = ProductoTerminado.objects.get(orden=orden)

    def test_cerrar_asigna_fecha_cierre(self):
        nc = NoConformidad.objects.create(producto_terminado=self.pt, severidad='menor', estado='abierta', descripcion='x')
        self.assertIsNone(nc.fecha_cierre)
        nc.estado = 'cerrada'
        nc.save()
        self.assertIsNotNone(nc.fecha_cierre)

    def test_reabrir_limpia_fecha_cierre(self):
        nc = NoConformidad.objects.create(producto_terminado=self.pt, severidad='menor', estado='cerrada', descripcion='x')
        self.assertIsNotNone(nc.fecha_cierre)
        nc.estado = 'abierta'
        nc.save()
        self.assertIsNone(nc.fecha_cierre)
