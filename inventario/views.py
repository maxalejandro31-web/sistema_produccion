import datetime

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.db.models import Sum, Max, ProtectedError
from django.utils import timezone

from .forms import MateriaPrimaForm, ClienteForm, RegistrarMovimientoForm
from .models import MateriaPrima, Cliente, MovimientoMP, q_sin_peso
from produccion.models import OrdenProduccion, DetalleSlitter
from produccion.analitica import mapa_rendimiento_rollos_terminados, UMBRAL_RENDIMIENTO_ROLLO
from dashboard.models import registrar_historial
from core.decorators import solo_dueno_puede_eliminar


@login_required
def captura_mp(request):
    if request.method == 'POST':
        form = MateriaPrimaForm(request.POST, request.FILES)
        if form.is_valid():
            mp_nueva = form.save()
            registrar_historial(request, 'MateriaPrima', mp_nueva.id, str(mp_nueva), 'CREAR', f'MP {mp_nueva.numero_mp} registrada.')
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
    cliente_id    = request.GET.get('cliente', '')
    cobro         = request.GET.get('cobro', '')
    rendimiento_bajo = request.GET.get('rendimiento_bajo', '')
    sin_peso      = request.GET.get('sin_peso', '')

    hoy = timezone.localdate()

    qs = MateriaPrima.objects.select_related('cliente').order_by('-id')

    if busqueda:
        qs = qs.filter(numero_mp__icontains=busqueda)
    if tipo:
        qs = qs.filter(tipo_mp=tipo)
    # Por defecto la lista muestra solo la MP que sigue en planta. Una MP
    # 'Terminado' (se le dio salida completa, se dio de baja o se consumió
    # toda en producción) ya no está físicamente, y antes seguía saliendo en
    # la lista como si estuviera. No se borra (sigue en reportes, historial
    # y búsquedas): se ve eligiendo "Terminado" o "Todos (incluye
    # terminados)" en el filtro de estado, o buscándola por número.
    ocultando_terminados = False
    if estado == 'todos':
        pass
    elif estado:
        qs = qs.filter(estado=estado)
    elif not busqueda and rendimiento_bajo != '1':
        qs = qs.exclude(estado='Terminado')
        ocultando_terminados = True
    if fecha_inicio:
        qs = qs.filter(fecha_entrada__gte=fecha_inicio)
    if fecha_fin:
        qs = qs.filter(fecha_entrada__lte=fecha_fin)
    if cliente_id:
        qs = qs.filter(cliente_id=cliente_id)
    if cobro == 'vencido':
        # El material propio de la maquila nunca genera cobro — sin este
        # exclude, este filtro (al que llega el link "Ver MP" de la alerta
        # de cobro activo) mostraba más filas de las que decía el conteo de
        # la alerta, porque ese conteo sí excluye lo propio.
        # Tampoco cuenta la MP ya 'Terminado': si ya salió de la planta, ya
        # no está generando estancia.
        qs = qs.filter(fecha_entrada__lt=hoy - datetime.timedelta(days=30)).exclude(cliente__nombre='MAQUILAS Y SERVICIOS JC').exclude(estado='Terminado')
    elif cobro == 'por_vencer':
        qs = qs.filter(
            fecha_entrada__range=(hoy - datetime.timedelta(days=30), hoy - datetime.timedelta(days=23))
        ).exclude(cliente__nombre='MAQUILAS Y SERVICIOS JC').exclude(estado='Terminado')
    elif cobro == 'libre':
        qs = qs.filter(fecha_entrada__gte=hoy - datetime.timedelta(days=22))
    if sin_peso == '1':
        # MP activas sin peso (nunca se capturó o quedó en 0): las que se
        # pueden dar de baja sin peso desde "Salida".
        qs = qs.filter(q_sin_peso())

    # Filtro que llega desde la alerta del dashboard: rollos ya terminados
    # cuyo rendimiento TOTAL (suma de kg producidos / suma de kg usados en
    # todas las órdenes que lo consumieron) quedó por debajo del umbral.
    mapa_rendimiento = None
    if rendimiento_bajo == '1':
        mapa_rendimiento = mapa_rendimiento_rollos_terminados()
        ids_bajo = [mp_id for mp_id, pct in mapa_rendimiento.items() if pct < UMBRAL_RENDIMIENTO_ROLLO]
        qs = qs.filter(id__in=ids_bajo)

    mp_vencidas_count   = MateriaPrima.objects.filter(fecha_entrada__lt=hoy - datetime.timedelta(days=30)).exclude(cliente__nombre='MAQUILAS Y SERVICIOS JC').exclude(estado='Terminado').count()
    mp_por_vencer_count = MateriaPrima.objects.filter(
        fecha_entrada__range=(hoy - datetime.timedelta(days=30), hoy - datetime.timedelta(days=23))
    ).exclude(cliente__nombre='MAQUILAS Y SERVICIOS JC').exclude(estado='Terminado').count()
    terminados_count = MateriaPrima.objects.filter(estado='Terminado').count() if ocultando_terminados else 0

    sin_peso_count = MateriaPrima.objects.filter(q_sin_peso()).count()

    paginator = Paginator(qs, 25)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    if mapa_rendimiento is not None:
        for mp in page_obj:
            mp.rendimiento_total = mapa_rendimiento.get(mp.id)

    return render(request, 'inventario/lista_mp.html', {
        'materias_primas': page_obj,
        'page_obj': page_obj,
        'busqueda': busqueda,
        'tipo': tipo,
        'estado': estado,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'cliente_id': cliente_id,
        'cobro': cobro,
        'rendimiento_bajo': rendimiento_bajo,
        'sin_peso': sin_peso,
        'ocultando_terminados': ocultando_terminados,
        'terminados_count': terminados_count,
        'sin_peso_count': sin_peso_count,
        'umbral_rendimiento_rollo': UMBRAL_RENDIMIENTO_ROLLO,
        'mp_vencidas_count': mp_vencidas_count,
        'mp_por_vencer_count': mp_por_vencer_count,
        'clientes': Cliente.objects.filter(activo=True).order_by('nombre'),
    })


@solo_dueno_puede_eliminar
@require_POST
def eliminar_mp(request, mp_id):
    mp = get_object_or_404(MateriaPrima, id=mp_id)
    numero_mp = mp.numero_mp
    mp_id_original = mp.id
    mp_str = str(mp)

    try:
        mp.delete()
    except ProtectedError:
        messages.error(
            request,
            f'No se puede eliminar la MP {numero_mp} porque ya tiene órdenes de '
            'producción asociadas. Primero hay que eliminar o reasignar esas '
            'órdenes antes de borrar la materia prima (esto también borraría '
            'su historial de movimientos).'
        )
        return redirect('detalle_mp', mp_id=mp_id)

    registrar_historial(request, 'MateriaPrima', mp_id_original, mp_str, 'ELIMINAR', f'MP {numero_mp} eliminada.')
    messages.success(request, f'Materia prima {numero_mp} eliminada correctamente.')
    return redirect('lista_mp')


@login_required
def editar_mp(request, mp_id):
    if not (
        request.user.is_superuser or
        request.user.groups.filter(name__in=['Administrador', 'Supervisor', 'Coordinador']).exists()
    ):
        return HttpResponse("No tienes permiso para editar materia prima.")

    mp = get_object_or_404(MateriaPrima, id=mp_id)

    if request.method == 'POST':
        # Se lee ANTES de construir el form (is_valid() ya le pone los
        # valores nuevos a la instancia).
        estaba_sin_peso = mp.sin_peso
        peso_antes = mp.peso
        restante_antes = mp.peso_restante
        form = MateriaPrimaForm(request.POST, request.FILES, instance=mp)
        if form.is_valid():
            mp = form.save(commit=False)
            restante_nuevo, error_peso = _peso_restante_tras_editar(
                mp, estaba_sin_peso, peso_antes, restante_antes,
            )
            if error_peso:
                form.add_error('peso', error_peso)
            else:
                detalle = ''
                if restante_nuevo is not None and restante_nuevo != restante_antes:
                    mp.peso_restante = restante_nuevo
                    if restante_nuevo == 0 and mp.estado != 'Terminado':
                        mp.estado = 'Terminado'
                    elif restante_nuevo > 0 and mp.estado == 'Terminado':
                        mp.estado = 'En Proceso' if mp.movimientos.exists() else 'Disponible'
                    detalle = (f' Peso: {peso_antes if peso_antes is not None else "sin peso"} → {mp.peso} kg;'
                               f' peso restante: {restante_antes if restante_antes is not None else "sin peso"} → {restante_nuevo} kg.')
                mp.save()
                form.save_m2m()
                registrar_historial(request, 'MateriaPrima', mp.id, str(mp), 'EDITAR', f'MP {mp.numero_mp} actualizada.{detalle}')
                if detalle:
                    messages.success(request, f'Materia prima {mp.numero_mp} actualizada. Peso restante ajustado a {mp.peso_restante} kg.')
                else:
                    messages.success(request, f'Materia prima {mp.numero_mp} actualizada correctamente.')
                return redirect('lista_mp')
    else:
        form = MateriaPrimaForm(instance=mp)

    pdf_url = None
    if mp.archivo_pdf:
        try:
            pdf_url = mp.archivo_pdf.url
        except Exception:
            pass

    return render(request, 'inventario/editar_mp.html', {
        'form': form,
        'mp': mp,
        'pdf_url': pdf_url,
    })


def _peso_restante_tras_editar(mp, estaba_sin_peso, peso_antes, restante_antes):
    """Calcula el peso_restante que debe quedar al editar el PESO de una MP.
    Devuelve (restante_nuevo o None si no cambia, mensaje_de_error o None).

    Antes, editar el peso solo cambiaba `peso`, y `peso_restante` (lo que se
    ve en la lista y suman el dashboard y los reportes) se quedaba con el
    valor mal capturado: corregir 213000 → 21300 dejaba 213000 en la lista.

    - Rollo que estaba sin peso: el restante arranca en el peso capturado.
    - Rollo con el restante "imposible" (mayor que su peso más lo que le ha
      entrado — justo lo que dejó el error de arriba): se recalcula con sus
      movimientos: peso + entradas − salidas/consumos. Así basta con abrir
      Editar y Guardar para que se corrija solo.
    - Corrección normal del peso: el restante se mueve exactamente lo mismo
      que el peso (lo ya consumido/salido no cambia). Si el peso nuevo es
      menor a lo que ya se usó del rollo, se rechaza.
    """
    from decimal import Decimal
    peso_nuevo = mp.peso
    if peso_nuevo is None:
        return None, None
    if estaba_sin_peso:
        return peso_nuevo, None

    entradas, salidas = mp.totales_movimientos()
    base_peso = peso_antes if peso_antes is not None else peso_nuevo
    if restante_antes is not None and restante_antes > base_peso + entradas:
        restante = peso_nuevo + entradas - salidas
        return max(restante, Decimal('0')), None

    if peso_antes is None or peso_nuevo == peso_antes:
        return None, None

    base_restante = restante_antes if restante_antes is not None else peso_antes
    restante = base_restante + (peso_nuevo - peso_antes)
    if restante < 0:
        usado = peso_antes - base_restante
        return None, (f'De este rollo ya se usaron/salieron {usado} kg; el peso no puede '
                      f'ser menor a eso (capturaste {peso_nuevo} kg).')
    return restante, None


@login_required
def detalle_mp(request, mp_id):
    if not (
        request.user.is_superuser or
        request.user.groups.filter(name__in=['Administrador', 'Supervisor', 'Operador', 'Almacen', 'Coordinador', 'Capturista']).exists()
    ):
        return HttpResponse("No tienes permiso para ver la materia prima.")

    mp = get_object_or_404(MateriaPrima, id=mp_id)

    ordenes_relacionadas = OrdenProduccion.objects.select_related(
        'cliente', 'linea'
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

    movimientos = MovimientoMP.objects.filter(mp=mp).select_related('usuario').order_by('-fecha')

    from dashboard.models import HistorialCambio
    historial = HistorialCambio.objects.filter(
        tipo_objeto='MateriaPrima', objeto_id=mp_id
    ).select_related('usuario')

    pdf_url = None
    if mp.archivo_pdf:
        try:
            pdf_url = mp.archivo_pdf.url
        except Exception:
            pass

    return render(request, 'inventario/detalle_mp.html', {
        'mp': mp,
        'ordenes_relacionadas': ordenes_relacionadas,
        'total_consumido': total_consumido,
        'total_producido': total_producido,
        'total_scrap': total_scrap,
        'cantidad_ordenes': cantidad_ordenes,
        'movimientos': movimientos,
        'historial': historial,
        'pdf_url': pdf_url,
    })


def _datos_reporte_rollo(mp):
    """Reconstruye todo el árbol de un rollo: cada orden de slitter que lo
    cortó -> sus cortes -> la orden de fleje (si ya existe) que consumió
    cada corte -> sus descargas -- junto con los totales generales del
    rollo. Es el mismo dato para la vista en pantalla y para el Excel, para
    que ambos digan siempre lo mismo."""
    from produccion.models import OrdenProduccion
    from produccion.views import _resumen_aprovechamiento_mp

    ordenes_slitter = OrdenProduccion.objects.filter(
        mp=mp, tipo_proceso__in=OrdenProduccion.TIPOS_CON_CORTES
    ).select_related('cliente', 'linea').prefetch_related('detalles_slitter').order_by('fecha', 'id')

    bloques = []
    total_scrap_slitter = 0.0
    total_descarte_slitter = 0.0
    total_scrap_fleje = 0.0
    total_fleje_producido = 0.0

    for orden in ordenes_slitter:
        detalles = list(orden.detalles_slitter.all())
        ordenes_fleje_hijas = OrdenProduccion.objects.filter(
            tipo_proceso='fleje',
            pt_origen__detalle_slitter__orden=orden,
        ).select_related(
            'pt_origen', 'pt_origen__detalle_slitter'
        ).prefetch_related('detalles_fleje').order_by('fecha', 'id')

        resumen = _resumen_aprovechamiento_mp(orden, detalles, ordenes_fleje_hijas)

        bloques.append({
            'orden': orden,
            'detalles': detalles,
            'ordenes_fleje_hijas': ordenes_fleje_hijas,
            'resumen': resumen,
        })

        total_scrap_slitter += resumen['peso_scrap_slitter']
        total_descarte_slitter += resumen['peso_descarte_slitter']
        total_scrap_fleje += resumen['scrap_fleje']
        total_fleje_producido += resumen['peso_fleje_producido']

    peso_rollo = float(mp.peso) if mp.peso else 0.0
    total_scrap_general = total_scrap_slitter + total_descarte_slitter + total_scrap_fleje
    aprovechamiento_pct = round((total_fleje_producido / peso_rollo) * 100, 2) if peso_rollo else None

    return {
        'bloques': bloques,
        'peso_rollo': peso_rollo,
        'total_scrap_slitter': total_scrap_slitter,
        'total_descarte_slitter': total_descarte_slitter,
        'total_scrap_fleje': total_scrap_fleje,
        'total_fleje_producido': total_fleje_producido,
        'total_scrap_general': total_scrap_general,
        'aprovechamiento_pct': aprovechamiento_pct,
    }


@login_required
def reporte_rollo(request, mp_id):
    """Reporte completo de trazabilidad de un rollo: MP -> cortes de
    slitter -> descargas de fleje de cada corte -> totales. Junta en una
    sola vista todas las órdenes de slitter que se hayan hecho sobre este
    rollo (un rollo se puede cortar en más de una orden, p. ej. un
    remanente que se vuelve a pasar después)."""
    mp = get_object_or_404(MateriaPrima, id=mp_id)
    datos = _datos_reporte_rollo(mp)
    return render(request, 'inventario/reporte_rollo.html', {'mp': mp, **datos})


@login_required
def reporte_rollo_excel(request, mp_id):
    """Mismo reporte que reporte_rollo, pero exportado a un .xlsx con el
    mismo formato que se llevaba a mano en planta (No. de rollo / peso /
    calibre / ancho, tabla de SLITTER, una tabla de FLEJES por cada corte
    ya procesado, y los totales al final)."""
    import openpyxl
    from openpyxl.styles import Font, Alignment, PatternFill
    from django.http import HttpResponse as _HttpResponse

    mp = get_object_or_404(MateriaPrima, id=mp_id)
    datos = _datos_reporte_rollo(mp)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = (mp.numero_mp or f'MP-{mp.id}')[:31]

    negrita = Font(bold=True)
    titulo_fill = PatternFill('solid', fgColor='1F2D3D')
    titulo_font = Font(bold=True, color='FFFFFF')
    centrado = Alignment(horizontal='center')

    fila = 1

    def escribir_titulo(texto, ncols=7):
        nonlocal fila
        ws.cell(row=fila, column=1, value=texto)
        ws.cell(row=fila, column=1).font = titulo_font
        ws.cell(row=fila, column=1).fill = titulo_fill
        for c in range(2, ncols + 1):
            ws.cell(row=fila, column=c).fill = titulo_fill
        fila += 1

    escribir_titulo('No. DE ROLLO')
    ws.cell(row=fila, column=1, value=mp.numero_mp).font = negrita
    fila += 1

    ws.cell(row=fila, column=1, value='PESO DE ROLLO').font = negrita
    ws.cell(row=fila, column=2, value='ESPESOR (MILS)').font = negrita
    ws.cell(row=fila, column=3, value='ANCHO').font = negrita
    fila += 1
    ws.cell(row=fila, column=1, value=float(mp.peso) if mp.peso else None)
    ws.cell(row=fila, column=2, value=float(mp.espesor_mils) if mp.espesor_mils else None)
    ws.cell(row=fila, column=3, value=float(mp.ancho) if mp.ancho else None)
    fila += 2

    for bloque in datos['bloques']:
        orden = bloque['orden']
        escribir_titulo(f"SLITTER — Orden {orden.folio_orden or orden.id} · {orden.fecha or ''}")
        # "Espesor" aquí es DetalleSlitter.espesor, capturado en PULGADAS —
        # unidad distinta al "ESPESOR (MILS)" de la MP que se exporta unas
        # filas arriba en esta misma hoja. Antes ambas columnas decían
        # "Espesor" a secas, lo que invitaba a leer este valor como si
        # también fuera mils (0.035 pulg ≠ 0.035 mils).
        headers = ['No. de corte', 'Ancho', 'Espesor (pulg)', 'Rebaba', 'Peso', 'Clasificación', 'Peso scrap/descarte']
        for i, h in enumerate(headers, start=1):
            c = ws.cell(row=fila, column=i, value=h)
            c.font = negrita
        fila += 1
        for d in bloque['detalles']:
            ws.cell(row=fila, column=1, value=d.folio_corte or d.no_corte)
            ws.cell(row=fila, column=2, value=float(d.ancho) if d.ancho else None)
            ws.cell(row=fila, column=3, value=float(d.espesor) if d.espesor else None)
            ws.cell(row=fila, column=4, value=d.rebaba or '')
            ws.cell(row=fila, column=5, value=float(d.peso) if d.peso else None)
            ws.cell(row=fila, column=6, value=d.get_clasificacion_display())
            ws.cell(row=fila, column=7, value=float(d.peso_merma) if d.peso_merma else None)
            fila += 1
        fila += 1

        for oh in bloque['ordenes_fleje_hijas']:
            origen = oh.pt_origen.detalle_slitter.folio_corte if (oh.pt_origen and oh.pt_origen.detalle_slitter) else str(oh.pt_origen)
            escribir_titulo(f"FLEJES — Orden {oh.folio_orden or oh.id} · origen {origen} · {oh.fecha or ''} · {oh.tipo_fleje or ''}")
            headers = ['No. descarga', 'Tipo de fleje', 'Peso descarga', '# Flejes', 'Peso x fleje', 'Ancho', 'Folio descarga']
            for i, h in enumerate(headers, start=1):
                c = ws.cell(row=fila, column=i, value=h)
                c.font = negrita
            fila += 1
            for d in oh.detalles_fleje.all():
                ws.cell(row=fila, column=1, value=d.numero_descarga or d.no_fleje)
                ws.cell(row=fila, column=2, value=oh.tipo_fleje or '')
                ws.cell(row=fila, column=3, value=float(d.peso_descarga) if d.peso_descarga else None)
                ws.cell(row=fila, column=4, value=d.numero_flejes)
                ws.cell(row=fila, column=5, value=d.peso_por_fleje)
                ws.cell(row=fila, column=6, value=float(d.ancho) if d.ancho else None)
                ws.cell(row=fila, column=7, value=d.folio_descarga or '')
                fila += 1
            ws.cell(row=fila, column=1, value='Peso total').font = negrita
            ws.cell(row=fila, column=3, value=float(oh.peso_producido) if oh.peso_producido else None).font = negrita
            ws.cell(row=fila, column=4, value=f"Scrap: {oh.scrap_total or 0} kg").font = negrita
            fila += 2

    fila += 1
    ws.cell(row=fila, column=1, value='TOTAL DESCARGAS (fleje)').font = negrita
    ws.cell(row=fila, column=2, value='TOTAL SCRAP SLITTER').font = negrita
    ws.cell(row=fila, column=3, value='TOTAL DESCARTE SLITTER').font = negrita
    ws.cell(row=fila, column=4, value='TOTAL SCRAP FLEJE').font = negrita
    ws.cell(row=fila, column=5, value='TOTAL SCRAP (todo)').font = negrita
    ws.cell(row=fila, column=6, value='TOTAL ROLLO').font = negrita
    ws.cell(row=fila, column=7, value='% APROVECHAMIENTO').font = negrita
    fila += 1
    ws.cell(row=fila, column=1, value=round(datos['total_fleje_producido'], 2))
    ws.cell(row=fila, column=2, value=round(datos['total_scrap_slitter'], 2))
    ws.cell(row=fila, column=3, value=round(datos['total_descarte_slitter'], 2))
    ws.cell(row=fila, column=4, value=round(datos['total_scrap_fleje'], 2))
    ws.cell(row=fila, column=5, value=round(datos['total_scrap_general'], 2))
    ws.cell(row=fila, column=6, value=round(datos['peso_rollo'], 2))
    ws.cell(row=fila, column=7, value=datos['aprovechamiento_pct'])

    for col in range(1, 8):
        ws.column_dimensions[chr(64 + col)].width = 18

    response = _HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    nombre_archivo = f"Reporte_{mp.numero_mp or mp.id}.xlsx".replace('/', '-')
    response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
    wb.save(response)
    return response


@login_required
def lista_clientes(request):
    if not (
        request.user.is_superuser or
        request.user.groups.filter(name__in=['Administrador', 'Supervisor', 'Coordinador']).exists()
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
        request.user.groups.filter(name__in=['Administrador', 'Supervisor', 'Coordinador']).exists()
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
        request.user.groups.filter(name__in=['Administrador', 'Supervisor', 'Coordinador']).exists()
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


@login_required
def registrar_movimiento(request, mp_id):
    if not (
        request.user.is_superuser or
        request.user.groups.filter(name__in=['Administrador', 'Supervisor', 'Almacen', 'Coordinador']).exists()
    ):
        messages.error(request, 'No tienes permiso para registrar movimientos.')
        return redirect('detalle_mp', mp_id=mp_id)

    mp = get_object_or_404(MateriaPrima, id=mp_id)

    if request.method == 'POST':
        form = RegistrarMovimientoForm(request.POST)
        if form.is_valid():
            mov = form.save(commit=False)
            mov.mp = mp
            mov.usuario = request.user
            mov.save()
            etiquetas = {
                'ENTRADA': 'Entrada', 'CONSUMO': 'Consumo',
                'AJUSTE_POSITIVO': 'Ajuste positivo', 'AJUSTE_NEGATIVO': 'Ajuste negativo',
                'MERMA': 'Merma', 'TRASPASO': 'Traspaso', 'SALIDA': 'Salida',
            }
            tipo_label = etiquetas.get(mov.tipo_movimiento, mov.tipo_movimiento)
            registrar_historial(request, 'MateriaPrima', mp.id, str(mp), 'MOVIMIENTO',
                f'{tipo_label} de {mov.peso} kg en MP {mp.numero_mp}.')
            messages.success(request, f'Movimiento "{tipo_label}" de {mov.peso} kg registrado correctamente.')
            return redirect('detalle_mp', mp_id=mp.id)
    else:
        form = RegistrarMovimientoForm()

    return render(request, 'inventario/registrar_movimiento.html', {
        'mp': mp,
        'form': form,
    })


@login_required
def dar_salida_mp(request, mp_id):
    if not (
        request.user.is_superuser or
        request.user.groups.filter(name__in=['Administrador', 'Supervisor', 'Almacen', 'Coordinador', 'Capturista']).exists()
    ):
        messages.error(request, 'No tienes permiso para registrar salidas.')
        return redirect('detalle_mp', mp_id=mp_id)

    mp = get_object_or_404(MateriaPrima, id=mp_id)
    clientes = Cliente.objects.filter(activo=True).order_by('nombre')

    # Un rollo ya 'Terminado' sin peso restante ya no tiene nada que sacar:
    # se bloquea para no registrar salidas/bajas duplicadas.
    if mp.estado == 'Terminado' and not (mp.peso_restante and mp.peso_restante > 0):
        messages.info(request, f'La MP {mp.numero_mp} ya está terminada (sin peso restante); no hay nada que dar de salida.')
        return redirect('detalle_mp', mp_id=mp.id)

    def _form(mp_actual):
        return render(request, 'inventario/dar_salida_mp.html', {
            'mp': mp_actual, 'clientes': clientes, 'post': request.POST,
        })

    if request.method == 'POST':
        peso_str      = request.POST.get('peso', '').replace(',', '.').strip()
        cliente_id    = request.POST.get('cliente_id') or None
        fecha_salida  = request.POST.get('fecha_salida')
        observaciones = request.POST.get('observaciones', '').strip()

        # Rollo sin peso registrado: se permite darlo de baja SIN escribir
        # peso (antes era imposible: el peso era obligatorio y no podía
        # superar un restante vacío/0). A cambio el motivo es obligatorio,
        # para que quede claro en el historial por qué salió sin peso.
        if mp.sin_peso:
            if not observaciones:
                messages.error(request, 'Escribe el motivo de la baja: este rollo no tiene peso registrado.')
                return _form(mp)
            peso = None
            if peso_str:
                try:
                    peso = float(peso_str)
                    if peso <= 0:
                        raise ValueError
                except (ValueError, TypeError):
                    messages.error(request, 'Si escribes un peso, debe ser un número mayor a 0. Si no lo conoces, déjalo vacío.')
                    return _form(mp)
        else:
            try:
                peso = float(peso_str)
                if peso <= 0:
                    raise ValueError
            except (ValueError, TypeError):
                messages.error(request, 'El peso debe ser un número positivo.')
                return _form(mp)

        # select_for_update() dentro de una transacción bloquea la fila de
        # la MP hasta que esta vista termine: si dos personas registran una
        # salida sobre el MISMO rollo casi al mismo instante, la segunda
        # espera a que la primera termine y entonces valida contra el peso
        # YA actualizado, en vez de leer el mismo peso_restante "viejo" que
        # leyó la primera y dejar pasar dos salidas que en conjunto superan
        # lo que el rollo realmente tenía. (En SQLite esto no bloquea de
        # verdad —la BD no lo soporta— pero tampoco falla; en Postgres,
        # producción, sí protege. Mismo patrón que MovimientoMP.save().)
        from django.db import transaction
        with transaction.atomic():
            sin_peso_al_abrir = mp.sin_peso
            mp = MateriaPrima.objects.select_for_update().get(pk=mp.pk)

            if mp.sin_peso != sin_peso_al_abrir:
                # Alguien le capturó (o le quitó) el peso mientras se llenaba
                # este formulario: mejor volver a mostrarlo con el dato real.
                messages.error(request, 'El peso de este rollo cambió mientras capturabas. Revisa los datos y vuelve a intentarlo.')
                return _form(mp)

            if not mp.sin_peso and peso > float(mp.peso_restante):
                messages.error(request, f'El peso ingresado ({peso} kg) supera el peso restante ({mp.peso_restante} kg).')
                return _form(mp)

            baja_sin_peso = mp.sin_peso
            if baja_sin_peso:
                # Si se conocía el peso aunque no estaba capturado, se guarda
                # como peso del rollo para que su registro quede completo
                # (entró con X kg y salieron X kg). Si no se conoce, el
                # restante se fija en 0 para que la salida lo deje
                # 'Terminado' sí o sí.
                if peso and not mp.peso:
                    mp.peso = peso
                mp.peso_restante = peso or 0
                mp.save(update_fields=['peso', 'peso_restante'])

            cliente_nombre = ''
            if cliente_id:
                try:
                    cliente_nombre = Cliente.objects.get(pk=cliente_id).nombre
                except Cliente.DoesNotExist:
                    pass

            from django.utils import timezone as tz
            fecha_dt = tz.now()
            if fecha_salida:
                try:
                    import datetime
                    fecha_dt = datetime.datetime.fromisoformat(fecha_salida)
                    if timezone.is_naive(fecha_dt):
                        fecha_dt = timezone.make_aware(fecha_dt)
                except (ValueError, TypeError):
                    # Antes esto se ignoraba en silencio y la salida se guardaba
                    # con la fecha/hora actual sin avisar que la fecha capturada
                    # no se pudo usar.
                    messages.warning(
                        request,
                        f'No se pudo interpretar la fecha "{fecha_salida}"; se usó la fecha/hora actual en su lugar.'
                    )

            if baja_sin_peso and not peso:
                obs_mov = f'Baja sin peso registrado. Motivo: {observaciones}'
            else:
                obs_mov = observaciones

            MovimientoMP.objects.create(
                mp=mp,
                tipo_movimiento='SALIDA',
                peso=peso or 0,
                fecha=fecha_dt,
                ubicacion_origen=mp.ubicacion or '',
                ubicacion_destino=cliente_nombre,
                observaciones=obs_mov,
                usuario=request.user,
            )

        if baja_sin_peso and not peso:
            registrar_historial(request, 'MateriaPrima', mp.id, str(mp), 'MOVIMIENTO',
                f'Baja de MP {mp.numero_mp} SIN peso registrado, hacia {cliente_nombre or "destino no especificado"}. Motivo: {observaciones}')
            messages.success(request, f'MP {mp.numero_mp} dada de baja (sin peso registrado). Quedó como Terminado.')
        else:
            registrar_historial(request, 'MateriaPrima', mp.id, str(mp), 'MOVIMIENTO',
                f'Salida de {peso} kg de MP {mp.numero_mp} hacia {cliente_nombre or "destino no especificado"}.')
            messages.success(request, f'Salida de {peso} kg registrada. Peso restante: {mp.peso_restante} kg.')
        return redirect('detalle_mp', mp_id=mp.id)

    return _form(mp)


@login_required
def lista_salidas_mp(request):
    busqueda     = request.GET.get('q', '')
    cliente_id   = request.GET.get('cliente', '')
    fecha_inicio = request.GET.get('fecha_inicio', '')
    fecha_fin    = request.GET.get('fecha_fin', '')

    qs = MovimientoMP.objects.filter(tipo_movimiento='SALIDA').select_related(
        'mp', 'mp__cliente', 'usuario'
    ).order_by('-fecha')

    if busqueda:
        qs = qs.filter(mp__numero_mp__icontains=busqueda)
    if cliente_id:
        qs = qs.filter(mp__cliente_id=cliente_id)
    if fecha_inicio:
        qs = qs.filter(fecha__date__gte=fecha_inicio)
    if fecha_fin:
        qs = qs.filter(fecha__date__lte=fecha_fin)

    paginator = Paginator(qs, 25)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'inventario/lista_salidas_mp.html', {
        'salidas': page_obj,
        'page_obj': page_obj,
        'busqueda': busqueda,
        'cliente_id': cliente_id,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'clientes': Cliente.objects.filter(activo=True).order_by('nombre'),
    })


@login_required
def api_datos_mp(request, mp_id):
    mp = get_object_or_404(MateriaPrima, id=mp_id)
    # Un mismo rollo puede pasar por la slitter varias veces en órdenes
    # distintas; el número de corte debe seguir la secuencia del rollo
    # completo, no reiniciar en cada orden nueva.
    ultimo_corte = DetalleSlitter.objects.filter(orden__mp=mp).aggregate(Max('no_corte'))['no_corte__max']
    return JsonResponse({
        'cliente_id': mp.cliente_id,
        'cliente_nombre': str(mp.cliente) if mp.cliente else '',
        'material': mp.material or '',
        'espesor_valor': str(mp.espesor_valor) if mp.espesor_valor else '',
        'unidad_espesor': mp.unidad_espesor or '',
        'espesor_mils': str(mp.espesor_mils) if mp.espesor_mils else '',
        'ancho': str(mp.ancho) if mp.ancho else '',
        'peso_restante': str(mp.peso_restante) if mp.peso_restante else '',
        'ubicacion': mp.ubicacion or '',
        'proximo_no_corte': (ultimo_corte or 0) + 1,
    })
