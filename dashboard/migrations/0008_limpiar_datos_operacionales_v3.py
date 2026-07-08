from django.db import migrations


def limpiar_datos_operacionales(apps, schema_editor):
    ProductoTerminado = apps.get_model('materia_terminada', 'ProductoTerminado')
    DetalleSlitter    = apps.get_model('produccion', 'DetalleSlitter')
    MovimientoMP      = apps.get_model('inventario', 'MovimientoMP')
    OrdenProduccion   = apps.get_model('produccion', 'OrdenProduccion')
    MateriaPrima      = apps.get_model('inventario', 'MateriaPrima')

    ProductoTerminado.objects.all().delete()
    DetalleSlitter.objects.all().delete()
    MovimientoMP.objects.all().delete()
    OrdenProduccion.objects.all().delete()
    MateriaPrima.objects.all().delete()


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
