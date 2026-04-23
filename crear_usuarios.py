from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

User = get_user_model()

# Crear grupos si no existen
for nombre in ['Administrador', 'Supervisor', 'Almacen', 'Operador']:
    Group.objects.get_or_create(name=nombre)

usuarios = [
    ("supervisor1", "supervisor1@empresa.com", "Supervisor123!", "Supervisor"),
    ("almacen1", "almacen1@empresa.com", "Almacen123!", "Almacen"),
    ("operador1", "operador1@empresa.com", "Operador123!", "Operador"),
]

for username, email, password, rol in usuarios:
    user, created = User.objects.get_or_create(
        username=username,
        defaults={
            "email": email,
            "is_active": True,
            "is_staff": True,
        }
    )

    user.email = email
    user.is_active = True
    user.is_staff = True
    user.is_superuser = False
    user.set_password(password)
    user.save()

    user.groups.clear()
    grupo = Group.objects.get(name=rol)
    user.groups.add(grupo)
    user.save()

    print(f"{username} -> {rol} listo")

print("Usuarios creados correctamente")