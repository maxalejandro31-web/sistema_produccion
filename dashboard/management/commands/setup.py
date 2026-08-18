import os
import secrets

from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.contrib.auth.models import User


# (username, variable de entorno que trae la contraseña, nombre completo)
USUARIOS_PROPIETARIOS = [
    ('jchapa', 'PASSWORD_JCHAPA', 'Jesus Chapa'),
    ('prodriguez', 'PASSWORD_PRODRIGUEZ', 'Pedro Rodriguez'),
]


class Command(BaseCommand):
    help = (
        "Crea o actualiza el usuario admin y los usuarios propietarios. "
        "Las contraseñas se toman de variables de entorno (ADMIN_PASSWORD, "
        "PASSWORD_JCHAPA, PASSWORD_PRODRIGUEZ) para no dejarlas escritas en "
        "el código fuente. Si una variable no está definida, se genera una "
        "contraseña aleatoria y se imprime una sola vez en la consola."
    )

    def _resolver_password(self, env_var):
        password = os.getenv(env_var)
        if password:
            return password, False
        return secrets.token_urlsafe(10), True

    def _crear_o_actualizar(self, username, env_var, nombre=None):
        password, generada = self._resolver_password(env_var)
        u, created = User.objects.get_or_create(username=username)
        u.set_password(password)
        u.is_superuser = True
        u.is_staff = True
        u.is_active = True
        if nombre:
            partes = nombre.split()
            u.first_name = partes[0]
            u.last_name = partes[-1] if len(partes) > 1 else ''
        u.save()

        etiqueta = nombre or username
        self.stdout.write(self.style.SUCCESS(f"{etiqueta} {'creado' if created else 'actualizado'} OK"))
        if generada:
            self.stdout.write(self.style.WARNING(
                f"  {env_var} no estaba definida: se generó la contraseña temporal "
                f"'{password}' para '{username}'. Guárdala ahora (no se vuelve a "
                "mostrar) y cámbiala desde 'Mi contraseña' en cuanto inicies sesión."
            ))

    def handle(self, *args, **options):
        # Siempre garantizar que admin existe con la contraseña correcta
        self._crear_o_actualizar('admin', 'ADMIN_PASSWORD')

        # Usuarios propietarios
        for username, env_var, nombre in USUARIOS_PROPIETARIOS:
            self._crear_o_actualizar(username, env_var, nombre)

        # Importar clientes siempre (get_or_create, no duplica)
        call_command('importar_clientes')
