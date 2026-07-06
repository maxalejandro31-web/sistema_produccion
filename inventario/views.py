import datetime

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Sum
from django.utils import timezone

from .forms import MateriaPrimaForm, ClienteForm, RegistrarMovimientoForm
from .models import MateriaPrima, Cliente, MovimientoMP
from produccion.models import OrdenProduccion
from dashboard.models import registrar_historial


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

    hoy = timezone.localdate()

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
    if cliente_id:
        qs = qs.filter(cliente_id=cliente_id)
    if cobro == 'vencido':
        qs = qs.filter(fecha_entrada__lt=hoy - datetime.timedelta(days=30))
    elif cobro == 'por_vencer':
        qs = qs.filter(
            fecha_entrada__range=(hoy - datetime.timedelta(days=30), hoy - datetime.timedelta(days=23))
        )
    elif cobro == 'libre':
        qs = qs.filter(fecha_entrada__gte=hoy - datetime.timedelta(days=22))

    mp_vencidas_count   = MateriaPrima.objects.filter(fecha_entrada__lt=hoy - datetime.timedelta(days=30)).count()
    mp_por_vencer_count = MateriaPrima.objects.filter(
        fecha_entrada__range=(hoy - datetime.timedelta(days=30), hoy - datetime.timedelta(days=23))
    ).count()

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
        'cliente_id': cliente_id,
        'cobro': cobro,
        'mp_vencidas_count': mp_vencidas_count,
        'mp_por_vencer_count': mp_por_vencer_count,
        'clientes': Cliente.objects.filter(activo=True).order_by('nombre'),
    })


@login_required
def editar_mp(request, mp_id):
    if not (
        request.user.is_superuser or
        request.user.groups.filter(name__in=['Administrador', 'Supervisor', 'Coordinador']).exists()
    ):
        return HttpResponse("No tienes permiso para editar materia prima.")

    mp = get_object_or_404(MateriaPrima, id=mp_id)

    if request.method == 'POST':
        form = MateriaPrimaForm(request.POST, request.FILES, instance=mp)
        if form.is_valid():
            form.save()
            registrar_historial(request, 'MateriaPrima', mp.id, str(mp), 'EDITAR', f'MP {mp.numero_mp} actualizada.')
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


@login_required
def detalle_mp(request, mp_id):
    if not (
        request.user.is_superuser or
        request.user.groups.filter(name__in=['Administrador', 'Supervisor', 'Operador', 'Almacen', 'Coordinador']).exists()
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

    movimientos = MovimientoMP.objects.filter(mp=mp).select_related('usuario').order_by('-fecha')

    from dashboard.models import HistorialCambio
    historial = HistorialCambio.objects.filter(
        tipo_objeto='MateriaPrima', objeto_id=mp_id
    ).select_related('usuario')

    return render(request, 'inventario/detalle_mp.html', {
        'mp': mp,
        'ordenes_relacionadas': ordenes_relacionadas,
        'total_consumido': total_consumido,
        'total_producido': total_producido,
        'total_scrap': total_scrap,
        'cantidad_ordenes': cantidad_ordenes,
        'movimientos': movimientos,
        'historial': historial,
    })


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
def api_datos_mp(request, mp_id):
    mp = get_object_or_404(MateriaPrima, id=mp_id)
    return JsonResponse({
        'cliente_id': mp.cliente_id,
        'cliente_nombre': str(mp.cliente) if mp.cliente else '',
        'material': mp.material or '',
        'espesor_valor': str(mp.espesor_valor) if mp.espesor_valor else '',
        'unidad_espesor': mp.unidad_espesor or '',
        'ancho': str(mp.ancho) if mp.ancho else '',
        'peso_restante': str(mp.peso_restante) if mp.peso_restante else '',
        'ubicacion': mp.ubicacion or '',
    })
