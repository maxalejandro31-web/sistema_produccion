def permisos_usuario(request):
    import datetime
    from django.conf import settings
    from django.utils import timezone
    from dashboard.models import ConfiguracionEmpresa

    if not request.user.is_authenticated:
        return {
            'es_admin_total': False,
            'es_administrador': False,
            'es_supervisor': False,
            'es_almacen': False,
            'es_operador': False,
            'es_capturista': False,
            'es_coordinador': False,
            'puede_eliminar': False,
            'config_empresa': ConfiguracionEmpresa.get(),
            'alertas_count': 0,
            'alertas_items': [],
        }

    es_superuser = request.user.is_superuser
    grupos = set(request.user.groups.values_list('name', flat=True))

    # ── Alertas globales (campanita del navbar) ─────────────────────────────
    # Misma función que arma las tarjetas del dashboard (dashboard/alertas.py)
    # — antes cada uno calculaba esto por su cuenta y la campanita solo
    # cubría 3 de las 5 categorías de alerta reales, así que podía mostrar
    # "sin alertas" mientras el dashboard sí mostraba una.
    alertas_items = []
    alertas_count = 0
    try:
        from dashboard.alertas import obtener_alertas
        alertas_items = obtener_alertas()
        alertas_count = sum(a['count'] for a in alertas_items)
    except Exception:
        # No queremos que un error aquí tumbe TODAS las páginas del sistema
        # (este context processor corre en cada request), pero tampoco debe
        # desaparecer en silencio: si algo falla, las alertas de la campana
        # simplemente se quedan en 0/vacías, y aquí queda registrado el motivo.
        import logging
        logging.getLogger(__name__).exception(
            "Error calculando alertas globales en permisos_usuario()"
        )

    return {
        'es_admin_total': es_superuser,
        'es_administrador': 'Administrador' in grupos,
        'es_supervisor': 'Supervisor' in grupos,
        'es_almacen': 'Almacen' in grupos,
        'es_operador': 'Operador' in grupos,
        'es_capturista': 'Capturista' in grupos,
        'es_coordinador': 'Coordinador' in grupos,
        'puede_eliminar': request.user.username == settings.USUARIO_CON_PERMISO_ELIMINAR,
        'config_empresa': ConfiguracionEmpresa.get(),
        'alertas_count': alertas_count,
        'alertas_items': alertas_items,
    }