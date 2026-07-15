from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.contrib.auth.models import User


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

        # Usuarios propietarios
        for username, password, nombre in [
            ('jchapa',     'jc12345', 'Jesus Chapa'),
            ('prodriguez', 'pr12345', 'Pedro Rodriguez'),
        ]:
            u, created = User.objects.get_or_create(username=username)
            u.set_password(password)
            u.is_superuser = True
            u.is_staff = True
            u.is_active = True
            u.first_name = nombre.split()[0]
            u.last_name  = nombre.split()[1]
            u.save()
            self.stdout.write(self.style.SUCCESS(f"{nombre} {'creado' if created else 'actualizado'} OK"))

        # Importar clientes siempre (get_or_create, no duplica)
        call_command('importar_clientes')
