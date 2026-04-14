from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.db.models import Sum

from .forms import MateriaPrimaForm, ClienteForm
from .models import MateriaPrima, Cliente
from produccion.models import OrdenProduccion


@login_required
def captura_mp(request):
    if not request.user.groups.filter(name__in=['Administrador', 'Operador', 'Supervisor']).exists():
        return HttpResponse("No tienes permiso para capturar materia prima.")

    mensaje = ''

    if request.method == 'POST':
        form = MateriaPrimaForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            mensaje = 'Materia prima registrada correctamente.'
            form = MateriaPrimaForm()
    else:
        form = MateriaPrimaForm()

    return render(request, 'inventario/captura_mp.html', {
        'form': form,
        'mensaje': mensaje,
    })


@login_required
def lista_mp(request):
    if not request.user.groups.filter(name__in=['Administrador', 'Supervisor', 'Operador']).exists():
        return HttpResponse("No tienes permiso para ver la materia prima.")

    busqueda = request.GET.get('q', '')
    tipo = request.GET.get('tipo', '')
    estado = request.GET.get('estado', '')

    materias_primas = MateriaPrima.objects.all().order_by('-id')

    if busqueda:
        materias_primas = materias_primas.filter(numero_mp__icontains=busqueda)

    if tipo:
        materias_primas = materias_primas.filter(tipo_mp=tipo)

    if estado:
        materias_primas = materias_primas.filter(estado=estado)

    return render(request, 'inventario/lista_mp.html', {
        'materias_primas': materias_primas,
        'busqueda': busqueda,
        'tipo': tipo,
        'estado': estado,
    })


@login_required
def editar_mp(request, mp_id):
    if not request.user.groups.filter(name__in=['Administrador', 'Supervisor']).exists():
        return HttpResponse("No tienes permiso para editar materia prima.")

    mp = get_object_or_404(MateriaPrima, id=mp_id)

    if request.method == 'POST':
        form = MateriaPrimaForm(request.POST, request.FILES, instance=mp)
        if form.is_valid():
            form.save()
            return redirect('lista_mp')
    else:
        form = MateriaPrimaForm(instance=mp)

    return render(request, 'inventario/editar_mp.html', {
        'form': form,
        'mp': mp,
    })


@login_required
def detalle_mp(request, mp_id):
    if not request.user.groups.filter(name__in=['Administrador', 'Supervisor', 'Operador']).exists():
        return HttpResponse("No tienes permiso para ver la materia prima.")

    mp = get_object_or_404(MateriaPrima, id=mp_id)

    ordenes_relacionadas = OrdenProduccion.objects.select_related(
        'cliente', 'linea', 'operador'
    ).filter(mp=mp).order_by('-id')

    total_consumido = ordenes_relacionadas.aggregate(total=Sum('peso_usado'))['total'] or 0
    total_producido = ordenes_relacionadas.aggregate(total=Sum('peso_producido'))['total'] or 0
    total_scrap = ordenes_relacionadas.aggregate(total=Sum('scrap_total'))['total'] or 0
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
    if not request.user.groups.filter(name__in=['Administrador', 'Supervisor']).exists():
        return HttpResponse("No tienes permiso para ver clientes.")

    busqueda = request.GET.get('q', '')
    clientes = Cliente.objects.all().order_by('nombre')

    if busqueda:
        clientes = clientes.filter(nombre__icontains=busqueda)

    return render(request, 'inventario/lista_clientes.html', {
        'clientes': clientes,
        'busqueda': busqueda,
    })


@login_required
def captura_cliente(request):
    if not request.user.groups.filter(name__in=['Administrador', 'Supervisor']).exists():
        return HttpResponse("No tienes permiso para capturar clientes.")

    mensaje = ''

    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            form.save()
            mensaje = 'Cliente registrado correctamente.'
            form = ClienteForm()
    else:
        form = ClienteForm()

    return render(request, 'inventario/captura_cliente.html', {
        'form': form,
        'mensaje': mensaje,
    })


@login_required
def editar_cliente(request, cliente_id):
    if not request.user.groups.filter(name__in=['Administrador', 'Supervisor']).exists():
        return HttpResponse("No tienes permiso para editar clientes.")

    cliente = get_object_or_404(Cliente, id=cliente_id)

    if request.method == 'POST':
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            form.save()
            return redirect('lista_clientes')
    else:
        form = ClienteForm(instance=cliente)

    return render(request, 'inventario/editar_cliente.html', {
        'form': form,
        'cliente': cliente,
    })