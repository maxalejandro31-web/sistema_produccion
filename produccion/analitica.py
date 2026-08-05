"""Detección de anomalías de rendimiento en órdenes de producción.

Compara el rendimiento de cada orden contra el histórico reciente de órdenes
terminadas con el mismo tipo_proceso y material de MP, para señalar cuándo
una orden salió muy por debajo de lo normal.
"""
import statistics

MUESTRA_MINIMA = 5
LIMITE_POR_GRUPO = 20
UMBRAL_MINIMO_PP = 5.0
FACTOR_DESVIACION = 1.5


def mapear_baselines_rendimiento(limite_por_grupo=LIMITE_POR_GRUPO):
    """Devuelve {(tipo_proceso, material): {'promedio', 'desviacion', 'muestra'}}
    usando hasta `limite_por_grupo` órdenes terminadas más recientes por grupo.
    Grupos con menos de MUESTRA_MINIMA órdenes se omiten (no hay baseline)."""
    from .models import OrdenProduccion

    filas = (
        OrdenProduccion.objects
        .filter(
            estado='terminado',
            rendimiento_porcentaje__isnull=False,
            mp__material__isnull=False,
        )
        .exclude(mp__material='')
        .order_by('-fecha')
        .values_list('tipo_proceso', 'mp__material', 'rendimiento_porcentaje')
    )

    grupos = {}
    for tipo_proceso, material, rendimiento in filas:
        clave = (tipo_proceso, material)
        valores = grupos.setdefault(clave, [])
        if len(valores) < limite_por_grupo:
            valores.append(float(rendimiento))

    mapa = {}
    for clave, valores in grupos.items():
        if len(valores) >= MUESTRA_MINIMA:
            mapa[clave] = {
                'promedio': round(statistics.mean(valores), 2),
                'desviacion': round(statistics.pstdev(valores), 2),
                'muestra': len(valores),
            }
    return mapa


def evaluar_anomalia(orden, mapa):
    """Evalúa una orden ya cargada (con .mp) contra el mapa de baselines.
    Devuelve None si no aplica, o un dict {'bucket', 'promedio', 'diferencia', 'muestra'}."""
    if not (orden.mp_id and orden.mp.material and orden.rendimiento_porcentaje is not None):
        return None

    stats = mapa.get((orden.tipo_proceso, orden.mp.material))
    if not stats:
        return {'bucket': 'sin_datos'}

    diferencia = stats['promedio'] - float(orden.rendimiento_porcentaje)
    umbral = max(UMBRAL_MINIMO_PP, stats['desviacion'] * FACTOR_DESVIACION)

    if diferencia > umbral:
        return {
            'bucket': 'bajo',
            'promedio': stats['promedio'],
            'diferencia': round(diferencia, 2),
            'muestra': stats['muestra'],
        }
    return {
        'bucket': 'normal',
        'promedio': stats['promedio'],
        'muestra': stats['muestra'],
    }


def anotar_anomalias(ordenes):
    """Calcula el mapa de baselines una sola vez y asigna `.anomalia_rendimiento`
    a cada orden de `ordenes` (requiere que .mp esté precargado con select_related).
    Devuelve la misma colección como lista."""
    mapa = mapear_baselines_rendimiento()
    ordenes = list(ordenes)
    for orden in ordenes:
        orden.anomalia_rendimiento = evaluar_anomalia(orden, mapa)
    return ordenes
