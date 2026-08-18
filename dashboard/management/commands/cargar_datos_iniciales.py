import os
import secrets

from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.contrib.auth.models import User
from django.conf import settings


class Command(BaseCommand):

    def handle(self, *args, **options):
        if User.objects.exists():
            self.stdout.write("Usuarios ya existen, omitiendo carga inicial.")
            return

        fixture_path = os.path.join(settings.BASE_DIR, 'fixtures', 'datos_iniciales.json')
        self.stdout.write(f"Cargando datos desde: {fixture_path}")

        if not os.path.exists(fixture_path):
            self.stdout.write(self.style.ERROR(f"Archivo no encontrado: {fixture_path}"))
            return

        try:
            call_command('loaddata', fixture_path, verbosity=1)
            self.stdout.write(self.style.SUCCESS("Datos iniciales cargados correctamente."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {e}"))
            # Si falla el fixture, crear superusuario mínimo. La contraseña
            # se toma de ADMIN_PASSWORD; si no está definida se genera una
            # aleatoria y se imprime una sola vez (nunca queda fija en el código).
            self.stdout.write("Creando superusuario de emergencia...")
            password = os.getenv('ADMIN_PASSWORD')
            generada = not password
            if generada:
                password = secrets.token_urlsafe(10)
            User.objects.create_superuser(
                username='admin',
                email='',
                password=password,
            )
            self.stdout.write(self.style.SUCCESS("Superusuario 'admin' creado."))
            if generada:
                self.stdout.write(self.style.WARNING(
                    f"ADMIN_PASSWORD no estaba definida: se generó la contraseña "
                    f"temporal '{password}'. Guárdala ahora y cámbiala en cuanto "
                    "inicies sesión."
                ))
