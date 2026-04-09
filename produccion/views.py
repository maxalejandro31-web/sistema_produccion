from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from .models import OrdenProduccion
from .forms import OrdenProduccionForm


@login_required
def captura_orden(request):
    if not request.user.groups.filter(name__in=['Administrador', 'Supervisor', 'Operador']).exists():
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
        return HttpResponse("No tienes permiso para ver órdenes.")

    ordenes = OrdenProduccion.objects.select_related(
        'cliente', 'mp', 'linea', 'operador'
    ).order_by('-id')

    return render(request, 'produccion/lista_ordenes.html', {
        'ordenes': ordenes
    })


@login_required
def cambiar_estado(request, orden_id, nuevo_estado):
    if not request.user.groups.filter(name__in=['Administrador', 'Supervisor']).exists():
        return HttpResponse("No tienes permiso para cambiar el estado de la orden.")

    estados_validos = ['pendiente', 'proceso', 'terminado']
    if nuevo_estado not in estados_validos:
        return HttpResponse("Estado no válido.")

    orden = get_object_or_404(OrdenProduccion, id=orden_id)

    # Actualiza solo el estado, sin volver a ejecutar lógica completa del save
    OrdenProduccion.objects.filter(id=orden.id).update(estado=nuevo_estado)

    return redirect('lista_ordenes')


@login_required
def editar_orden(request, orden_id):
    if not request.user.groups.filter(name__in=['Administrador', 'Supervisor']).exists():
        return HttpResponse("No tienes permiso para editar órdenes.")

    orden = get_object_or_404(OrdenProduccion, id=orden_id)

    try:
        if request.method == 'POST':
            form = OrdenProduccionForm(request.POST, instance=orden)
            if form.is_valid():
                orden_actualizada = form.save(commit=False)
                orden_actualizada.save()
                return redirect('lista_ordenes')
        else:
            form = OrdenProduccionForm(instance=orden)

        return render(request, 'produccion/editar_orden.html', {
            'form': form,
            'orden': orden,
        })

    except Exception as e:
        return HttpResponse(f"Error al editar orden: {e}")


@login_required
def detalle_orden(request, orden_id):
    if not request.user.groups.filter(name__in=['Administrador', 'Supervisor', 'Operador']).exists():
        return HttpResponse("No tienes permiso para ver esta orden.")

    orden = get_object_or_404(
        OrdenProduccion.objects.select_related('cliente', 'mp', 'linea', 'operador'),
        id=orden_id
    )
    detalles = orden.detalles_slitter.all()

    return render(request, 'produccion/detalle_orden.html', {
        'orden': orden,
        'detalles': detalles,
    })