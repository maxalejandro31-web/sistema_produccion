from django.db import migrations


def crear_grupo_coordinador(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.get_or_create(name='Coordinador')


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0004_crear_grupo_capturista'),
    ]

    operations = [
        migrations.RunPython(crear_grupo_coordinador, migrations.RunPython.noop),
    ]
