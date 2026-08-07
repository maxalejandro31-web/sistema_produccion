from functools import wraps
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse


def roles_required(*roles):
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            if request.user.groups.filter(name__in=roles).exists():
                return view_func(request, *args, **kwargs)

            return HttpResponse("No tienes permisos para acceder a esta sección.")
        return _wrapped_view
    return decorator


def solo_dueno_puede_eliminar(view_func):
    """Restringe la vista al único usuario autorizado a borrar registros
    (settings.USUARIO_CON_PERMISO_ELIMINAR), sin importar rol o superuser."""
    @login_required
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if request.user.username != settings.USUARIO_CON_PERMISO_ELIMINAR:
            return HttpResponse("No tienes permisos para eliminar este registro.", status=403)
        return view_func(request, *args, **kwargs)
    return _wrapped_view