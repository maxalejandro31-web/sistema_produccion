"""Evaluación de tolerancias dimensionales para cortes de slitter.

Compara el ancho/espesor de cada DetalleSlitter contra el ancho/espesor
declarado de la MP de origen, usando la tolerancia configurada en
ToleranciaProceso para ese tipo de proceso + material. Sigue el mismo
patrón que produccion/analitica.py (anotar_* sobre una colección ya cargada).
"""
from .models import ToleranciaProceso


def evaluar_tolerancia_detalle(detalle):
    """Evalúa un DetalleSlitter ya cargado (requiere detalle.orden.mp
    precargado). Devuelve None si no aplica (falta MP, ancho o tolerancia
    configurada), o un dict con el resultado de la comparación."""
    orden = detalle.orden
    if not (orden and orden.mp_id):
        return None

    mp = orden.mp
    tolerancia = ToleranciaProceso.obtener(orden.tipo_proceso, mp.material)
    if not tolerancia:
        return None

    resultado = {'tolerancia': tolerancia, 'ancho_ok': None, 'espesor_ok': None}

    if (
        tolerancia.tolerancia_ancho_mm is not None
        and detalle.ancho is not None
        and mp.ancho is not None
    ):
        diferencia_ancho = abs(float(detalle.ancho) - float(mp.ancho))
        resultado['ancho_ok'] = diferencia_ancho <= float(tolerancia.tolerancia_ancho_mm)
        resultado['diferencia_ancho'] = round(diferencia_ancho, 3)

    if (
        tolerancia.tolerancia_espesor_mm is not None
        and detalle.espesor is not None
        and mp.espesor_mm is not None
    ):
        diferencia_espesor = abs(float(detalle.espesor) - float(mp.espesor_mm))
        resultado['espesor_ok'] = diferencia_espesor <= float(tolerancia.tolerancia_espesor_mm)
        resultado['diferencia_espesor'] = round(diferencia_espesor, 4)

    resultado['fuera_de_tolerancia'] = (
        resultado['ancho_ok'] is False or resultado['espesor_ok'] is False
    )
    return resultado


def anotar_tolerancias(detalles):
    """Asigna `.tolerancia_info` a cada DetalleSlitter de la colección
    (requiere select_related('orden', 'orden__mp')). Devuelve una lista."""
    detalles = list(detalles)
    for detalle in detalles:
        detalle.tolerancia_info = evaluar_tolerancia_detalle(detalle)
    return detalles
