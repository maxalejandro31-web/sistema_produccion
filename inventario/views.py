from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from .forms import MateriaPrimaForm
from .models import MateriaPrima


@login_required
def captura_mp(request):
    if not request.user.groups.filter(name__in=['Administrador', 'Operador']).exists():
        return HttpResponse("No tienes permiso para capturar materia prima.")

    mensaje = ''

    if request.method == 'POST':
        form = MateriaPrimaForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            mensaje = 'Materia prima registrada correctamente.'
            form = MateriaPrimaForm()
    else:
        form = MateriaPrimaForm()

    return render(request, 'inventario/captura_mp.html', {
        'form': form,
        'mensaje': mensaje,
    })


@login_required
def lista_mp(request):
    if not request.user.groups.filter(name__in=['Administrador', 'Supervisor', 'Operador']).exists():
        return HttpResponse("No tienes permiso para ver la materia prima.")

    busqueda = request.GET.get('q', '')
    tipo = request.GET.get('tipo', '')
    estado = request.GET.get('estado', '')

    materias_primas = MateriaPrima.objects.all().order_by('-id')

    if busqueda:
        materias_primas = materias_primas.filter(numero_mp__icontains=busqueda)

    if tipo:
        materias_primas = materias_primas.filter(tipo_mp=tipo)

    if estado:
        materias_primas = materias_primas.filter(estado=estado)

    return render(request, 'inventario/lista_mp.html', {
        'materias_primas': materias_primas,
        'busqueda': busqueda,
        'tipo': tipo,
        'estado': estado,
    })


@login_required
def editar_mp(request, mp_id):
    if not request.user.groups.filter(name__in=['Administrador', 'Supervisor']).exists():
        return HttpResponse("No tienes permiso para editar materia prima.")

    mp = get_object_or_404(MateriaPrima, id=mp_id)

    if request.method == 'POST':
        form = MateriaPrimaForm(request.POST, request.FILES, instance=mp)
        if form.is_valid():
            form.save()
            return redirect('lista_mp')
    else:
        form = MateriaPrimaForm(instance=mp)

    return render(request, 'inventario/editar_mp.html', {
        'form': form,
        'mp': mp,
    })


@login_required
def detalle_mp(request, mp_id):
    if not request.user.groups.filter(name__in=['Administrador', 'Supervisor', 'Operador']).exists():
        return HttpResponse("No tienes permiso para ver la materia prima.")

    mp = get_object_or_404(MateriaPrima, id=mp_id)

    return render(request, 'inventario/detalle_mp.html', {
        'mp': mp,
    })