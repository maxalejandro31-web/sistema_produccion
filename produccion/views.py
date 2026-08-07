from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib import messages
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST

from .models import OrdenProduccion
from .forms import OrdenProduccionForm, DetalleSlitterFormSet, DetalleFlejeFormSet
from .analitica import anotar_anomalias
from core.decorators import roles_required, solo_dueno_puede_eliminar
from inventario.models import Cliente
from dashboard.models import registrar_historial


def _calcular_scrap_merma(orden):
    """Scrap total y merma se derivan de peso_usado - peso_producido, para
    los cuatro tipos de proceso (slitter/fleje ya traen peso_producido
    calculado desde su detalle; corte_liso/mini_slitter lo capturan a mano)."""
    if orden.peso_usado is not None and orden.peso_producido is not None:
        diferencia = float(orden.peso_usado) - float(orden.peso_producido)
    else:
        diferencia = 0
    diferencia = diferencia if diferencia > 0 else 0
    orden.scrap_total = diferencia
    orden.merma_kg = diferencia


@roles_required('Administrador', 'Supervisor', 'Operador', 'Capturista', 'Coordinador')
def captura_orden(request):
    if request.method == 'POST':
        form = OrdenProduccionForm(request.POST)
        formset = DetalleSlitterFormSet(request.POST, prefix='detalles')
        formset_fleje = DetalleFlejeFormSet(request.POST, prefix='detalles_fleje')

        if form.is_valid() and formset.is_valid() and formset_fleje.is_valid():
            orden = form.save(commit=False)
            tipo = orden.tipo_proceso
            detalles = formset.save(commit=False)
            detalles_fleje = formset_fleje.save(commit=False)

            if tipo == 'slitter':
                suma_pesos = 0

                for d in detalles:
                    if d.peso:
                        suma_pesos += float(d.peso)

                orden.peso_producido = suma_pesos
                detalles_fleje = []
            elif tipo == 'fleje':
                suma_pesos = sum(
                    float(d.peso_descarga) for d in detalles_fleje if d.peso_descarga
                )
                orden.peso_producido = suma_pesos
                if orden.peso_rollo_padre:
                    orden.peso_usado = orden.peso_rollo_padre
                orden.mp = None
                detalles = []
            else:
                detalles = []
                detalles_fleje = []

            _calcular_scrap_merma(orden)

            try:
                orden.save()
            except ValueError as e:
                messages.error(request, str(e))
                return render(request, 'produccion/captura_orden.html', {
                    'form': form,
                    'formset': formset,
                    'formset_fleje': formset_fleje,
                })

            for d in detalles:
                d.orden = orden
                d.save()
            for obj in formset.deleted_objects:
                obj.delete()

            for d in detalles_fleje:
                d.orden = orden
                d.save()
            for obj in formset_fleje.deleted_objects:
                obj.delete()

            registrar_historial(request, 'OrdenProduccion', orden.id, str(orden), 'CREAR',
                f'Orden {orden.folio_orden or orden.id} creada.')
            messages.success(request, 'Orden registrada correctamente.')
            form = OrdenProduccionForm()
            formset = DetalleSlitterFormSet(prefix='detalles')
            formset_fleje = DetalleFlejeFormSet(prefix='detalles_fleje')
    else:
        form = OrdenProduccionForm()
        formset = DetalleSlitterFormSet(prefix='detalles')
        formset_fleje = DetalleFlejeFormSet(prefix='detalles_fleje')

    return render(request, 'produccion/captura_orden.html', {
        'form': form,
        'formset': formset,
        'formset_fleje': formset_fleje,
    })


@roles_required('Administrador', 'Supervisor', 'Operador', 'Capturista', 'Coordinador')
def lista_ordenes(request):
    estado       = request.GET.get('estado', '')
    tipo_proceso = request.GET.get('tipo_proceso', '')
    fecha_inicio = request.GET.get('fecha_inicio', '')
    fecha_fin    = request.GET.get('fecha_fin', '')
    q            = request.GET.get('q', '')
    cliente_id   = request.GET.get('cliente', '')

    qs = OrdenProduccion.objects.select_related(
        'cliente', 'mp', 'linea'
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
    if cliente_id:
        qs = qs.filter(cliente_id=cliente_id)

    paginator = Paginator(qs, 25)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'produccion/lista_ordenes.html', {
        'ordenes': anotar_anomalias(page_obj),
        'page_obj': page_obj,
        'estado': estado,
        'tipo_proceso': tipo_proceso,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'q': q,
        'cliente_id': cliente_id,
        'clientes': Cliente.objects.filter(activo=True).order_by('nombre'),
    })


@roles_required('Administrador', 'Supervisor', 'Coordinador')
def cambiar_estado(request, orden_id, nuevo_estado):
    estados_validos = ['pendiente', 'proceso', 'terminado']
    if nuevo_estado not in estados_validos:
        return HttpResponse("Estado no válido.")

    orden = get_object_or_404(OrdenProduccion, id=orden_id)
    orden.estado = nuevo_estado
    orden.save()

    etiquetas = {'pendiente': 'Pendiente', 'proceso': 'En Proceso', 'terminado': 'Terminado'}
    registrar_historial(request, 'OrdenProduccion', orden.id, str(orden), 'ESTADO',
        f'Estado cambiado a {etiquetas[nuevo_estado]}.')
    messages.success(request, f'Orden {orden.folio_orden or orden.id} cambiada a {etiquetas[nuevo_estado]}.')
    return redirect('lista_ordenes')


@solo_dueno_puede_eliminar
@require_POST
def eliminar_orden(request, orden_id):
    orden = get_object_or_404(OrdenProduccion, id=orden_id)
    folio = orden.folio_orden or orden.id
    registrar_historial(request, 'OrdenProduccion', orden.id, str(orden), 'ELIMINAR', f'Orden {folio} eliminada.')
    orden.delete()
    messages.success(request, f'Orden {folio} eliminada correctamente.')
    return redirect('lista_ordenes')


@roles_required('Administrador', 'Supervisor', 'Coordinador')
def editar_orden(request, orden_id):
    orden = get_object_or_404(OrdenProduccion, id=orden_id)

    try:
        if request.method == 'POST':
            form = OrdenProduccionForm(request.POST, instance=orden)
            formset = DetalleSlitterFormSet(request.POST, instance=orden, prefix='detalles')
            formset_fleje = DetalleFlejeFormSet(request.POST, instance=orden, prefix='detalles_fleje')

            if form.is_valid() and formset.is_valid() and formset_fleje.is_valid():
                orden_actualizada = form.save(commit=False)

                detalles = formset.save(commit=False)
                for d in detalles:
                    d.orden = orden_actualizada
                    d.save()
                for obj in formset.deleted_objects:
                    obj.delete()

                detalles_fleje = formset_fleje.save(commit=False)
                for d in detalles_fleje:
                    d.orden = orden_actualizada
                    d.save()
                for obj in formset_fleje.deleted_objects:
                    obj.delete()

                if orden_actualizada.tipo_proceso == 'slitter':
                    suma_pesos = sum(
                        float(d.peso) for d in orden_actualizada.detalles_slitter.all() if d.peso
                    )
                    orden_actualizada.peso_producido = suma_pesos
                elif orden_actualizada.tipo_proceso == 'fleje':
                    suma_pesos = sum(
                        float(d.peso_descarga) for d in orden_actualizada.detalles_fleje.all() if d.peso_descarga
                    )
                    orden_actualizada.peso_producido = suma_pesos
                    if orden_actualizada.peso_rollo_padre:
                        orden_actualizada.peso_usado = orden_actualizada.peso_rollo_padre
                    orden_actualizada.mp = None

                _calcular_scrap_merma(orden_actualizada)
                orden_actualizada.save()

                registrar_historial(request, 'OrdenProduccion', orden.id, str(orden), 'EDITAR',
                    f'Orden {orden.folio_orden or orden.id} actualizada.')
                messages.success(request, f'Orden {orden.folio_orden or orden.id} actualizada correctamente.')
                return redirect('lista_ordenes')
        else:
            form = OrdenProduccionForm(instance=orden)
            formset = DetalleSlitterFormSet(instance=orden, prefix='detalles')
            formset_fleje = DetalleFlejeFormSet(instance=orden, prefix='detalles_fleje')

        return render(request, 'produccion/editar_orden.html', {
            'form': form,
            'formset': formset,
            'formset_fleje': formset_fleje,
            'orden': orden,
        })

    except Exception as e:
        return HttpResponse(f"Error al editar orden: {e}")


@roles_required('Administrador', 'Supervisor', 'Operador', 'Capturista', 'Coordinador')
def imprimir_orden(request, orden_id):
    orden = get_object_or_404(
        OrdenProduccion.objects.select_related('cliente', 'mp', 'linea', 'pt_origen'),
        id=orden_id
    )
    detalles = orden.detalles_slitter.all()
    detalles_fleje = orden.detalles_fleje.all()
    return render(request, 'produccion/imprimir_orden.html', {
        'orden': orden,
        'detalles': detalles,
        'detalles_fleje': detalles_fleje,
    })


@roles_required('Administrador', 'Supervisor', 'Operador', 'Capturista', 'Coordinador')
def detalle_orden(request, orden_id):
    orden = get_object_or_404(
        OrdenProduccion.objects.select_related('cliente', 'mp', 'linea', 'pt_origen'),
        id=orden_id
    )
    orden = anotar_anomalias([orden])[0]
    detalles = orden.detalles_slitter.all()
    detalles_fleje = orden.detalles_fleje.all()

    from dashboard.models import HistorialCambio
    historial = HistorialCambio.objects.filter(
        tipo_objeto='OrdenProduccion', objeto_id=orden_id
    ).select_related('usuario')

    return render(request, 'produccion/detalle_orden.html', {
        'orden': orden,
        'detalles': detalles,
        'detalles_fleje': detalles_fleje,
        'historial': historial,
    })