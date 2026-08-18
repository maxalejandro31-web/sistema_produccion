from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from core.decorators import roles_required, solo_dueno_puede_eliminar
from dashboard.models import registrar_historial
from inventario.models import MateriaPrima
from materia_terminada.models import ProductoTerminado
from produccion.models import OrdenProduccion

from .forms import (
    CertificadoCalidadForm,
    NoConformidadForm,
    CambiarEstadoNoConformidadForm,
    ToleranciaProcesoForm,
)
from .models import CertificadoCalidad, NoConformidad, ToleranciaProceso

ROLES_CALIDAD = ('Administrador', 'Supervisor', 'Operador', 'Capturista', 'Coordinador')
ROLES_CONFIG = ('Administrador', 'Supervisor', 'Coordinador')


@login_required
def index(request):
    certificados_pendientes = CertificadoCalidad.objects.filter(aprobado=False).count()
    nc_abiertas = NoConformidad.objects.filter(estado='abierta').count()
    nc_criticas_abiertas = NoConformidad.objects.filter(estado='abierta', severidad='critica').count()
    ultimos_certificados = CertificadoCalidad.objects.select_related('mp', 'producto_terminado')[:8]
    ultimas_nc = NoConformidad.objects.select_related('orden', 'mp', 'producto_terminado')[:8]

    return render(request, 'calidad/index.html', {
        'certificados_pendientes': certificados_pendientes,
        'nc_abiertas': nc_abiertas,
        'nc_criticas_abiertas': nc_criticas_abiertas,
        'ultimos_certificados': ultimos_certificados,
        'ultimas_nc': ultimas_nc,
    })


# ── Certificados de calidad ──────────────────────────────────────────────────

@login_required
def lista_certificados(request):
    tipo = request.GET.get('tipo', '')
    aprobado = request.GET.get('aprobado', '')
    q = request.GET.get('q', '')

    qs = CertificadoCalidad.objects.select_related('mp', 'producto_terminado', 'registrado_por')

    if tipo:
        qs = qs.filter(tipo_documento=tipo)
    if aprobado == '1':
        qs = qs.filter(aprobado=True)
    elif aprobado == '0':
        qs = qs.filter(aprobado=False)
    if q:
        qs = qs.filter(numero_certificado__icontains=q)

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'calidad/lista_certificados.html', {
        'certificados': page_obj,
        'page_obj': page_obj,
        'tipo': tipo,
        'aprobado': aprobado,
        'q': q,
    })


@roles_required(*ROLES_CALIDAD)
def crear_certificado(request, tipo, objeto_id):
    if tipo == 'mp':
        objeto = get_object_or_404(MateriaPrima, id=objeto_id)
        url_retorno = 'detalle_mp'
        kwargs_retorno = {'mp_id': objeto.id}
    elif tipo == 'pt':
        objeto = get_object_or_404(ProductoTerminado, id=objeto_id)
        url_retorno = 'detalle_pt'
        kwargs_retorno = {'pt_id': objeto.id}
    else:
        messages.error(request, 'Tipo de documento no válido.')
        return redirect('lista_certificados')

    if request.method == 'POST':
        # El modelo exige (en clean()) que apunte a exactamente una MP o un
        # PT; como esos campos no están en el formulario (los decide la URL,
        # no el usuario), hay que dejarlos ya puestos en la instancia ANTES
        # de validar, si no CertificadoCalidad.clean() los ve a ambos vacíos
        # y el formulario nunca pasa is_valid().
        instancia = CertificadoCalidad(tipo_documento=tipo)
        if tipo == 'mp':
            instancia.mp = objeto
        else:
            instancia.producto_terminado = objeto

        form = CertificadoCalidadForm(request.POST, request.FILES, instance=instancia)
        if form.is_valid():
            certificado = form.save(commit=False)
            certificado.registrado_por = request.user
            certificado.save()
            registrar_historial(
                request, 'CertificadoCalidad', certificado.id, str(certificado), 'CREAR',
                f'Certificado registrado para {objeto}.'
            )
            messages.success(request, 'Certificado de calidad registrado correctamente.')
            return redirect(url_retorno, **kwargs_retorno)
    else:
        form = CertificadoCalidadForm()

    return render(request, 'calidad/certificado_form.html', {
        'form': form,
        'tipo': tipo,
        'objeto': objeto,
    })


@login_required
def detalle_certificado(request, certificado_id):
    certificado = get_object_or_404(
        CertificadoCalidad.objects.select_related('mp', 'producto_terminado', 'registrado_por'),
        id=certificado_id,
    )
    return render(request, 'calidad/certificado_detalle.html', {'certificado': certificado})


@solo_dueno_puede_eliminar
@require_POST
def eliminar_certificado(request, certificado_id):
    certificado = get_object_or_404(CertificadoCalidad, id=certificado_id)
    objeto = certificado.mp or certificado.producto_terminado
    if certificado.mp_id:
        url_retorno, kwargs_retorno = 'detalle_mp', {'mp_id': certificado.mp_id}
    else:
        url_retorno, kwargs_retorno = 'detalle_pt', {'pt_id': certificado.producto_terminado_id}

    registrar_historial(request, 'CertificadoCalidad', certificado.id, str(certificado), 'ELIMINAR',
        f'Certificado de {objeto} eliminado.')
    certificado.delete()
    messages.success(request, 'Certificado eliminado correctamente.')
    return redirect(url_retorno, **kwargs_retorno)


# ── No conformidades ──────────────────────────────────────────────────────────

@login_required
def lista_no_conformidades(request):
    estado = request.GET.get('estado', '')
    severidad = request.GET.get('severidad', '')
    tipo = request.GET.get('tipo', '')

    qs = NoConformidad.objects.select_related('orden', 'mp', 'producto_terminado', 'detectado_por')

    if estado:
        qs = qs.filter(estado=estado)
    if severidad:
        qs = qs.filter(severidad=severidad)
    if tipo:
        qs = qs.filter(tipo=tipo)

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'calidad/lista_no_conformidades.html', {
        'no_conformidades': page_obj,
        'page_obj': page_obj,
        'estado': estado,
        'severidad': severidad,
        'tipo': tipo,
        'estados': NoConformidad.ESTADO_CHOICES,
        'severidades': NoConformidad.SEVERIDAD_CHOICES,
        'tipos': NoConformidad.TIPO_CHOICES,
    })


@roles_required(*ROLES_CALIDAD)
def crear_no_conformidad(request, origen, objeto_id):
    if origen == 'orden':
        objeto = get_object_or_404(OrdenProduccion, id=objeto_id)
        url_retorno, kwargs_retorno = 'detalle_orden', {'orden_id': objeto.id}
        campo_fk = 'orden'
    elif origen == 'mp':
        objeto = get_object_or_404(MateriaPrima, id=objeto_id)
        url_retorno, kwargs_retorno = 'detalle_mp', {'mp_id': objeto.id}
        campo_fk = 'mp'
    elif origen == 'pt':
        objeto = get_object_or_404(ProductoTerminado, id=objeto_id)
        url_retorno, kwargs_retorno = 'detalle_pt', {'pt_id': objeto.id}
        campo_fk = 'producto_terminado'
    else:
        messages.error(request, 'Origen no válido.')
        return redirect('lista_no_conformidades')

    if request.method == 'POST':
        form = NoConformidadForm(request.POST, request.FILES)
        if form.is_valid():
            nc = form.save(commit=False)
            setattr(nc, campo_fk, objeto)
            nc.detectado_por = request.user
            nc.save()
            registrar_historial(
                request, 'NoConformidad', nc.id, str(nc), 'CREAR',
                f'No conformidad reportada sobre {objeto}.'
            )
            messages.success(request, 'No conformidad registrada correctamente.')
            return redirect(url_retorno, **kwargs_retorno)
    else:
        form = NoConformidadForm()

    return render(request, 'calidad/no_conformidad_form.html', {
        'form': form,
        'origen': origen,
        'objeto': objeto,
    })


@login_required
def detalle_no_conformidad(request, nc_id):
    nc = get_object_or_404(
        NoConformidad.objects.select_related('orden', 'mp', 'producto_terminado', 'detectado_por'),
        id=nc_id,
    )

    puede_gestionar = (
        request.user.is_superuser
        or request.user.groups.filter(name__in=ROLES_CONFIG).exists()
    )

    if request.method == 'POST' and puede_gestionar:
        form = CambiarEstadoNoConformidadForm(request.POST, instance=nc)
        if form.is_valid():
            form.save()
            registrar_historial(request, 'NoConformidad', nc.id, str(nc), 'ESTADO',
                f'No conformidad cambiada a {nc.get_estado_display()}.')
            messages.success(request, 'No conformidad actualizada correctamente.')
            return redirect('detalle_no_conformidad', nc_id=nc.id)
    else:
        form = CambiarEstadoNoConformidadForm(instance=nc)

    return render(request, 'calidad/no_conformidad_detalle.html', {
        'nc': nc,
        'form': form,
        'puede_gestionar': puede_gestionar,
    })


# ── Tolerancias de proceso ───────────────────────────────────────────────────

@roles_required(*ROLES_CONFIG)
def lista_tolerancias(request):
    tolerancias = ToleranciaProceso.objects.all()
    return render(request, 'calidad/lista_tolerancias.html', {'tolerancias': tolerancias})


@roles_required(*ROLES_CONFIG)
def crear_tolerancia(request):
    if request.method == 'POST':
        form = ToleranciaProcesoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Tolerancia registrada correctamente.')
            return redirect('lista_tolerancias')
    else:
        form = ToleranciaProcesoForm()
    return render(request, 'calidad/tolerancia_form.html', {'form': form})


@roles_required(*ROLES_CONFIG)
def editar_tolerancia(request, tolerancia_id):
    tolerancia = get_object_or_404(ToleranciaProceso, id=tolerancia_id)
    if request.method == 'POST':
        form = ToleranciaProcesoForm(request.POST, instance=tolerancia)
        if form.is_valid():
            form.save()
            messages.success(request, 'Tolerancia actualizada correctamente.')
            return redirect('lista_tolerancias')
    else:
        form = ToleranciaProcesoForm(instance=tolerancia)
    return render(request, 'calidad/tolerancia_form.html', {'form': form, 'tolerancia': tolerancia})
