"""Detección de anomalías de rendimiento en órdenes de producción.

Compara el rendimiento de cada orden contra el histórico reciente de órdenes
terminadas con el mismo tipo_proceso y material de MP, para señalar cuándo
una orden salió muy por debajo de lo normal.
"""
import statistics

from django.core.cache import cache
from django.db.models import Sum

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


# ─────────────────────────────────────────────────────────────────────────
# Alarma de rendimiento TOTAL por rollo (MateriaPrima).
#
# Esto es distinto de `anotar_anomalias`: aquella compara una orden contra
# el promedio histórico de su mismo tipo_proceso/material (umbral relativo,
# estadístico). Esta alarma es un umbral FIJO sobre el aprovechamiento total
# de un rollo completo, sumando TODAS las órdenes (de cualquier tipo_proceso)
# que lo consumieron: rendimiento_total = suma(peso_producido) / suma(peso_usado).
# Solo se evalúan rollos con estado='Terminado' (ya se agotaron por completo,
# así que su rendimiento total ya es definitivo y no va a cambiar).
# ─────────────────────────────────────────────────────────────────────────

UMBRAL_RENDIMIENTO_ROLLO = 96.5


def mapa_rendimiento_rollos_terminados():
    """Devuelve {mp_id: rendimiento_total_pct} para cada MateriaPrima con
    estado='Terminado' que tenga al menos una orden con peso_usado y
    peso_producido capturados. rendimiento_total_pct redondeado a 2
    decimales."""
    from .models import OrdenProduccion

    agregados = (
        OrdenProduccion.objects
        .filter(mp__estado='Terminado')
        .exclude(peso_usado__isnull=True)
        .exclude(peso_producido__isnull=True)
        .values('mp_id')
        .annotate(usado=Sum('peso_usado'), producido=Sum('peso_producido'))
    )

    mapa = {}
    for fila in agregados:
        usado = float(fila['usado'] or 0)
        producido = float(fila['producido'] or 0)
        if usado <= 0:
            continue
        mapa[fila['mp_id']] = round((producido / usado) * 100, 2)
    return mapa


def ids_rollos_rendimiento_bajo(umbral=UMBRAL_RENDIMIENTO_ROLLO):
    """IDs de MateriaPrima 'Terminadas' cuyo rendimiento total está por
    debajo de `umbral` (96.5% por defecto)."""
    mapa = mapa_rendimiento_rollos_terminados()
    return [mp_id for mp_id, pct in mapa.items() if pct < umbral]
