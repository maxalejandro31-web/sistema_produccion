from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Sum

from .forms import MateriaPrimaForm, ClienteForm
from .models import MateriaPrima, Cliente
from produccion.models import OrdenProduccion


@login_required
def captura_mp(request):
    if request.method == 'POST':
        form = MateriaPrimaForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'Materia prima registrada correctamente.')
            form = MateriaPrimaForm()
    else:
        form = MateriaPrimaForm()

    return render(request, 'inventario/captura_mp.html', {'form': form})


@login_required
def lista_mp(request):
    busqueda      = request.GET.get('q', '')
    tipo          = request.GET.get('tipo', '')
    estado        = request.GET.get('estado', '')
    fecha_inicio  = request.GET.get('fecha_inicio', '')
    fecha_fin     = request.GET.get('fecha_fin', '')

    qs = MateriaPrima.objects.select_related('cliente').order_by('-id')

    if busqueda:
        qs = qs.filter(numero_mp__icontains=busqueda)
    if tipo:
        qs = qs.filter(tipo_mp=tipo)
    if estado:
        qs = qs.filter(estado=estado)
    if fecha_inicio:
        qs = qs.filter(fecha_entrada__gte=fecha_inicio)
    if fecha_fin:
        qs = qs.filter(fecha_entrada__lte=fecha_fin)

    paginator = Paginator(qs, 25)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'inventario/lista_mp.html', {
        'materias_primas': page_obj,
        'page_obj': page_obj,
        'busqueda': busqueda,
        'tipo': tipo,
        'estado': estado,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
    })


@login_required
def editar_mp(request, mp_id):
    if not (
        request.user.is_superuser or
        request.user.groups.filter(name__in=['Administrador', 'Supervisor']).exists()
    ):
        return HttpResponse("No tienes permiso para editar materia prima.")

    mp = get_object_or_404(MateriaPrima, id=mp_id)

    if request.method == 'POST':
        form = MateriaPrimaForm(request.POST, request.FILES, instance=mp)
        if form.is_valid():
            form.save()
            messages.success(request, f'Materia prima {mp.numero_mp} actualizada correctamente.')
            return redirect('lista_mp')
    else:
        form = MateriaPrimaForm(instance=mp)

    return render(request, 'inventario/editar_mp.html', {
        'form': form,
        'mp': mp,
    })


@login_required
def detalle_mp(request, mp_id):
    if not (
        request.user.is_superuser or
        request.user.groups.filter(name__in=['Administrador', 'Supervisor', 'Operador', 'Almacen']).exists()
    ):
        return HttpResponse("No tienes permiso para ver la materia prima.")

    mp = get_object_or_404(MateriaPrima, id=mp_id)

    ordenes_relacionadas = OrdenProduccion.objects.select_related(
        'cliente', 'linea', 'operador'
    ).filter(mp_id=mp.id).order_by('-id')

    resumen = ordenes_relacionadas.aggregate(
        total_consumido=Sum('peso_usado'),
        total_producido=Sum('peso_producido'),
        total_scrap=Sum('scrap_total'),
    )

    total_consumido = resumen['total_consumido'] or 0
    total_producido = resumen['total_producido'] or 0
    total_scrap = resumen['total_scrap'] or 0
    cantidad_ordenes = ordenes_relacionadas.count()

    return render(request, 'inventario/detalle_mp.html', {
        'mp': mp,
        'ordenes_relacionadas': ordenes_relacionadas,
        'total_consumido': total_consumido,
        'total_producido': total_producido,
        'total_scrap': total_scrap,
        'cantidad_ordenes': cantidad_ordenes,
    })


@login_required
def lista_clientes(request):
    if not (
        request.user.is_superuser or
        request.user.groups.filter(name__in=['Administrador', 'Supervisor']).exists()
    ):
        return HttpResponse("No tienes permiso para ver clientes.")

    busqueda = request.GET.get('q', '')
    qs = Cliente.objects.all().order_by('nombre')
    if busqueda:
        qs = qs.filter(nombre__icontains=busqueda)

    paginator = Paginator(qs, 25)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'inventario/lista_clientes.html', {
        'clientes': page_obj,
        'page_obj': page_obj,
        'busqueda': busqueda,
    })


@login_required
def captura_cliente(request):
    if not (
        request.user.is_superuser or
        request.user.groups.filter(name__in=['Administrador', 'Supervisor']).exists()
    ):
        return HttpResponse("No tienes permiso para capturar clientes.")

    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cliente registrado correctamente.')
            form = ClienteForm()
    else:
        form = ClienteForm()

    return render(request, 'inventario/captura_cliente.html', {'form': form})


@login_required
def editar_cliente(request, cliente_id):
    if not (
        request.user.is_superuser or
        request.user.groups.filter(name__in=['Administrador', 'Supervisor']).exists()
    ):
        return HttpResponse("No tienes permiso para editar clientes.")

    cliente = get_object_or_404(Cliente, id=cliente_id)

    if request.method == 'POST':
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            form.save()
            messages.success(request, f'Cliente {cliente.nombre} actualizado correctamente.')
            return redirect('lista_clientes')
    else:
        form = ClienteForm(instance=cliente)

    return render(request, 'inventario/editar_cliente.html', {
        'form': form,
        'cliente': cliente,
    })
