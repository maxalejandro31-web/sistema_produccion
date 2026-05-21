from django.core.management.base import BaseCommand
from inventario.models import Cliente


CLIENTES = [
    # JCH MAQUILAS Y SERVICIOS
    "GALVAPRIME",
    "ACEROMEX",
    "FORTACERO",
    "PLACA Y FIERRO DE MONTERREY",
    "MALLA CID",
    "CATAFORESIS",
    "LAMINA DESPLEGADA",
    "NUCOR COLD FINISH MONTERREY",
    "ACEROTECA TRADING",
    "LST LEGNAR STEEL",
    # MAQUILAS Y SERVICIOS JC
    "GRUPO COLLADO",
    "ACEROS DEL TORO",
    "ATV METAL",
    "ACEROS Y PRENSAS",
    "LAMINAS DEL NORTE",
    "ACEROS VILLAREAL",
    "ACEROS CHANDI",
    "ROBERTO MONTEMAYOR GUTIERREZ",
    "SERVILAMINA SUMMIT MEXICANA",
    "INDUSTRIAL PROCARSA",
    "MAQUILACERO",
    "SISFLEX",
    "PERFIPLAF",
    "INTERNACIONAL DE CAJAS",
    "JOE NEO ESPINOSA GALLEGOS",
    "GRANS CONSULTING AND LOGISTICS",
    "JUAN RAMON ORTIZ CANTU",
    "GSIDEMIND",
    "ACEROS VS",
    "MULTI ACEROS ESTREY",
    "INDUSTRIAL DE ACEROS Y LAMINAS JE",
    "METALES LOZANO",
    "STEEL PARK",
    "NEOSTEEL SOLUTIONS",
    "MULTI ACEROS SSK",
    "FABRICA DE MANUFACTURAS METALICAS",
    "GRUPO JR INDUSTRIAL",
    "SOPORTERIA ELECTRICA MEXICANA",
    "MIMSA METALES INDUSTRIALES DE MONTERREY",
    "STEEL INDUSTRY DS",
    "ACEROS METALLI",
    "JO STEEL INDUSTRY",
    "SERVICIOS COMPLETOS A LA INDUSTRIA",
    "GRUPO ACERERO BENITTA ANCIRA",
    "JUAN MANUEL ACOSTA AGUILERA",
    "JUAN MANUEL CHAPA SALAZAR",
    "ENFIMIFAR",
    "PERFILES Y MATERIALES ANAHUAC",
    "SIDERURGICO Y MATERIALES",
    "FC FACIL DE CONSTRUIR",
    "ALAN JESUS NINO RUIZ",
    "OPCION METAL",
    "ESTEBAN MIJAIL MARTINEZ LOPEZ",
    "IWP MANUFACTURING",
    "PERFILES Y PLANOS DEL RIO",
    "TECNICA DE FLUIDOS",
    "GRUPO METELMEX",
    "STEEL TECH8",
    "ODILON REYNA MARTINEZ",
    "SERVICIOS ARYC",
    "LARSA PUERTAS Y PRODUCTOS DE ACERO",
    "PEDRO GUSTAVO BUSTOS CANTU",
    "CLIENTES PUBLICO GENERAL",
    "ABINSA",
    "GALVACID",
]


class Command(BaseCommand):
    help = 'Importa la lista de clientes desde el Excel de la empresa'

    def handle(self, *args, **options):
        creados = 0
        existentes = 0
        for nombre in CLIENTES:
            _, created = Cliente.objects.get_or_create(nombre=nombre.strip())
            if created:
                creados += 1
            else:
                existentes += 1

        self.stdout.write(self.style.SUCCESS(
            f"Importacion completada: {creados} clientes nuevos, {existentes} ya existian."
        ))
