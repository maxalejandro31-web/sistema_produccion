import os
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.contrib.auth.models import User
from django.conf import settings


class Command(BaseCommand):

    def handle(self, *args, **options):
        # Siempre garantizar que admin existe con la contraseña correcta
        u, created = User.objects.get_or_create(username='admin')
        u.set_password('Berenice28')
        u.is_superuser = True
        u.is_staff = True
        u.is_active = True
        u.save()
        self.stdout.write(self.style.SUCCESS(f"Admin {'creado' if created else 'actualizado'} OK"))

        # Cargar datos solo si no hay materia prima
        from inventario.models import MateriaPrima
        if not MateriaPrima.objects.exists():
            fixture = os.path.join(settings.BASE_DIR, 'fixtures', 'datos_produccion.json')
            if os.path.exists(fixture):
                call_command('loaddata', fixture, verbosity=1)
                self.stdout.write(self.style.SUCCESS("Datos de producción cargados OK"))
            else:
                self.stdout.write(self.style.WARNING("Fixture no encontrado"))
        else:
            self.stdout.write("Datos ya existentes, sin cambios.")
