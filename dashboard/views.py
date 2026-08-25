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
from django.core.paginator import Paginator
from django.db.models import Sum
from django.utils import timezone

from inventario.models import MateriaPrima
from produccion.models import OrdenProduccion
from produccion.analitica import anotar_anomalias
from materia_terminada.models import Salida
from .models import ConfiguracionEmpresa, HistorialCambio
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
    agg_mp_propia = MateriaPrima.objects.filter(
        cliente__nombre='MAQUILAS Y SERVICIOS JC'
    ).aggregate(total_kg=Sum('peso_restante'))
    total_kg_mp_propia = round(float(agg_mp_propia['total_kg'] or 0), 1)

    agg_mp_clientes = MateriaPrima.objects.exclude(
        cliente__nombre='MAQUILAS Y SERVICIOS JC'
    ).aggregate(total_kg=Sum('peso_restante'))
    total_kg_mp_clientes = round(float(agg_mp_clientes['total_kg'] or 0), 1)

    mp_disponible_propia  = MateriaPrima.objects.filter(cliente__nombre='MAQUILAS Y SERVICIOS JC', estado='Disponible').count()
    mp_proceso_propia     = MateriaPrima.objects.filter(cliente__nombre='MAQUILAS Y SERVICIOS JC', estado='En Proceso').count()
    mp_disponible_cliente = MateriaPrima.objects.exclude(cliente__nombre='MAQUILAS Y SERVICIOS JC').filter(estado='Disponible').count()
    mp_proceso_cliente    = MateriaPrima.objects.exclude(cliente__nombre='MAQUILAS Y SERVICIOS JC').filter(estado='En Proceso').count()

    total_ordenes      = OrdenProduccion.objects.count()
    ordenes_pendientes = OrdenProduccion.objects.filter(estado='pendiente').count()
    ordenes_proceso    = OrdenProduccion.objects.filter(estado='proceso').count()

    agg = OrdenProduccion.objects.aggregate(
        consumido=Sum('peso_usado'),
        producido=Sum('peso_producido'),
        scrap=Sum('scrap_total'),
    )
    peso_consumido = round(float(agg['consumido'] or 0), 2)
    peso_producido = round(float(agg['producido'] or 0), 2)
    scrap_total    = round(float(agg['scrap']    or 0), 2)

    ultimas_ordenes = OrdenProduccion.objects.select_related(
        'cliente', 'mp', 'linea'
    ).order_by('-id')[:8]

    mp_critica = MateriaPrima.objects.filter(
        peso_restante__isnull=False,
        peso_restante__gt=0,
    ).exclude(estado='Terminado').order_by('peso_restante')[:8]

    # ── Alertas ───────────────────────────────────────────────────────────────
    hoy = timezone.localdate()

    mp_cobro_activo = MateriaPrima.objects.filter(
        fecha_entrada__isnull=False,
        fecha_entrada__lt=hoy - datetime.timedelta(days=30),
    ).exclude(cliente__nombre='MAQUILAS Y SERVICIOS JC').count()

    mp_por_vencer = MateriaPrima.objects.filter(
        fecha_entrada__isnull=False,
        fecha_entrada__range=(
            hoy - datetime.timedelta(days=30),
            hoy - datetime.timedelta(days=23),
        ),
    ).exclude(cliente__nombre='MAQUILAS Y SERVICIOS JC').count()

    ordenes_urgentes = OrdenProduccion.objects.filter(
        estado__in=['pendiente', 'proceso'],
        prioridad='urgente',
    ).count()

    ordenes_recientes_terminadas = OrdenProduccion.objects.select_related('mp').filter(
        estado='terminado',
        fecha__gte=hoy - datetime.timedelta(days=30),
    ).order_by('-fecha')
    ordenes_rendimiento_bajo = sum(
        1 for o in anotar_anomalias(ordenes_recientes_terminadas)
        if o.anomalia_rendimiento and o.anomalia_rendimiento['bucket'] == 'bajo'
    )

    # ── Datos para gráficas ───────────────────────────────────────────────────

    # Resumen del mes en curso: MP que entró, kg procesados (producidos) y
    # kg que salieron a cliente/centro de servicio, todo en el mismo mes —
    # da una lectura rápida del flujo real de la planta mes a mes, en vez
    # de solo el conteo acumulado histórico de órdenes por tipo de proceso.
    MESES_ES = {
        1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril', 5: 'mayo', 6: 'junio',
        7: 'julio', 8: 'agosto', 9: 'septiembre', 10: 'octubre', 11: 'noviembre', 12: 'diciembre',
    }
    nombre_mes_actual = f'{MESES_ES[hoy.month]} {hoy.year}'

    agg_mp_mes = MateriaPrima.objects.filter(
        fecha_entrada__year=hoy.year, fecha_entrada__month=hoy.month,
    ).aggregate(total=Sum('peso'))
    mp_ingresada_mes = round(float(agg_mp_mes['total'] or 0), 1)

    agg_procesado_mes = OrdenProduccion.objects.filter(
        fecha__year=hoy.year, fecha__month=hoy.month,
    ).aggregate(total=Sum('peso_producido'))
    kg_procesados_mes = round(float(agg_procesado_mes['total'] or 0), 1)

    agg_salidas_mes = Salida.objects.filter(
        fecha_salida__year=hoy.year, fecha_salida__month=hoy.month,
    ).aggregate(total=Sum('peso_total'))
    kg_salidas_mes = round(float(agg_salidas_mes['total'] or 0), 1)

    resumen_mes_chart = json.dumps({
        'labels': ['MP Ingresada', 'Procesado', 'Salidas'],
        'data':   [mp_ingresada_mes, kg_procesados_mes, kg_salidas_mes],
        'colors': ['#2980b9', '#8e44ad', '#27ae60'],
    })

    # Rendimiento de la planta por mes (kg producido / kg usado × 100),
    # últimos 6 meses incluyendo el actual — para ver si el aprovechamiento
    # de la materia prima está mejorando o empeorando mes a mes, no solo
    # el dato aislado de hoy.
    MESES_ABR = {
        1: 'ene', 2: 'feb', 3: 'mar', 4: 'abr', 5: 'may', 6: 'jun',
        7: 'jul', 8: 'ago', 9: 'sep', 10: 'oct', 11: 'nov', 12: 'dic',
    }

    def _mes_atras(fecha, n):
        mes = fecha.month - n
        anio = fecha.year
        while mes <= 0:
            mes += 12
            anio -= 1
        return anio, mes

    rendimiento_labels, rendimiento_data = [], []
    for i in range(5, -1, -1):
        anio_i, mes_i = _mes_atras(hoy, i)
        agg_mes = OrdenProduccion.objects.filter(
            fecha__year=anio_i, fecha__month=mes_i,
        ).aggregate(usado=Sum('peso_usado'), producido=Sum('peso_producido'))
        usado_mes = float(agg_mes['usado'] or 0)
        producido_mes = float(agg_mes['producido'] or 0)
        pct_mes = round((producido_mes / usado_mes) * 100, 1) if usado_mes > 0 else None
        rendimiento_labels.append(f'{MESES_ABR[mes_i]} {anio_i}')
        rendimiento_data.append(pct_mes)

    rendimiento_mensual_chart = json.dumps({'labels': rendimiento_labels, 'data': rendimiento_data})
    rendimiento_mes_actual = rendimiento_data[-1]

    dias_labels, dias_data = [], []
    for i in range(6, -1, -1):
        dia = hoy - datetime.timedelta(days=i)
        dias_labels.append(dia.strftime('%d/%m'))
        dias_data.append(OrdenProduccion.objects.filter(fecha=dia).count())

    ordenes_semana_chart = json.dumps({'labels': dias_labels, 'data': dias_data})

    return render(request, 'dashboard/inicio.html', {
        'total_kg_mp_propia': total_kg_mp_propia,
        'total_kg_mp_clientes': total_kg_mp_clientes,
        'mp_disponible_propia': mp_disponible_propia,
        'mp_proceso_propia': mp_proceso_propia,
        'mp_disponible_cliente': mp_disponible_cliente,
        'mp_proceso_cliente': mp_proceso_cliente,
        'total_ordenes': total_ordenes,
        'ordenes_pendientes': ordenes_pendientes,
        'ordenes_proceso': ordenes_proceso,
        'peso_consumido': peso_consumido,
        'peso_producido': peso_producido,
        'scrap_total': scrap_total,
        'ultimas_ordenes': ultimas_ordenes,
        'mp_critica': mp_critica,
        'mp_cobro_activo': mp_cobro_activo,
        'mp_por_vencer': mp_por_vencer,
        'ordenes_urgentes': ordenes_urgentes,
        'ordenes_rendimiento_bajo': ordenes_rendimiento_bajo,
        'resumen_mes_chart': resumen_mes_chart,
        'nombre_mes_actual': nombre_mes_actual,
        'rendimiento_mensual_chart': rendimiento_mensual_chart,
        'rendimiento_mes_actual': rendimiento_mes_actual,
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


# ── Historial / auditoría ──────────────────────────────────────────────────────

@login_required
def historial_general(request):
    if not request.user.is_superuser:
        messages.error(request, 'No tienes permiso para ver el historial.')
        return redirect('inicio')

    tipo_objeto = request.GET.get('tipo_objeto', '')
    accion      = request.GET.get('accion', '')
    usuario_id  = request.GET.get('usuario', '')
    q           = request.GET.get('q', '')

    qs = HistorialCambio.objects.select_related('usuario').order_by('-fecha')

    if tipo_objeto:
        qs = qs.filter(tipo_objeto=tipo_objeto)
    if accion:
        qs = qs.filter(accion=accion)
    if usuario_id:
        qs = qs.filter(usuario_id=usuario_id)
    if q:
        qs = qs.filter(objeto_str__icontains=q) | qs.filter(descripcion__icontains=q)

    paginator = Paginator(qs, 50)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'dashboard/historial.html', {
        'page_obj': page_obj,
        'tipos_objeto': HistorialCambio.objects.order_by().values_list('tipo_objeto', flat=True).distinct(),
        'acciones': HistorialCambio.ACCION_CHOICES,
        'usuarios': User.objects.filter(historialcambio__isnull=False).distinct().order_by('username'),
        'tipo_objeto': tipo_objeto,
        'accion': accion,
        'usuario_id': usuario_id,
        'q': q,
    })
