from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from core.decorators import roles_required
from .models import ProductoTerminado


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
        ProductoTerminado.objects.select_related('cliente', 'orden', 'orden__linea', 'orden__operador'),
        id=pt_id,
    )
    return render(request, 'materia_terminada/detalle_pt.html', {'producto': producto})


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
