from django.core.management.base import BaseCommand
from inventario.models import Cliente


# (codigo, nombre) — IDs exactos del Excel
CLIENTES = [
    # JCH MAQUILAS Y SERVICIOS
    ("5",   "GALVAPRIME"),
    ("8",   "ACEROMEX"),
    ("9",   "FORTACERO"),
    ("16",  "PLACA Y FIERRO DE MONTERREY"),
    ("19",  "MALLA CID"),
    ("22",  "CATAFORESIS"),
    ("23",  "LAMINA DESPLEGADA"),
    ("26",  "NUCOR COLD FINISH MONTERREY"),
    ("33",  "ACEROTECA TRADING"),
    ("34",  "LST LEGNAR STEEL"),
    # MAQUILAS Y SERVICIOS JC
    ("1",   "MAQUILAS Y SERVICIOS JC"),
    ("106", "ACEROMEX"),          # mismo cliente, empresa JC
    ("118", "GRUPO COLLADO"),
    ("125", "ACEROS DEL TORO"),
    ("138", "ATV METAL"),
    ("142", "ACEROS Y PRENSAS"),
    ("145", "CATAFORESIS"),       # mismo cliente, empresa JC
    ("181", "LAMINAS DEL NORTE"),
    ("182", "ACEROS VILLAREAL"),
    ("238", "ACEROS CHANDI"),
    ("239", "ROBERTO MONTEMAYOR GUTIERREZ"),
    ("287", "SERVILAMINA SUMMIT MEXICANA"),
    ("288", "INDUSTRIAL PROCARSA"),
    ("293", "MAQUILACERO"),
    ("304", "SISFLEX"),
    ("305", "PERFIPLAF"),
    ("311", "INTERNACIONAL DE CAJAS"),
    ("317", "JOE NEO ESPINOSA GALLEGOS"),
    ("324", "GRANS CONSULTING AND LOGISTICS"),
    ("333", "JUAN RAMON ORTIZ CANTU"),
    ("337", "GSIDEMIND"),
    ("339", "ACEROS VS"),
    ("342", "MULTI ACEROS ESTREY"),
    ("346", "INDUSTRIAL DE ACEROS Y LAMINAS JE"),
    ("351", "METALES LOZANO"),
    ("356", "STEEL PARK"),
    ("358", "NEOSTEEL SOLUTIONS"),
    ("359", "MULTI ACEROS SSK"),
    ("362", "FABRICA DE MANUFACTURAS METALICAS"),
    ("366", "GRUPO JR INDUSTRIAL"),
    ("371", "SOPORTERIA ELECTRICA MEXICANA"),
    ("382", "MIMSA METALES INDUSTRIALES DE MONTERREY"),
    ("384", "STEEL INDUSTRY DS"),
    ("387", "ACEROS METALLI"),
    ("392", "JO STEEL INDUSTRY"),
    ("409", "SERVICIOS COMPLETOS A LA INDUSTRIA"),
    ("414", "GRUPO ACERERO BENITTA ANCIRA"),
    ("424", "JUAN MANUEL ACOSTA AGUILERA"),
    ("425", "JUAN MANUEL CHAPA SALAZAR"),
    ("432", "ENFIMIFAR"),
    ("433", "PERFILES Y MATERIALES ANAHUAC"),
    ("435", "SIDERURGICO Y MATERIALES"),
    ("438", "FC FACIL DE CONSTRUIR"),
    ("439", "ALAN JESUS NINO RUIZ"),
    ("444", "OPCION METAL"),
    ("446", "ESTEBAN MIJAIL MARTINEZ LOPEZ"),
    ("447", "IWP MANUFACTURING"),
    ("451", "PERFILES Y PLANOS DEL RIO"),
    ("456", "TECNICA DE FLUIDOS"),
    ("459", "GRUPO METELMEX"),
    ("466", "STEEL TECH8"),
    ("468", "ODILON REYNA MARTINEZ"),
    ("474", "SERVICIOS ARYC"),
    ("475", "LARSA, PUERTAS Y PRODUCTOS DE ACERO"),
    ("476", "PEDRO GUSTAVO BUSTOS CANTU"),
    ("74",  "CLIENTES PUBLICO GENERAL"),
    ("85",  "ABINSA"),
    ("89",  "GALVACID"),
]


class Command(BaseCommand):
    help = 'Importa clientes desde el Excel con sus codigos ID'

    def handle(self, *args, **options):
        creados = 0
        actualizados = 0
        for codigo, nombre in CLIENTES:
            obj, created = Cliente.objects.get_or_create(nombre=nombre)
            if created:
                obj.codigo_cliente = codigo
                obj.save()
                creados += 1
            elif not obj.codigo_cliente:
                obj.codigo_cliente = codigo
                obj.save()
                actualizados += 1

        self.stdout.write(self.style.SUCCESS(
            f"Clientes: {creados} nuevos, {actualizados} actualizados con codigo."
        ))
