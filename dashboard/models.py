from django.db import models

# Create your models here.

from datetime import date

def dias_en_planta(self):
    return (date.today() - self.fecha_registro).days