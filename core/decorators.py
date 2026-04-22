from functools import wraps
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