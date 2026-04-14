from django import forms
from .models import MateriaPrima, Cliente


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['nombre', 'activo']


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
            'fecha_entrada',
            'archivo_pdf',
            'observaciones',
        ]
        widgets = {
            'fecha_entrada': forms.DateInput(attrs={'type': 'date'}),
            'observaciones': forms.Textarea(attrs={'rows': 3}),
        }