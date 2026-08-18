"""Detección de anomalías de rendimiento en órdenes de producción.

Compara el rendimiento de cada orden contra el histórico reciente de órdenes
terminadas con el mismo tipo_proceso y material de MP, para señalar cuándo
una orden salió muy por debajo de lo normal.
"""
import statistics

from django.core.cache import cache

MUESTRA_MINIMA = 5
LIMITE_POR_GRUPO = 20
UMBRAL_MINIMO_PP = 5.0
FACTOR_DESVIACION = 1.5

# El baseline se recalcula sobre TODO el histórico de órdenes terminadas cada
# vez que se llama; en páginas de alto tráfico (dashboard, lista de órdenes)
# eso significa recalcularlo en cada request. Se cachea unos minutos: es
# estadística de tendencia, no necesita ser exacta al segundo.
CACHE_KEY = 'produccion:baselines_rendimiento'
CACHE_TIMEOUT_SEGUNDOS = 300


def mapear_baselines_rendimiento(limite_por_grupo=LIMITE_POR_GRUPO, usar_cache=True):
    """Devuelve {(tipo_proceso, material): {'promedio', 'desviacion', 'muestra'}}
    usando hasta `limite_por_grupo` órdenes terminadas más recientes por grupo.
    Grupos con menos de MUESTRA_MINIMA órdenes se omiten (no hay baseline)."""
    if usar_cache and limite_por_grupo == LIMITE_POR_GRUPO:
        mapa_cacheado = cache.get(CACHE_KEY)
        if mapa_cacheado is not None:
            return mapa_cacheado

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

    if usar_cache and limite_por_grupo == LIMITE_POR_GRUPO:
        cache.set(CACHE_KEY, mapa, CACHE_TIMEOUT_SEGUNDOS)

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
