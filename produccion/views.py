from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from .models import OrdenProduccion
from .forms import OrdenProduccionForm, DetalleSlitterFormSet


@login_required
def captura_orden(request):
    if not request.user.groups.filter(name__in=['Administrador', 'Supervisor', 'Operador']).exists():
        return HttpResponse("No tienes permiso para capturar órdenes.")

    mensaje = ''
    error = ''

    if request.method == 'POST':
        form = OrdenProduccionForm(request.POST)
        formset = DetalleSlitterFormSet(request.POST, prefix='detalles')

        if form.is_valid() and formset.is_valid():
            orden = form.save(commit=False)
            tipo = orden.tipo_proceso
            detalles = formset.save(commit=False)

            if tipo == 'slitter':
                suma_pesos = 0

                for d in detalles:
                    if d.peso:
                        suma_pesos += float(d.peso)

                if orden.peso_usado:
                    diferencia = float(orden.peso_usado) - suma_pesos
                else:
                    diferencia = 0

                orden.peso_producido = suma_pesos
                orden.scrap_total = diferencia if diferencia > 0 else 0
            else:
                detalles = []

            orden.save()

            for d in detalles:
                d.orden = orden
                d.save()

            for obj in formset.deleted_objects:
                obj.delete()

            mensaje = 'Orden registrada correctamente.'
            form = OrdenProduccionForm()
            formset = DetalleSlitterFormSet(prefix='detalles')
    else:
        form = OrdenProduccionForm()
        formset = DetalleSlitterFormSet(prefix='detalles')

    return render(request, 'produccion/captura_orden.html', {
        'form': form,
        'formset': formset,
        'mensaje': mensaje,
        'error': error,
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