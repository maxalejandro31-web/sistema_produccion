from django.db import migrations


def limpiar_datos_operacionales(apps, schema_editor):
    pass  # cancelado — ya hay datos reales en producción


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0007_limpiar_datos_operacionales_v2'),
        ('materia_terminada', '0001_initial'),
        ('produccion', '0007_alter_detalleslitter_options_and_more'),
        ('inventario', '0014_materiaprima_material_texto_libre'),
    ]

    operations = [
        migrations.RunPython(limpiar_datos_operacionales, migrations.RunPython.noop),
    ]
