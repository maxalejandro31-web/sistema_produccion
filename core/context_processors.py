def permisos_usuario(request):
    if not request.user.is_authenticated:
        return {
            'es_admin_total': False,
            'es_administrador': False,
            'es_supervisor': False,
            'es_almacen': False,
            'es_operador': False,
        }

    es_superuser = request.user.is_superuser
    grupos = set(request.user.groups.values_list('name', flat=True))

    return {
        'es_admin_total': es_superuser,
        'es_administrador': 'Administrador' in grupos,
        'es_supervisor': 'Supervisor' in grupos,
        'es_almacen': 'Almacen' in grupos,
        'es_operador': 'Operador' in grupos,
    }