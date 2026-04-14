from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Sum

from inventario.models import MateriaPrima
from produccion.models import OrdenProduccion


def login_view(request):
    if request.user.is_authenticated:
        return redirect('inicio')

    error = ''

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect('inicio')
        else:
            error = 'Usuario o contraseña incorrectos'

    return render(request, 'dashboard/login.html', {'error': error})


def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def inicio(request):
    total_mp = MateriaPrima.objects.count()
    mp_disponible = MateriaPrima.objects.filter(estado='Disponible').count()
    mp_proceso = MateriaPrima.objects.filter(estado='En Proceso').count()
    mp_terminada = MateriaPrima.objects.filter(estado='Terminado').count()

    total_ordenes = OrdenProduccion.objects.count()
    ordenes_pendientes = OrdenProduccion.objects.filter(estado='pendiente').count()
    ordenes_proceso = OrdenProduccion.objects.filter(estado='proceso').count()
    ordenes_terminadas = OrdenProduccion.objects.filter(estado='terminado').count()

    peso_consumido = OrdenProduccion.objects.aggregate(total=Sum('peso_usado'))['total'] or 0
    peso_producido = OrdenProduccion.objects.aggregate(total=Sum('peso_producido'))['total'] or 0
    scrap_total = OrdenProduccion.objects.aggregate(total=Sum('scrap_total'))['total'] or 0

    ultimas_ordenes = OrdenProduccion.objects.select_related(
        'cliente', 'mp', 'linea', 'operador'
    ).order_by('-id')[:8]

    mp_critica = MateriaPrima.objects.order_by('peso_restante')[:8]

    context = {
        'total_mp': total_mp,
        'mp_disponible': mp_disponible,
        'mp_proceso': mp_proceso,
        'mp_terminada': mp_terminada,

        'total_ordenes': total_ordenes,
        'ordenes_pendientes': ordenes_pendientes,
        'ordenes_proceso': ordenes_proceso,
        'ordenes_terminadas': ordenes_terminadas,

        'peso_consumido': peso_consumido,
        'peso_producido': peso_producido,
        'scrap_total': scrap_total,

        'ultimas_ordenes': ultimas_ordenes,
        'mp_critica': mp_critica,
    }

    return render(request, 'dashboard/inicio.html', context)