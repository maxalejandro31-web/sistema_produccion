def permisos_usuario(request):
    import datetime
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
            'config_empresa': ConfiguracionEmpresa.get(),
            'alertas_count': 0,
            'alertas_items': [],
        }

    es_superuser = request.user.is_superuser
    grupos = set(request.user.groups.values_list('name', flat=True))

    # ── Alertas globales ──────────────────────────────────────────────────────
    alertas_items = []
    mp_vencidas = mp_por_vencer = urgentes = 0
    try:
        from inventario.models import MateriaPrima
        from produccion.models import OrdenProduccion
        hoy = timezone.localdate()

        mp_vencidas = MateriaPrima.objects.filter(
            fecha_entrada__lt=hoy - datetime.timedelta(days=30)
        ).count()
        if mp_vencidas:
            alertas_items.append({
                'tipo': 'danger',
                'icono': '🔴',
                'texto': f'{mp_vencidas} MP con cobro activo',
                'url': '/lista-mp/?cobro=vencido',
            })

        mp_por_vencer = MateriaPrima.objects.filter(
            fecha_entrada__range=(
                hoy - datetime.timedelta(days=30),
                hoy - datetime.timedelta(days=23),
            )
        ).count()
        if mp_por_vencer:
            alertas_items.append({
                'tipo': 'warning',
                'icono': '⚠️',
                'texto': f'{mp_por_vencer} MP por vencer pronto',
                'url': '/lista-mp/?cobro=por_vencer',
            })

        urgentes = OrdenProduccion.objects.filter(
            estado__in=['pendiente', 'proceso'],
            prioridad='urgente',
        ).count()
        if urgentes:
            alertas_items.append({
                'tipo': 'warning',
                'icono': '⚡',
                'texto': f'{urgentes} orden(es) urgente(s)',
                'url': '/ordenes/?estado=proceso',
            })
    except Exception:
        pass

    alertas_count = mp_vencidas + mp_por_vencer + urgentes if alertas_items else 0

    return {
        'es_admin_total': es_superuser,
        'es_administrador': 'Administrador' in grupos,
        'es_supervisor': 'Supervisor' in grupos,
        'es_almacen': 'Almacen' in grupos,
        'es_operador': 'Operador' in grupos,
        'es_capturista': 'Capturista' in grupos,
        'es_coordinador': 'Coordinador' in grupos,
        'config_empresa': ConfiguracionEmpresa.get(),
        'alertas_count': alertas_count,
        'alertas_items': alertas_items,
    }