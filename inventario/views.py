from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Sum
from django import forms

from .forms import MateriaPrimaForm, ClienteForm
from .models import MateriaPrima, Cliente
from produccion.models import OrdenProduccion
from core.decorators import roles_required


def preparar_form_mp(form):
    """
    Evita que el widget del archivo intente renderizar un PDF roto
    y tumbe editar_mp.
    """
    if 'archivo_pdf' in form.fields:
        form.fields['archivo_pdf'].required = False
        form.fields['archivo_pdf'].widget = forms.FileInput(attrs={
            'accept': '.pdf'
        })
    return form


def obtener_pdf_url_segura(mp):
    """
    Intenta obtener la URL del PDF sin tirar error 500 si el archivo está mal.
    """
    try:
        if getattr(mp, 'archivo_pdf', None):
            return mp.archivo_pdf.url
    except Exception:
        return None
    return None


@roles_required('Administrador', 'Supervisor', 'Almacen')
def captura_mp(request):
    mensaje = ''

    if request.method == 'POST':
        form = MateriaPrimaForm(request.POST, request.FILES)
        form = preparar_form_mp(form)

        if form.is_valid():
            form.save()
            mensaje = 'Materia prima registrada correctamente'
            form = preparar_form_mp(MateriaPrimaForm())
    else:
        form = preparar_form_mp(MateriaPrimaForm())

    return render(request, 'inventario/captura_mp.html', {
        'form': form,
        'mensaje': mensaje
    })


@roles_required('Administrador', 'Supervisor', 'Almacen')
def lista_mp(request):
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


@roles_required('Administrador', 'Supervisor')
def editar_mp(request, mp_id):
    mp = get_object_or_404(MateriaPrima, id=mp_id)
    pdf_url = obtener_pdf_url_segura(mp)

    if request.method == 'POST':
        form = MateriaPrimaForm(request.POST, request.FILES, instance=mp)
        form = preparar_form_mp(form)

        if form.is_valid():
            mp_actualizada = form.save(commit=False)

            if not request.FILES.get('archivo_pdf'):
                mp_actualizada.archivo_pdf = mp.archivo_pdf

            mp_actualizada.save()
            return redirect('lista_mp')
    else:
        form = preparar_form_mp(MateriaPrimaForm(instance=mp))

    return render(request, 'inventario/editar_mp.html', {
        'form': form,
        'mp': mp,
        'pdf_url': pdf_url,
    })


@roles_required('Administrador', 'Supervisor', 'Almacen')
def detalle_mp(request, mp_id):
    mp = get_object_or_404(MateriaPrima, id=mp_id)
    pdf_url = obtener_pdf_url_segura(mp)

    ordenes_relacionadas = []
    total_consumido = 0
    total_producido = 0
    total_scrap = 0
    cantidad_ordenes = 0

    try:
        qs = OrdenProduccion.objects.select_related(
            'cliente', 'linea', 'operador'
        ).filter(mp=mp).order_by('-id')

        ordenes_relacionadas = qs
        total_consumido = qs.aggregate(total=Sum('peso_usado'))['total'] or 0
        total_producido = qs.aggregate(total=Sum('peso_producido'))['total'] or 0
        total_scrap = qs.aggregate(total=Sum('scrap_total'))['total'] or 0
        cantidad_ordenes = qs.count()
    except Exception:
        ordenes_relacionadas = []
        total_consumido = 0
        total_producido = 0
        total_scrap = 0
        cantidad_ordenes = 0

    return render(request, 'inventario/detalle_mp.html', {
        'mp': mp,
        'pdf_url': pdf_url,
        'ordenes_relacionadas': ordenes_relacionadas,
        'total_consumido': total_consumido,
        'total_producido': total_producido,
        'total_scrap': total_scrap,
        'cantidad_ordenes': cantidad_ordenes,
    })


@roles_required('Administrador', 'Supervisor')
def lista_clientes(request):
    busqueda = request.GET.get('q', '')
    clientes = Cliente.objects.all().order_by('nombre')

    if busqueda:
        clientes = clientes.filter(nombre__icontains=busqueda)

    return render(request, 'inventario/lista_clientes.html', {
        'clientes': clientes,
        'busqueda': busqueda,
    })


@roles_required('Administrador', 'Supervisor')
def captura_cliente(request):
    mensaje = ''

    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            form.save()
            mensaje = 'Cliente registrado correctamente.'
            form = ClienteForm()
    else:
        form = ClienteForm()

    return render(request, 'inventario/captura_cliente.html', {
        'form': form,
        'mensaje': mensaje,
    })


@roles_required('Administrador', 'Supervisor')
def editar_cliente(request, cliente_id):
    cliente = get_object_or_404(Cliente, id=cliente_id)

    if request.method == 'POST':
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            form.save()
            return redirect('lista_clientes')
    else:
        form = ClienteForm(instance=cliente)

    return render(request, 'inventario/editar_cliente.html', {
        'form': form,
        'cliente': cliente,
    })