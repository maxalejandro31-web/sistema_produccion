from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.utils import timezone
from core.decorators import roles_required
from inventario.models import Cliente
from .models import ProductoTerminado, Salida, SalidaDetalle


@login_required
def lista_pt(request):
    estado = request.GET.get('estado', '')
    q      = request.GET.get('q', '')

    qs = ProductoTerminado.objects.select_related('cliente', 'orden').order_by('-fecha_ingreso')

    if estado:
        qs = qs.filter(estado=estado)
    if q:
        qs = qs.filter(numero_pt__icontains=q)

    total = qs.count()
    paginator = Paginator(qs, 25)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'materia_terminada/lista_pt.html', {
        'productos': page_obj,
        'page_obj': page_obj,
        'total': total,
        'estado_filtro': estado,
        'q': q,
    })


@login_required
def detalle_pt(request, pt_id):
    producto = get_object_or_404(
        ProductoTerminado.objects.select_related(
            'cliente', 'orden', 'orden__linea', 'orden__operador',
            'detalle_slitter', 'orden__pt_origen',
        ),
        id=pt_id,
    )

    rendimiento = None
    if producto.orden and producto.orden.peso_usado:
        peso_entrada = float(producto.orden.peso_usado)
        if producto.tipo_producto == 'fleje' and producto.orden.pt_origen:
            peso_entrada = float(producto.orden.pt_origen.peso_kg or 0)
        if peso_entrada > 0:
            rendimiento = round((float(producto.peso_kg) / peso_entrada) * 100, 1)

    return render(request, 'materia_terminada/detalle_pt.html', {
        'producto': producto,
        'rendimiento': rendimiento,
    })


@roles_required('Administrador', 'Supervisor', 'Coordinador')
def cambiar_estado_pt(request, pt_id, nuevo_estado):
    estados_validos = ['en_almacen', 'vendido', 'embarcado']
    if nuevo_estado not in estados_validos:
        return HttpResponse("Estado no válido.")

    producto = get_object_or_404(ProductoTerminado, id=pt_id)
    producto.estado = nuevo_estado
    producto.save()

    etiquetas = {'en_almacen': 'En Almacén', 'vendido': 'Vendido', 'embarcado': 'Embarcado'}
    messages.success(request, f'Producto {producto.numero_pt} marcado como {etiquetas[nuevo_estado]}.')
    return redirect('lista_pt')


# ── Salidas ───────────────────────────────────────────────────────────────────

@login_required
def lista_salidas(request):
    qs = Salida.objects.select_related('cliente').prefetch_related('detalles').order_by('-fecha_salida')
    paginator = Paginator(qs, 25)
    page_obj  = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'materia_terminada/lista_salidas.html', {
        'salidas': page_obj,
        'page_obj': page_obj,
    })


@roles_required('Administrador', 'Supervisor', 'Coordinador')
def crear_salida(request):
    pt_disponibles = ProductoTerminado.objects.filter(
        estado='en_almacen'
    ).select_related('cliente', 'orden').order_by('-fecha_ingreso')

    clientes = Cliente.objects.filter(activo=True).order_by('nombre')

    if request.method == 'POST':
        tipo          = request.POST.get('tipo')
        cliente_id    = request.POST.get('cliente') or None
        fecha_salida  = request.POST.get('fecha_salida')
        observaciones = request.POST.get('observaciones', '')
        pt_ids        = request.POST.getlist('pt_seleccionados')

        if not tipo:
            messages.error(request, 'Debes seleccionar el tipo de salida.')
        elif not pt_ids:
            messages.error(request, 'Debes seleccionar al menos un PT para la salida.')
        else:
            salida = Salida.objects.create(
                tipo=tipo,
                cliente_id=cliente_id,
                fecha_salida=fecha_salida or timezone.now(),
                observaciones=observaciones,
            )

            peso_total = 0
            for pt_id in pt_ids:
                try:
                    pt = ProductoTerminado.objects.get(pk=pt_id, estado='en_almacen')
                    SalidaDetalle.objects.create(
                        salida=salida,
                        producto_terminado=pt,
                        peso_kg=pt.peso_kg,
                        cantidad_piezas=pt.cantidad_piezas,
                    )
                    pt.estado = 'embarcado'
                    pt.save()
                    peso_total += float(pt.peso_kg)
                except ProductoTerminado.DoesNotExist:
                    pass

            Salida.objects.filter(pk=salida.pk).update(peso_total=peso_total)
            messages.success(request, f'Salida {salida.folio_remision} registrada con {len(pt_ids)} PT ({peso_total:.1f} kg).')
            return redirect('detalle_salida', salida_id=salida.pk)

    return render(request, 'materia_terminada/crear_salida.html', {
        'pt_disponibles': pt_disponibles,
        'clientes': clientes,
    })


@login_required
def detalle_salida(request, salida_id):
    salida = get_object_or_404(
        Salida.objects.select_related('cliente').prefetch_related('detalles__producto_terminado'),
        pk=salida_id,
    )
    return render(request, 'materia_terminada/detalle_salida.html', {'salida': salida})
