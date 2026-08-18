from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib import messages
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from django.db.models import ProtectedError

from .models import OrdenProduccion, DetalleSlitter
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


def _cortes_duplicados(mp, detalles, excluir_orden_id=None):
    """Números de corte que ya existen para este mismo rollo en OTRA orden.

    Un rollo se puede cortar en la slitter las veces que sea necesario, en
    órdenes distintas (p. ej. un remanente que se vuelve a pasar); lo que no
    debe pasar es que dos cortes distintos de ese mismo rollo terminen con
    el mismo No. de corte (y por lo tanto el mismo folio impreso)."""
    if not mp:
        return []
    numeros = [d.no_corte for d in detalles if d.no_corte]
    if not numeros:
        return []
    qs = DetalleSlitter.objects.filter(orden__mp=mp, no_corte__in=numeros)
    if excluir_orden_id:
        qs = qs.exclude(orden_id=excluir_orden_id)
    return sorted(set(qs.values_list('no_corte', flat=True)))


def _descripcion_pesos(orden):
    """Texto con los pesos capturados/calculados, para dejar constancia en
    el historial de exactamente qué se guardó (incluido lo automático)."""
    partes = []
    if orden.peso_usado is not None:
        partes.append(f'usado {orden.peso_usado} kg')
    if orden.peso_producido is not None:
        partes.append(f'producido {orden.peso_producido} kg')
    if orden.scrap_total is not None:
        partes.append(f'scrap {orden.scrap_total} kg')
    if orden.merma_kg is not None:
        partes.append(f'merma {orden.merma_kg} kg')
    return ' | '.join(partes)


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
                duplicados = _cortes_duplicados(orden.mp, detalles)
                if duplicados:
                    lista = ', '.join(str(n) for n in duplicados)
                    messages.error(
                        request,
                        f'El rollo {orden.mp.numero_mp} ya tiene registrado el corte No. {lista} '
                        'en otra orden. Usa un número de corte distinto (puede cortarse las veces '
                        'que sea necesario, pero cada corte debe tener su propio número).'
                    )
                    return render(request, 'produccion/captura_orden.html', {
                        'form': form,
                        'formset': formset,
                        'formset_fleje': formset_fleje,
                    })

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
                f'Orden {orden.folio_orden or orden.id} creada. {_descripcion_pesos(orden)}')
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
    orden_id_original = orden.id
    orden_str = str(orden)
    descripcion_pesos = _descripcion_pesos(orden)
    # Se guardan antes de borrar: al llamar orden.delete() Django limpia el
    # pk del objeto en memoria, y necesitamos estos datos después para
    # revertir el consumo de MP y para el historial.
    mp = orden.mp
    peso_a_revertir = orden.peso_usado

    try:
        orden.delete()
    except ProtectedError:
        messages.error(
            request,
            f'No se puede eliminar la orden {folio} porque ya generó producto '
            'terminado. Primero hay que eliminar o reasignar ese producto '
            'terminado (y cualquier remisión que lo incluya) antes de borrar '
            'la orden.'
        )
        return redirect('lista_ordenes')

    if mp and peso_a_revertir:
        # La orden había consumido peso de este rollo/placa (ver
        # OrdenProduccion.save()); al borrarla hay que devolver ese peso al
        # inventario, si no se queda descontado para siempre sin motivo.
        from inventario.models import MovimientoMP
        MovimientoMP.objects.create(
            mp=mp,
            tipo_movimiento='AJUSTE_POSITIVO',
            peso=peso_a_revertir,
            ubicacion_destino=mp.ubicacion or '',
            observaciones=f'Reversión automática por eliminación de orden {folio}.',
        )

    registrar_historial(request, 'OrdenProduccion', orden_id_original, orden_str, 'ELIMINAR',
        f'Orden {folio} eliminada. {descripcion_pesos}')
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

                if orden_actualizada.tipo_proceso == 'slitter':
                    duplicados = _cortes_duplicados(orden_actualizada.mp, detalles, excluir_orden_id=orden.id)
                    if duplicados:
                        lista = ', '.join(str(n) for n in duplicados)
                        messages.error(
                            request,
                            f'El rollo {orden_actualizada.mp.numero_mp} ya tiene registrado el corte '
                            f'No. {lista} en otra orden. Usa un número de corte distinto.'
                        )
                        return render(request, 'produccion/editar_orden.html', {
                            'form': form,
                            'formset': formset,
                            'formset_fleje': formset_fleje,
                            'orden': orden,
                        })

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
                    f'Orden {orden.folio_orden or orden.id} actualizada. {_descripcion_pesos(orden_actualizada)}')
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


def _resumen_aprovechamiento_mp(orden, detalles, ordenes_fleje_hijas):
    """Resumen de cierre del rollo: cuánto de la MP se aprovechó en fleje
    terminado y cuánto se fue en scrap/descarte a lo largo de toda la
    cadena MP → Slitter → Fleje, para el reporte final impreso."""
    peso_rollo = float(orden.mp.peso) if orden.mp and orden.mp.peso else 0

    peso_normal_slitter = sum(
        float(d.peso) for d in detalles if d.clasificacion == 'normal' and d.peso
    )
    peso_scrap_slitter = sum(
        float(d.peso_merma) for d in detalles if d.clasificacion == 'scrap' and d.peso_merma
    )
    peso_descarte_slitter = sum(
        float(d.peso_merma) for d in detalles if d.clasificacion == 'descarte' and d.peso_merma
    )

    peso_fleje_producido = sum(
        float(oh.peso_producido) for oh in ordenes_fleje_hijas if oh.peso_producido
    )
    scrap_fleje = sum(
        float(oh.scrap_total) for oh in ordenes_fleje_hijas if oh.scrap_total
    )

    scrap_total = peso_scrap_slitter + peso_descarte_slitter + scrap_fleje
    aprovechamiento_pct = round((peso_fleje_producido / peso_rollo) * 100, 2) if peso_rollo else None

    return {
        'peso_rollo': peso_rollo,
        'peso_normal_slitter': peso_normal_slitter,
        'peso_scrap_slitter': peso_scrap_slitter,
        'peso_descarte_slitter': peso_descarte_slitter,
        'peso_fleje_producido': peso_fleje_producido,
        'scrap_fleje': scrap_fleje,
        'scrap_total': scrap_total,
        'aprovechamiento_pct': aprovechamiento_pct,
    }


@roles_required('Administrador', 'Supervisor', 'Operador', 'Capturista', 'Coordinador')
def imprimir_orden(request, orden_id):
    orden = get_object_or_404(
        OrdenProduccion.objects.select_related('cliente', 'mp', 'linea', 'pt_origen'),
        id=orden_id
    )
    detalles = orden.detalles_slitter.all()
    detalles_fleje = orden.detalles_fleje.all()

    ordenes_fleje_hijas = []
    resumen_mp = None
    if orden.tipo_proceso == 'slitter':
        # Órdenes de fleje que consumieron alguno de los cortes de este rollo,
        # para reconstruir en el mismo reporte la cadena MP → Slitter → Fleje
        # tal como se ve en el formato de papel de planta.
        ordenes_fleje_hijas = OrdenProduccion.objects.filter(
            tipo_proceso='fleje',
            pt_origen__detalle_slitter__orden=orden,
        ).select_related(
            'pt_origen', 'pt_origen__detalle_slitter'
        ).prefetch_related('detalles_fleje').order_by('fecha')

        if orden.mp:
            resumen_mp = _resumen_aprovechamiento_mp(orden, detalles, ordenes_fleje_hijas)

    return render(request, 'produccion/imprimir_orden.html', {
        'orden': orden,
        'detalles': detalles,
        'detalles_fleje': detalles_fleje,
        'ordenes_fleje_hijas': ordenes_fleje_hijas,
        'resumen_mp': resumen_mp,
    })


@roles_required('Administrador', 'Supervisor', 'Operador', 'Capturista', 'Coordinador')
def detalle_orden(request, orden_id):
    orden = get_object_or_404(
        OrdenProduccion.objects.select_related('cliente', 'mp', 'linea', 'pt_origen'),
        id=orden_id
    )
    orden = anotar_anomalias([orden])[0]
    detalles = list(orden.detalles_slitter.all())
    detalles_fleje = orden.detalles_fleje.all()

    from calidad.utils import anotar_tolerancias
    from calidad.models import NoConformidad
    for d in detalles:
        # Evita una consulta extra por cada corte al pedir d.orden.mp: ya
        # tenemos la orden cargada (con su MP) desde arriba.
        d.orden = orden
    detalles = anotar_tolerancias(detalles)

    no_conformidades = NoConformidad.objects.filter(orden=orden).select_related('detectado_por')

    from dashboard.models import HistorialCambio
    historial = HistorialCambio.objects.filter(
        tipo_objeto='OrdenProduccion', objeto_id=orden_id
    ).select_related('usuario')

    return render(request, 'produccion/detalle_orden.html', {
        'orden': orden,
        'detalles': detalles,
        'detalles_fleje': detalles_fleje,
        'historial': historial,
        'no_conformidades': no_conformidades,
    })