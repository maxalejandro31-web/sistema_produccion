from django.db import migrations


def crear_grupo_capturista(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.get_or_create(name='Capturista')


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0003_historialcambio'),
    ]

    operations = [
        migrations.RunPython(crear_grupo_capturista, migrations.RunPython.noop),
    ]
