import datetime

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from django.db.models import ProtectedError
from django.utils import timezone

from .models import (
    OrdenProduccion, DetalleSlitter, peso_producido_slitter, error_producido_mayor_a_usado,
    corte_vacio, tira_vacia,
)
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


def _peso_usado_fleje(orden, excluir_orden_id=None, validar=True):
    """Peso de cinta que entra en ESTE lote de fleje.

    Antes se forzaba siempre al peso COMPLETO de la cinta (peso_rollo_padre),
    aunque la cinta se procesara en varios lotes: cada lote quedaba con un
    rendimiento falsamente bajo y la cinta se "agotaba" desde el primer lote.
    Ahora se respeta el peso usado que se capture; si se deja vacío, se toma
    lo que le queda disponible a la cinta (que en un solo lote es la cinta
    completa, igual que antes). Devuelve un mensaje de error si el lote pide
    más de lo que le queda a la cinta, o None."""
    from decimal import Decimal

    pt = orden.pt_origen
    disponible = _disponible_cinta(pt, excluir_orden_id) if pt is not None else None

    if not orden.peso_usado:
        if disponible is not None:
            orden.peso_usado = disponible
        elif orden.peso_rollo_padre:
            orden.peso_usado = orden.peso_rollo_padre

    if (validar and disponible is not None and orden.peso_usado
            and Decimal(str(orden.peso_usado)) > disponible + Decimal('0.01')):
        return (f'A la cinta {pt.numero_pt} solo le quedan {disponible} kg para fleje; '
                f'el peso usado de este lote ({orden.peso_usado} kg) no puede ser mayor.')
    return None


def _quitar_renglon_vacio(detalle):
    """Borra un corte/tira que quedó sin datos. Si tenía una cinta/fleje en
    Producto Terminado que nunca se movió, también se quita (si no, quedaría
    huérfana con el peso viejo); si ya se movió, el PT se conserva."""
    for pt in detalle.producto_terminado.all():
        if pt.sin_movimientos():
            pt.delete()
    detalle.delete()


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
            # Se descartan los renglones que no traen ningún dato (la
            # pantalla les pre-llena el número de corte/tira).
            detalles = [d for d in formset.save(commit=False) if not corte_vacio(d)]
            detalles_fleje = [d for d in formset_fleje.save(commit=False) if not tira_vacia(d)]

            if tipo in OrdenProduccion.TIPOS_CON_CORTES:
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

                # Solo cortes 'normal': scrap/descarte no es producto.
                orden.peso_producido = peso_producido_slitter(detalles)
                detalles_fleje = []
            elif tipo == 'fleje':
                suma_pesos = sum(
                    float(d.peso_descarga) for d in detalles_fleje if d.peso_descarga
                )
                orden.peso_producido = suma_pesos
                error_fleje = _peso_usado_fleje(orden)
                if error_fleje:
                    messages.error(request, error_fleje)
                    return render(request, 'produccion/captura_orden.html', {
                        'form': form,
                        'formset': formset,
                        'formset_fleje': formset_fleje,
                    })
                orden.mp = None
                detalles = []
            else:
                detalles = []
                detalles_fleje = []

            error_pesos = error_producido_mayor_a_usado(orden.peso_usado, orden.peso_producido)
            if error_pesos:
                messages.error(request, error_pesos)
                return render(request, 'produccion/captura_orden.html', {
                    'form': form,
                    'formset': formset,
                    'formset_fleje': formset_fleje,
                })

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
def api_datos_pt_origen(request, pt_id):
    """Datos del rollo padre (folio/espesor/peso) que le dieron origen a una
    Cinta (ProductoTerminado) para autocompletar los campos 'Folio rollo
    padre' / 'Espesor rollo padre' / 'Peso rollo padre' al crear o editar
    una orden de Fleje -- así ya no hay que volver a escribir a mano datos
    que el sistema ya tiene del corte de Slitter que produjo esa cinta.

    Si la cinta viene de un solo corte (caso normal), el folio usa el mismo
    formato 'M010017075-2-1' que ya se usa en el resto del sistema
    (DetalleSlitter.folio_corte). Si no se puede determinar el corte de
    origen (por ejemplo, una cinta armada empalmando varios cortes), se
    regresan campos vacíos y el usuario los captura a mano como hasta
    ahora -- esto es un atajo, no reemplaza la captura manual cuando no
    aplica."""
    from materia_terminada.models import ProductoTerminado

    pt = get_object_or_404(ProductoTerminado, id=pt_id)
    detalle = pt.detalle_slitter

    folio_rollo_padre = detalle.folio_corte if detalle else None
    espesor_rollo_padre = detalle.espesor if detalle else None

    return JsonResponse({
        'folio_rollo_padre': folio_rollo_padre or '',
        # f"{float(x):g}" en vez de str(x): un DecimalField como espesor
        # (max_digits=10, decimal_places=4) imprime siempre sus 4 decimales
        # ('0.0350'); pasando por float se ve como se captura normalmente
        # en el sistema ('0.035').
        'espesor_rollo_padre': f"{float(espesor_rollo_padre):g}" if espesor_rollo_padre else '',
        'peso_rollo_padre': f"{float(pt.peso_kg):g}" if pt.peso_kg else '',
        # Lo que le queda a la cinta para fleje (descontando los lotes que
        # ya la usaron) — es el valor sugerido para "peso usado" del lote.
        'peso_disponible': f"{float(_disponible_cinta(pt, request.GET.get('excluir_orden'))):g}",
    })


def _disponible_cinta(pt, excluir_orden_id=None):
    from decimal import Decimal
    from django.db.models import Sum
    otros = pt.ordenes_flejado.all()
    if excluir_orden_id and str(excluir_orden_id).isdigit():
        otros = otros.exclude(pk=int(excluir_orden_id))
    consumido = otros.aggregate(t=Sum('peso_usado'))['t'] or Decimal('0')
    return max(Decimal(str(pt.peso_kg or 0)) - consumido, Decimal('0'))


@roles_required('Administrador', 'Supervisor', 'Operador', 'Capturista', 'Coordinador')
def lista_ordenes(request):
    estado       = request.GET.get('estado', '')
    tipo_proceso = request.GET.get('tipo_proceso', '')
    fecha_inicio = request.GET.get('fecha_inicio', '')
    fecha_fin    = request.GET.get('fecha_fin', '')
    q            = request.GET.get('q', '')
    cliente_id   = request.GET.get('cliente', '')
    urgentes     = request.GET.get('urgentes', '')
    anomalia     = request.GET.get('anomalia', '')

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
    if urgentes == '1':
        # A dónde lleva la alerta "órdenes urgentes pendientes" — mismo
        # criterio exacto usado para contar esa alerta (dashboard/alertas.py),
        # así que lo que ves aquí siempre coincide con el número que la
        # generó.
        qs = qs.filter(estado__in=['pendiente', 'proceso'], prioridad='urgente')
    if anomalia == 'bajo':
        # A dónde lleva la alerta "órdenes con rendimiento anómalo". La
        # anomalía es un cálculo en Python (compara contra el promedio
        # histórico, ver produccion/analitica.py), no algo que se pueda
        # filtrar directo en la base de datos — así que primero se
        # recalcula sobre el mismo universo exacto que usó la alerta
        # (terminadas, últimos 30 días) y luego se filtra el queryset por
        # esos IDs, para no perder la paginación/orden normal de la lista.
        hoy = timezone.localdate()
        candidatas = OrdenProduccion.objects.select_related('mp').filter(
            estado='terminado', fecha__gte=hoy - datetime.timedelta(days=30),
        )
        ids_bajo = [
            o.id for o in anotar_anomalias(candidatas)
            if o.anomalia_rendimiento and o.anomalia_rendimiento['bucket'] == 'bajo'
        ]
        qs = qs.filter(pk__in=ids_bajo)

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

    if orden.estado == 'terminado' and nuevo_estado != 'terminado':
        # Reabrir ("Regresar"/"Reabrir") una orden que ya estaba terminada:
        # el producto terminado que se auto-generó al finalizarla por
        # primera vez (y, si es Fleje, el estado 'embarcado' que le puso a
        # la cinta origen) hay que revertirlos también. Antes esto no se
        # tocaba: el PT viejo se quedaba huérfano/obsoleto (con los pesos
        # de ANTES de la corrección) y la cinta origen se quedaba
        # 'embarcado' para siempre, sin poder volver a elegirse como
        # origen de un nuevo lote aunque la orden se reabriera para
        # corregirla y volver a finalizarla.
        from django.db import transaction
        from materia_terminada.models import ProductoTerminado

        productos = list(orden.productos_terminados.all())
        # Si alguno de esos PT ya se movió de verdad (se vendió/embarcó,
        # entró a una remisión de salida, o -si es una cinta- ya se usó
        # como origen de otra orden de fleje), no es seguro borrarlo solo
        # porque se reabrió la orden que lo generó: se bloquea el reabrir
        # y se le pide al usuario resolver eso primero.
        comprometidos = [
            p for p in productos
            if p.estado != 'en_almacen' or p.salida_detalle.exists() or p.ordenes_flejado.exists()
        ]
        if comprometidos:
            nombres = ', '.join(p.numero_pt for p in comprometidos)
            messages.error(
                request,
                f'No se puede reabrir la orden {orden.folio_orden or orden.id}: ya se movió el '
                f'producto terminado que generó ({nombres} — vendido, embarcado, incluido en una '
                'salida, o usado como origen de otra orden). Resuelve eso primero si de verdad '
                'necesitas reabrirla.'
            )
            return redirect('lista_ordenes')

        try:
            with transaction.atomic():
                pt_origen = orden.pt_origen
                for p in productos:
                    p.delete()
                if pt_origen:
                    pt_origen.refresh_from_db()
                    if pt_origen.estado == 'embarcado' and pt_origen.peso_disponible_fleje > 0.01:
                        pt_origen.estado = 'en_almacen'
                        pt_origen.save(update_fields=['estado'])
        except ProtectedError:
            messages.error(
                request,
                f'No se puede reabrir la orden {orden.folio_orden or orden.id}: el producto terminado '
                'que generó ya está referenciado en otro lugar del sistema.'
            )
            return redirect('lista_ordenes')

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
            # Antes de construir el form (is_valid() le pone los valores
            # nuevos a la instancia).
            peso_usado_antes = orden.peso_usado
            pt_origen_antes = orden.pt_origen_id
            form = OrdenProduccionForm(request.POST, instance=orden)
            formset = DetalleSlitterFormSet(request.POST, instance=orden, prefix='detalles')
            formset_fleje = DetalleFlejeFormSet(request.POST, instance=orden, prefix='detalles_fleje')

            # La plantilla solo muestra (y por lo tanto solo manda datos
            # reales de) el bloque de detalle que corresponde al
            # tipo_proceso ORIGINAL de la orden -- el otro formset nunca
            # se renderiza para esta orden, así que exigirle is_valid()
            # de todos modos es imposible de cumplir (Django no encuentra
            # datos que validar) y la orden se quedaba sin poder
            # guardarse NUNCA, sin ningún error visible en pantalla. Por
            # eso aquí solo se exige (y más abajo solo se guarda) el
            # formset que de verdad se le mostró al usuario.
            if orden.usa_cortes:
                formsets_validos = formset.is_valid()
            elif orden.tipo_proceso == 'fleje':
                formsets_validos = formset_fleje.is_valid()
            else:
                formsets_validos = True

            if form.is_valid() and formsets_validos:
                from django.db import transaction
                try:
                    with transaction.atomic():
                        orden_actualizada = form.save(commit=False)

                        if orden.usa_cortes:
                            detalles = formset.save(commit=False)

                            duplicados = _cortes_duplicados(
                                orden_actualizada.mp, [d for d in detalles if not corte_vacio(d)],
                                excluir_orden_id=orden.id,
                            )
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
                            # Renglones que quedaron vacíos (los que se
                            # guardaron así antes, o que se borraron a mano
                            # al editar) se quitan para no dejar basura.
                            for d in orden_actualizada.detalles_slitter.all():
                                if corte_vacio(d):
                                    _quitar_renglon_vacio(d)

                        if orden.tipo_proceso == 'fleje':
                            detalles_fleje = formset_fleje.save(commit=False)
                            for d in detalles_fleje:
                                d.orden = orden_actualizada
                                d.save()
                            for obj in formset_fleje.deleted_objects:
                                obj.delete()
                            for d in orden_actualizada.detalles_fleje.all():
                                if tira_vacia(d):
                                    _quitar_renglon_vacio(d)

                        error_pesos = None
                        if orden_actualizada.usa_cortes:
                            # Solo cortes 'normal': scrap/descarte no es producto.
                            orden_actualizada.peso_producido = peso_producido_slitter(
                                orden_actualizada.detalles_slitter.all()
                            )
                        elif orden_actualizada.tipo_proceso == 'fleje':
                            suma_pesos = sum(
                                float(d.peso_descarga) for d in orden_actualizada.detalles_fleje.all() if d.peso_descarga
                            )
                            orden_actualizada.peso_producido = suma_pesos
                            # Solo se valida contra lo disponible de la cinta si de
                            # verdad se cambió el peso usado o la cinta: así una orden
                            # vieja (capturada cuando el peso usado era siempre la
                            # cinta completa) se puede seguir editando en lo demás.
                            cambio_fleje = (
                                orden_actualizada.peso_usado != peso_usado_antes
                                or orden_actualizada.pt_origen_id != pt_origen_antes
                            )
                            error_pesos = _peso_usado_fleje(
                                orden_actualizada, excluir_orden_id=orden.id, validar=cambio_fleje,
                            )
                            orden_actualizada.mp = None

                        error_pesos = error_pesos or error_producido_mayor_a_usado(
                            orden_actualizada.peso_usado, orden_actualizada.peso_producido,
                        )

                        _calcular_scrap_merma(orden_actualizada)
                        if error_pesos:
                            # Los cortes/descargas ya se guardaron arriba dentro de
                            # esta misma transacción: al lanzar el error se deshace
                            # TODO lo de esta edición, no queda guardado a medias.
                            raise ValueError(error_pesos)
                        orden_actualizada.save()
                except ValueError as e:
                    messages.error(request, str(e))
                    return render(request, 'produccion/editar_orden.html', {
                        'form': form,
                        'formset': formset,
                        'formset_fleje': formset_fleje,
                        'orden': orden,
                    })

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
    # Peso de un corte scrap/descarte: el pesado aparte (peso_merma) si se
    # capturó; si no, el peso del propio renglón (que también es scrap, no
    # producto). Antes, si solo se capturaba el peso del renglón, ese scrap
    # no aparecía en ningún lado del resumen.
    def _peso_desperdicio(d):
        return float(d.peso_merma or d.peso or 0)

    peso_scrap_slitter = sum(
        _peso_desperdicio(d) for d in detalles if d.clasificacion == 'scrap'
    )
    peso_descarte_slitter = sum(
        _peso_desperdicio(d) for d in detalles if d.clasificacion == 'descarte'
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
    if orden.usa_cortes:
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