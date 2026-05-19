from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from core.decorators import roles_required
from .models import ProductoTerminado


@login_required
def lista_pt(request):
    estado = request.GET.get('estado', '')
    q = request.GET.get('q', '')

    productos = ProductoTerminado.objects.select_related('cliente', 'orden')

    if estado:
        productos = productos.filter(estado=estado)
    if q:
        productos = productos.filter(numero_pt__icontains=q)

    return render(request, 'materia_terminada/lista_pt.html', {
        'productos': productos,
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


@roles_required('Administrador', 'Supervisor')
def cambiar_estado_pt(request, pt_id, nuevo_estado):
    estados_validos = ['en_almacen', 'vendido', 'embarcado']
    if nuevo_estado not in estados_validos:
        return HttpResponse("Estado no válido.")

    producto = get_object_or_404(ProductoTerminado, id=pt_id)
    producto.estado = nuevo_estado
    producto.save()
    return redirect('lista_pt')
