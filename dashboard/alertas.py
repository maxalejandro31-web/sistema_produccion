"""Cálculo centralizado de las alertas activas del sistema.

Antes esto estaba duplicado en dos lugares que se fueron desincronizando:
`core/context_processors.py` (la campanita del navbar, visible en TODAS las
páginas) solo calculaba 3 de las 5 categorías de alerta que ya existían en
`dashboard/views.py::inicio()` (le faltaban las dos de rendimiento bajo) —
así que la campanita podía mostrar "sin alertas" mientras el dashboard sí
mostraba una. Ahora ambos llaman a `obtener_alertas()` y siempre van a
coincidir exactamente, porque literalmente comparten el mismo cálculo.

Cada alerta se recalcula en vivo contra la base de datos en cada llamada —
nunca se cachea — así que siempre refleja el estado actual, no una foto
vieja. Cada URL queda YA filtrada al subconjunto exacto de registros que
generó esa alerta (antes algunos links de la campanita llevaban a la lista
completa sin filtrar, o a un filtro que no coincidía con el cálculo real).
"""
import datetime

from django.template.defaultfilters import pluralize
from django.urls import reverse
from django.utils import timezone


def obtener_alertas():
    """Lista de alertas activas, en orden de severidad. Cada una es un dict:
    tipo (critica/rendimiento/aviso/info — define color e ícono en la UI),
    icono (nombre del set de partials/icono.html), titulo, descripcion,
    url (ya filtrada), cta (texto corto del botón), count (para el badge).
    """
    from inventario.models import MateriaPrima
    from produccion.models import OrdenProduccion
    from produccion.analitica import anotar_anomalias, ids_rollos_rendimiento_bajo

    hoy = timezone.localdate()
    alertas = []

    # ── Rendimiento (calidad/proceso) ───────────────────────────────────────
    rollos_bajo = len(ids_rollos_rendimiento_bajo())
    if rollos_bajo:
        alertas.append({
            'tipo': 'rendimiento', 'icono': 'tendencia-baja',
            'titulo': f'{rollos_bajo} rollo{pluralize(rollos_bajo, ",s")} con rendimiento total menor a 96.5%',
            'descripcion': 'Sumando todo lo producido contra todo lo consumido de ese rollo, ya terminado.',
            'url': f"{reverse('lista_mp')}?rendimiento_bajo=1",
            'cta': 'Ver rollos',
            'count': rollos_bajo,
        })

    ordenes_recientes_terminadas = OrdenProduccion.objects.select_related('mp').filter(
        estado='terminado', fecha__gte=hoy - datetime.timedelta(days=30),
    )
    ordenes_bajo = sum(
        1 for o in anotar_anomalias(ordenes_recientes_terminadas)
        if o.anomalia_rendimiento and o.anomalia_rendimiento['bucket'] == 'bajo'
    )
    if ordenes_bajo:
        alertas.append({
            'tipo': 'rendimiento', 'icono': 'tendencia-baja',
            'titulo': f'{ordenes_bajo} orden{pluralize(ordenes_bajo, ",es")} con rendimiento anómalo',
            'descripcion': 'En los últimos 30 días, muy por debajo del promedio histórico para ese material y proceso.',
            'url': f"{reverse('lista_ordenes')}?anomalia=bajo",
            'cta': 'Ver órdenes',
            'count': ordenes_bajo,
        })

    # ── Cobro por estancia (financiero) ─────────────────────────────────────
    # El material propio de la maquila nunca genera cobro — mismo exclude
    # que ya se usa en inventario/views.py, dashboard/views.py y el propio
    # reporte de Cobros por Estancia, para que el conteo de la campanita
    # coincida exactamente con lo que ves al hacer clic en "Ver MP".
    mp_vencidas = MateriaPrima.objects.filter(
        fecha_entrada__isnull=False,
        fecha_entrada__lt=hoy - datetime.timedelta(days=30),
    ).exclude(cliente__nombre='MAQUILAS Y SERVICIOS JC').count()
    if mp_vencidas:
        alertas.append({
            'tipo': 'critica', 'icono': 'alerta-circulo',
            'titulo': f'{mp_vencidas} materia prima con cobro por estancia activo',
            'descripcion': 'Superaron los 30 días de estadía gratuita.',
            'url': f"{reverse('lista_mp')}?cobro=vencido",
            'cta': 'Ver MP',
            'count': mp_vencidas,
        })

    mp_por_vencer = MateriaPrima.objects.filter(
        fecha_entrada__isnull=False,
        fecha_entrada__range=(hoy - datetime.timedelta(days=30), hoy - datetime.timedelta(days=23)),
    ).exclude(cliente__nombre='MAQUILAS Y SERVICIOS JC').count()
    if mp_por_vencer:
        alertas.append({
            'tipo': 'aviso', 'icono': 'alerta-triangulo',
            'titulo': f'{mp_por_vencer} materia prima por vencer',
            'descripcion': 'Quedan 7 días o menos para que inicie el cobro.',
            'url': f"{reverse('lista_mp')}?cobro=por_vencer",
            'cta': 'Ver MP',
            'count': mp_por_vencer,
        })

    # ── Producción (acción requerida) ───────────────────────────────────────
    ordenes_urgentes = OrdenProduccion.objects.filter(
        estado__in=['pendiente', 'proceso'], prioridad='urgente',
    ).count()
    if ordenes_urgentes:
        alertas.append({
            'tipo': 'info', 'icono': 'alerta-octagono',
            'titulo': f'{ordenes_urgentes} orden{pluralize(ordenes_urgentes, ",es")} urgente{pluralize(ordenes_urgentes)} pendiente{pluralize(ordenes_urgentes)}',
            'descripcion': 'Requieren atención inmediata.',
            'url': f"{reverse('lista_ordenes')}?urgentes=1",
            'cta': 'Ver órdenes',
            'count': ordenes_urgentes,
        })

    return alertas
