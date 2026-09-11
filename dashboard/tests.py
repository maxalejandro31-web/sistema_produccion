"""Tests de dashboard: que las acciones administrativas sensibles (crear/
editar usuario, cambiar rol, cambiar contraseña, activar/desactivar,
configuración de empresa) queden registradas en HistorialCambio — antes de
esta corrección no quedaba ningún rastro de quién hizo estos cambios.
"""
from django.contrib.auth.models import User, Group
from django.test import TestCase
from django.urls import reverse

from .models import ConfiguracionEmpresa, HistorialCambio


class HistorialDeAccionesDeUsuarioTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user('admin_hist', password='pass12345', is_superuser=True, is_staff=True)
        self.client.force_login(self.admin)

    def test_crear_usuario_queda_en_historial(self):
        self.client.post(reverse('crear_usuario'), {
            'username': 'nuevo1', 'password': 'clave12345', 'password2': 'clave12345',
        })
        nuevo = User.objects.get(username='nuevo1')
        self.assertTrue(
            HistorialCambio.objects.filter(tipo_objeto='Usuario', objeto_id=nuevo.id, accion='CREAR').exists()
        )

    def test_cambiar_rol_queda_en_historial(self):
        grupo, _ = Group.objects.get_or_create(name='Operador')
        otro = User.objects.create_user('otro1', password='pass12345')
        self.client.post(reverse('editar_usuario', args=[otro.id]), {
            'accion': 'cambiar_rol', 'grupo': str(grupo.id), 'es_admin': '',
        })
        self.assertTrue(
            HistorialCambio.objects.filter(tipo_objeto='Usuario', objeto_id=otro.id, accion='EDITAR').exists()
        )

    def test_cambiar_password_queda_en_historial_sin_guardar_la_password(self):
        otro = User.objects.create_user('otro2', password='pass12345')
        self.client.post(reverse('editar_usuario', args=[otro.id]), {
            'accion': 'cambiar_password', 'nueva_password': 'nuevaclave1', 'confirmar_password': 'nuevaclave1',
        })
        registro = HistorialCambio.objects.filter(tipo_objeto='Usuario', objeto_id=otro.id, accion='EDITAR').first()
        self.assertIsNotNone(registro)
        self.assertNotIn('nuevaclave1', registro.descripcion)

    def test_toggle_activo_queda_en_historial(self):
        otro = User.objects.create_user('otro3', password='pass12345')
        self.client.post(reverse('editar_usuario', args=[otro.id]), {'accion': 'toggle_activo'})
        self.assertTrue(
            HistorialCambio.objects.filter(tipo_objeto='Usuario', objeto_id=otro.id, accion='ESTADO').exists()
        )

    def test_configuracion_empresa_queda_en_historial(self):
        config = ConfiguracionEmpresa.get()
        self.client.post(reverse('configuracion_empresa'), {
            'nombre_empresa': 'Nuevo Nombre S.A.', 'slogan': '', 'logo_url': '',
        })
        self.assertTrue(
            HistorialCambio.objects.filter(tipo_objeto='ConfiguracionEmpresa', objeto_id=config.id, accion='EDITAR').exists()
        )
