from django.core.management.base import BaseCommand
from django.contrib.auth.models import User


class Command(BaseCommand):

    def handle(self, *args, **options):
        if User.objects.exists():
            self.stdout.write("Base de datos ya tiene usuarios, omitiendo carga inicial.")
            return

        self.stdout.write("Base de datos vacía. Cargando datos iniciales...")
        from django.core.management import call_command
        try:
            call_command('loaddata', 'fixtures/datos_iniciales.json', verbosity=1)
            self.stdout.write(self.style.SUCCESS("Datos iniciales cargados correctamente."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error al cargar datos: {e}"))
