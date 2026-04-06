import csv
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.db.models import Sum, Count
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout

from inventario.models import MateriaPrima
from produccion.models import OrdenProduccion


def login_view(request):
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
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')

    mp_qs = MateriaPrima.objects.all()
    ordenes_qs = OrdenProduccion.objects.all()

    if fecha_inicio:
        ordenes_qs = ordenes_qs.filter(fecha__date__gte=fecha_inicio)

    if fecha_fin:
        ordenes_qs = ordenes_qs.filter(fecha__date__lte=fecha_fin)

    total_mp = mp_qs.count()
    mp_disponible = mp_qs.filter(estado='Disponible').count()
    mp_proceso = mp_qs.filter(estado='En Proceso').count()
    mp_terminado = mp_qs.filter(estado='Terminado').count()

    peso_total = mp_qs.aggregate(total=Sum('peso'))['total'] or 0
    peso_restante = mp_qs.aggregate(total=Sum('peso_restante'))['total'] or 0

    total_ordenes = ordenes_qs.count()
    ordenes_pendientes = ordenes_qs.filter(estado='pendiente').count()
    ordenes_proceso = ordenes_qs.filter(estado='proceso').count()
    ordenes_terminadas = ordenes_qs.filter(estado='terminado').count()

    produccion_total = ordenes_qs.aggregate(total=Sum('peso_producido'))['total'] or 0
    consumo_total = ordenes_qs.aggregate(total=Sum('peso_usado'))['total'] or 0

    ultimas_ordenes = ordenes_qs.select_related('cliente', 'mp', 'linea').order_by('-fecha')[:5]
    mp_baja = mp_qs.filter(peso_restante__lt=1000).order_by('peso_restante')[:5]

    ordenes_labels = ['Pendientes', 'En proceso', 'Terminadas']
    ordenes_data = [ordenes_pendientes, ordenes_proceso, ordenes_terminadas]

    mp_labels = ['Disponible', 'En Proceso', 'Terminado']
    mp_data = [mp_disponible, mp_proceso, mp_terminado]

    context = {
        'total_mp': total_mp,
        'mp_disponible': mp_disponible,
        'mp_proceso': mp_proceso,
        'mp_terminado': mp_terminado,
        'peso_total': peso_total,
        'peso_restante': peso_restante,
        'total_ordenes': total_ordenes,
        'ordenes_pendientes': ordenes_pendientes,
        'ordenes_proceso': ordenes_proceso,
        'ordenes_terminadas': ordenes_terminadas,
        'produccion_total': produccion_total,
        'consumo_total': consumo_total,
        'ultimas_ordenes': ultimas_ordenes,
        'mp_baja': mp_baja,
        'fecha_inicio': fecha_inicio or '',
        'fecha_fin': fecha_fin or '',
        'ordenes_labels': ordenes_labels,
        'ordenes_data': ordenes_data,
        'mp_labels': mp_labels,
        'mp_data': mp_data,
    }

    return render(request, 'dashboard/inicio.html', context)


@login_required
def exportar_excel(request):
    ordenes = OrdenProduccion.objects.select_related('cliente', 'mp', 'linea').all()

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="ordenes_produccion.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Folio',
        'Cliente',
        'Materia Prima',
        'Linea',
        'Peso usado',
        'Peso producido',
        'Estado',
        'Fecha'
    ])

    for orden in ordenes:
        writer.writerow([
            orden.folio_orden,
            orden.cliente,
            orden.mp,
            orden.linea,
            orden.peso_usado,
            orden.peso_producido,
            orden.estado,
            orden.fecha,
        ])

    return response