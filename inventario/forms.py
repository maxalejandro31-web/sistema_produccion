from django import forms
from .models import MateriaPrima


class MateriaPrimaForm(forms.ModelForm):
    class Meta:
        model = MateriaPrima
        fields = [
            'numero_mp',
            'tipo_mp',
            'cliente',
            'origen_mp',
            'lote',
            'codigo',
            'descripcion',
            'material',
            'grado',
            'acabado',
            'espesor_valor',
            'unidad_espesor',
            'ancho',
            'largo',
            'peso',
            'diametro_interior',
            'diametro_exterior',
            'proveedor',
            'ubicacion',
            'estado',
            'archivo_pdf',
            'observaciones',
        ]
        widgets = {
            'descripcion': forms.TextInput(attrs={'placeholder': 'Descripción de la materia prima'}),
            'grado': forms.TextInput(attrs={'placeholder': 'Ej. G50'}),
            'acabado': forms.TextInput(attrs={'placeholder': 'Ej. RCD, Galv, etc.'}),
            'observaciones': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Notas u observaciones'}),
        }