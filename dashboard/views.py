import os
import json
import datetime

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User, Group
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.http import HttpResponse
from django.core.management import call_command
from django.conf import settings
from django.db.models import Sum, Count
from django.utils import timezone

from inventario.models import MateriaPrima
from produccion.models import OrdenProduccion
from .models import ConfiguracionEmpresa
from .forms import ConfiguracionEmpresaForm


# ── Carga de datos iniciales ──────────────────────────────────────────────────

@staff_member_required
def cargar_datos_view(request):
    if MateriaPrima.objects.exists():
        return HttpResponse("Los datos ya existen. No se cargó nada.")
    fixture = os.path.join(settings.BASE_DIR, 'fixtures', 'datos_produccion.json')
    try:
        call_command('loaddata', fixture, verbosity=0)
        return HttpResponse("✅ Datos cargados correctamente.")
    except Exception as e:
        return HttpResponse(f"❌ Error: {e}")


# ── Autenticación ─────────────────────────────────────────────────────────────

def login_view(request):
    if request.user.is_authenticated:
        return redirect('inicio')
    error = ''
    if request.method == 'POST':
        user = authenticate(
            request,
            username=request.POST.get('username'),
            password=request.POST.get('password'),
        )
        if user is not None:
            login(request, user)
            return redirect('inicio')
        error = 'Usuario o contraseña incorrectos'
    return render(request, 'dashboard/login.html', {'error': error})


def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def cambiar_password(request):
    error = ''
    if request.method == 'POST':
        actual    = request.POST.get('password_actual', '')
        nueva     = request.POST.get('password_nueva', '')
        confirmar = request.POST.get('password_confirmar', '')

        if not request.user.check_password(actual):
            error = 'La contraseña actual es incorrecta.'
        elif len(nueva) < 6:
            error = 'La nueva contraseña debe tener al menos 6 caracteres.'
        elif nueva != confirmar:
            error = 'Las contraseñas nuevas no coinciden.'
        else:
            request.user.set_password(nueva)
            request.user.save()
            update_session_auth_hash(request, request.user)
            messages.success(request, 'Contraseña actualizada correctamente.')
            return redirect('inicio')

    return render(request, 'dashboard/cambiar_password.html', {'error': error})


# ── Dashboard principal ───────────────────────────────────────────────────────

@login_required
def inicio(request):
    mp_disponible = MateriaPrima.objects.filter(estado='Disponible').count()
    mp_proceso    = MateriaPrima.objects.filter(estado='En Proceso').count()
    mp_terminada  = MateriaPrima.objects.filter(estado='Terminado').count()

    agg_mp = MateriaPrima.objects.aggregate(total_kg=Sum('peso_restante'))
    total_kg_mp = round(float(agg_mp['total_kg'] or 0), 1)

    total_ordenes      = OrdenProduccion.objects.count()
    ordenes_pendientes = OrdenProduccion.objects.filter(estado='pendiente').count()
    ordenes_proceso    = OrdenProduccion.objects.filter(estado='proceso').count()
    ordenes_terminadas = OrdenProduccion.objects.filter(estado='terminado').count()

    agg = OrdenProduccion.objects.aggregate(
        consumido=Sum('peso_usado'),
        producido=Sum('peso_producido'),
        scrap=Sum('scrap_total'),
    )
    peso_consumido = round(float(agg['consumido'] or 0), 2)
    peso_producido = round(float(agg['producido'] or 0), 2)
    scrap_total    = round(float(agg['scrap']    or 0), 2)

    ultimas_ordenes = OrdenProduccion.objects.select_related(
        'cliente', 'mp', 'linea', 'operador'
    ).order_by('-id')[:8]

    mp_critica = MateriaPrima.objects.filter(
        peso_restante__isnull=False
    ).order_by('peso_restante')[:8]

    # ── Alertas ───────────────────────────────────────────────────────────────
    hoy = timezone.localdate()

    mp_cobro_activo = MateriaPrima.objects.filter(
        fecha_entrada__isnull=False,
        fecha_entrada__lt=hoy - datetime.timedelta(days=30),
    ).count()

    mp_por_vencer = MateriaPrima.objects.filter(
        fecha_entrada__isnull=False,
        fecha_entrada__range=(
            hoy - datetime.timedelta(days=30),
            hoy - datetime.timedelta(days=23),
        ),
    ).count()

    ordenes_urgentes = OrdenProduccion.objects.filter(
        estado__in=['pendiente', 'proceso'],
        prioridad='urgente',
    ).count()

    # ── Datos para gráficas ───────────────────────────────────────────────────
    mp_chart = json.dumps({
        'labels': ['Disponible', 'En Proceso', 'Terminado'],
        'data':   [mp_disponible, mp_proceso, mp_terminada],
        'colors': ['#27ae60', '#2980b9', '#7f8c8d'],
    })

    ordenes_estado_chart = json.dumps({
        'labels': ['Pendientes', 'En Proceso', 'Terminadas'],
        'data':   [ordenes_pendientes, ordenes_proceso, ordenes_terminadas],
        'colors': ['#f39c12', '#2980b9', '#27ae60'],
    })

    LABELS_PROCESO = {
        'slitter': 'Slitter',
        'corte_liso': 'Corte Liso',
        'mini_slitter': 'Mini Slitter',
        'fleje': 'Fleje',
    }
    por_proceso = list(
        OrdenProduccion.objects.values('tipo_proceso')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
    ordenes_proceso_chart = json.dumps({
        'labels': [LABELS_PROCESO.get(x['tipo_proceso'], x['tipo_proceso']) for x in por_proceso],
        'data':   [x['total'] for x in por_proceso],
    })

    dias_labels, dias_data = [], []
    for i in range(6, -1, -1):
        dia = hoy - datetime.timedelta(days=i)
        dias_labels.append(dia.strftime('%d/%m'))
        dias_data.append(OrdenProduccion.objects.filter(fecha=dia).count())

    ordenes_semana_chart = json.dumps({'labels': dias_labels, 'data': dias_data})

    return render(request, 'dashboard/inicio.html', {
        'total_kg_mp': total_kg_mp,
        'mp_disponible': mp_disponible,
        'mp_proceso': mp_proceso,
        'mp_terminada': mp_terminada,
        'total_ordenes': total_ordenes,
        'ordenes_pendientes': ordenes_pendientes,
        'ordenes_proceso': ordenes_proceso,
        'ordenes_terminadas': ordenes_terminadas,
        'peso_consumido': peso_consumido,
        'peso_producido': peso_producido,
        'scrap_total': scrap_total,
        'ultimas_ordenes': ultimas_ordenes,
        'mp_critica': mp_critica,
        'mp_cobro_activo': mp_cobro_activo,
        'mp_por_vencer': mp_por_vencer,
        'ordenes_urgentes': ordenes_urgentes,
        'mp_chart': mp_chart,
        'ordenes_estado_chart': ordenes_estado_chart,
        'ordenes_proceso_chart': ordenes_proceso_chart,
        'ordenes_semana_chart': ordenes_semana_chart,
    })


# ── Gestión de usuarios ───────────────────────────────────────────────────────

@login_required
def lista_usuarios(request):
    if not request.user.is_superuser:
        messages.error(request, 'No tienes permiso para gestionar usuarios.')
        return redirect('inicio')
    usuarios = User.objects.all().order_by('username').prefetch_related('groups')
    grupos   = Group.objects.all().order_by('name')
    return render(request, 'dashboard/usuarios.html', {'usuarios': usuarios, 'grupos': grupos})


@login_required
def crear_usuario(request):
    if not request.user.is_superuser:
        messages.error(request, 'No tienes permiso.')
        return redirect('inicio')

    grupos = Group.objects.all().order_by('name')
    error  = ''

    if request.method == 'POST':
        username  = request.POST.get('username', '').strip()
        password  = request.POST.get('password', '')
        password2 = request.POST.get('password2', '')
        grupo_id  = request.POST.get('grupo')
        es_admin  = request.POST.get('es_admin') == '1'

        if not username or not password:
            error = 'Usuario y contraseña son requeridos.'
        elif len(password) < 6:
            error = 'La contraseña debe tener al menos 6 caracteres.'
        elif password != password2:
            error = 'Las contraseñas no coinciden.'
        elif User.objects.filter(username=username).exists():
            error = f'El usuario "{username}" ya existe.'
        else:
            user = User.objects.create_user(username=username, password=password)
            if es_admin:
                user.is_superuser = True
                user.is_staff = True
            elif grupo_id:
                try:
                    user.groups.add(Group.objects.get(id=grupo_id))
                except Group.DoesNotExist:
                    pass
            user.save()
            messages.success(request, f'Usuario "{username}" creado correctamente.')
            return redirect('lista_usuarios')

    return render(request, 'dashboard/crear_usuario.html', {'grupos': grupos, 'error': error})


@login_required
def editar_usuario(request, user_id):
    if not request.user.is_superuser:
        messages.error(request, 'No tienes permiso.')
        return redirect('inicio')

    usuario      = get_object_or_404(User, id=user_id)
    grupos       = Group.objects.all().order_by('name')
    grupo_actual = usuario.groups.first()
    error        = ''

    if request.method == 'POST':
        accion = request.POST.get('accion')

        if accion == 'cambiar_rol':
            grupo_id = request.POST.get('grupo')
            es_admin = request.POST.get('es_admin') == '1'
            usuario.is_superuser = es_admin
            usuario.is_staff = es_admin
            usuario.groups.clear()
            if grupo_id and not es_admin:
                try:
                    usuario.groups.add(Group.objects.get(id=grupo_id))
                except Group.DoesNotExist:
                    pass
            usuario.save()
            messages.success(request, f'Rol de "{usuario.username}" actualizado.')
            return redirect('lista_usuarios')

        elif accion == 'cambiar_password':
            nueva     = request.POST.get('nueva_password', '')
            confirmar = request.POST.get('confirmar_password', '')
            if len(nueva) < 6:
                error = 'La contraseña debe tener al menos 6 caracteres.'
            elif nueva != confirmar:
                error = 'Las contraseñas no coinciden.'
            else:
                usuario.set_password(nueva)
                usuario.save()
                messages.success(request, f'Contraseña de "{usuario.username}" actualizada.')
                return redirect('lista_usuarios')

        elif accion == 'toggle_activo':
            if usuario == request.user:
                messages.error(request, 'No puedes desactivarte a ti mismo.')
            else:
                usuario.is_active = not usuario.is_active
                usuario.save()
                estado = 'activado' if usuario.is_active else 'desactivado'
                messages.success(request, f'Usuario "{usuario.username}" {estado}.')
            return redirect('lista_usuarios')

    return render(request, 'dashboard/editar_usuario.html', {
        'usuario': usuario,
        'grupos': grupos,
        'grupo_actual': grupo_actual,
        'error': error,
    })


@login_required
def configuracion_empresa(request):
    if not request.user.is_superuser:
        messages.error(request, 'Solo el Admin Total puede cambiar la configuración.')
        return redirect('inicio')

    config = ConfiguracionEmpresa.get()

    if request.method == 'POST':
        form = ConfiguracionEmpresaForm(request.POST, request.FILES, instance=config)
        if form.is_valid():
            form.save()
            messages.success(request, 'Configuración actualizada correctamente.')
            return redirect('configuracion_empresa')
    else:
        form = ConfiguracionEmpresaForm(instance=config)

    return render(request, 'dashboard/configuracion_empresa.html', {
        'form': form,
        'config': config,
    })
