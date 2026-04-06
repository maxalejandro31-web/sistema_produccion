from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from .forms import OrdenProduccionForm
from .models import OrdenProduccion


@login_required
def captura_orden(request):
    if not request.user.groups.filter(name__in=['Administrador', 'Operador']).exists():
        return HttpResponse("No tienes permiso para capturar órdenes.")

    mensaje = ''

    if request.method == 'POST':
        form = OrdenProduccionForm(request.POST)
        if form.is_valid():
            form.save()
            mensaje = 'Orden registrada correctamente.'
            form = OrdenProduccionForm()
    else:
        form = OrdenProduccionForm()

    return render(request, 'produccion/captura_orden.html', {
        'form': form,
        'mensaje': mensaje,
    })


@login_required
def lista_ordenes(request):
    if not request.user.groups.filter(name__in=['Administrador', 'Supervisor', 'Operador']).exists():
        return HttpResponse("No tienes permiso para ver las órdenes.")

    ordenes = OrdenProduccion.objects.select_related('cliente', 'mp', 'linea').all().order_by('-fecha')

    return render(request, 'produccion/lista_ordenes.html', {
        'ordenes': ordenes,
    })


@login_required
def cambiar_estado(request, orden_id, nuevo_estado):
    if not request.user.groups.filter(name__in=['Administrador', 'Supervisor']).exists():
        return HttpResponse("No tienes permiso para cambiar el estado.")

    estados_validos = ['pendiente', 'proceso', 'terminado']
    if nuevo_estado not in estados_validos:
        return HttpResponse("Estado no válido.")

    orden = get_object_or_404(OrdenProduccion, id=orden_id)
    orden.estado = nuevo_estado

    if orden.mp:
        if nuevo_estado == 'pendiente':
            orden.mp.estado = 'Disponible'
        elif nuevo_estado == 'proceso':
            orden.mp.estado = 'En Proceso'
        elif nuevo_estado == 'terminado':
            orden.mp.estado = 'Terminado'
        orden.mp.save()

    orden.save()

    return redirect('lista_ordenes')


@login_required
def editar_orden(request, orden_id):
    if not request.user.groups.filter(name__in=['Administrador', 'Supervisor']).exists():
        return HttpResponse("No tienes permiso para editar órdenes.")

    orden = get_object_or_404(OrdenProduccion, id=orden_id)

    if request.method == 'POST':
        form = OrdenProduccionForm(request.POST, instance=orden)
        if form.is_valid():
            form.save()
            return redirect('lista_ordenes')
    else:
        form = OrdenProduccionForm(instance=orden)

    return render(request, 'produccion/editar_orden.html', {
        'form': form,
        'orden': orden,
    })


@login_required
def detalle_orden(request, orden_id):
    if not request.user.groups.filter(name__in=['Administrador', 'Supervisor', 'Operador']).exists():
        return HttpResponse("No tienes permiso para ver la orden.")

    orden = get_object_or_404(OrdenProduccion, id=orden_id)

    return render(request, 'produccion/detalle_orden.html', {
        'orden': orden,
    })