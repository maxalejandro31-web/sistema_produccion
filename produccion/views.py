from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib import messages
from django.core.paginator import Paginator

from .models import OrdenProduccion
from .forms import OrdenProduccionForm, DetalleSlitterFormSet
from core.decorators import roles_required


@roles_required('Administrador', 'Supervisor', 'Operador')
def captura_orden(request):
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

            messages.success(request, 'Orden registrada correctamente.')
            form = OrdenProduccionForm()
            formset = DetalleSlitterFormSet(prefix='detalles')
    else:
        form = OrdenProduccionForm()
        formset = DetalleSlitterFormSet(prefix='detalles')

    return render(request, 'produccion/captura_orden.html', {
        'form': form,
        'formset': formset,
    })


@roles_required('Administrador', 'Supervisor', 'Operador')
def lista_ordenes(request):
    estado       = request.GET.get('estado', '')
    tipo_proceso = request.GET.get('tipo_proceso', '')
    fecha_inicio = request.GET.get('fecha_inicio', '')
    fecha_fin    = request.GET.get('fecha_fin', '')
    q            = request.GET.get('q', '')

    qs = OrdenProduccion.objects.select_related(
        'cliente', 'mp', 'linea', 'operador'
    ).order_by('-id')

    if estado:
        qs = qs.filter(estado=estado)
    if tipo_proceso:
        qs = qs.filter(tipo_proceso=tipo_proceso)
    if fecha_inicio:
        qs = qs.filter(fecha__gte=fecha_inicio)
    if fecha_fin:
        qs = qs.filter(fecha__lte=fecha_fin)
    if q:
        qs = qs.filter(folio_orden__icontains=q)

    paginator = Paginator(qs, 25)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'produccion/lista_ordenes.html', {
        'ordenes': page_obj,
        'page_obj': page_obj,
        'estado': estado,
        'tipo_proceso': tipo_proceso,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'q': q,
    })


@roles_required('Administrador', 'Supervisor')
def cambiar_estado(request, orden_id, nuevo_estado):
    estados_validos = ['pendiente', 'proceso', 'terminado']
    if nuevo_estado not in estados_validos:
        return HttpResponse("Estado no válido.")

    orden = get_object_or_404(OrdenProduccion, id=orden_id)
    orden.estado = nuevo_estado
    orden.save()

    etiquetas = {'pendiente': 'Pendiente', 'proceso': 'En Proceso', 'terminado': 'Terminado'}
    messages.success(request, f'Orden {orden.folio_orden or orden.id} cambiada a {etiquetas[nuevo_estado]}.')
    return redirect('lista_ordenes')


@roles_required('Administrador', 'Supervisor')
def editar_orden(request, orden_id):
    orden = get_object_or_404(OrdenProduccion, id=orden_id)

    try:
        if request.method == 'POST':
            form = OrdenProduccionForm(request.POST, instance=orden)
            if form.is_valid():
                orden_actualizada = form.save(commit=False)
                orden_actualizada.save()
                messages.success(request, f'Orden {orden.folio_orden or orden.id} actualizada correctamente.')
                return redirect('lista_ordenes')
        else:
            form = OrdenProduccionForm(instance=orden)

        return render(request, 'produccion/editar_orden.html', {
            'form': form,
            'orden': orden,
        })

    except Exception as e:
        return HttpResponse(f"Error al editar orden: {e}")


@roles_required('Administrador', 'Supervisor', 'Operador')
def detalle_orden(request, orden_id):
    orden = get_object_or_404(
        OrdenProduccion.objects.select_related('cliente', 'mp', 'linea', 'operador'),
        id=orden_id
    )
    detalles = orden.detalles_slitter.all()

    return render(request, 'produccion/detalle_orden.html', {
        'orden': orden,
        'detalles': detalles,
    })