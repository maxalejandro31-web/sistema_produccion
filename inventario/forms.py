from django import forms
from .models import MateriaPrima, Cliente


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['codigo_cliente', 'nombre', 'activo']
        widgets = {
            'codigo_cliente': forms.TextInput(attrs={'class': 'form-control'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


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
            'numero_mp': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo_mp': forms.Select(attrs={'class': 'form-control'}),
            'cliente': forms.Select(attrs={'class': 'form-control'}),
            'origen_mp': forms.TextInput(attrs={'class': 'form-control'}),
            'lote': forms.TextInput(attrs={'class': 'form-control'}),
            'codigo': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.TextInput(attrs={'class': 'form-control'}),
            'material': forms.TextInput(attrs={'class': 'form-control'}),
            'grado': forms.TextInput(attrs={'class': 'form-control'}),
            'acabado': forms.TextInput(attrs={'class': 'form-control'}),
            'espesor_valor': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'unidad_espesor': forms.Select(attrs={'class': 'form-control'}),
            'ancho': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'largo': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'peso': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'diametro_interior': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'diametro_exterior': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'proveedor': forms.TextInput(attrs={'class': 'form-control'}),
            'ubicacion': forms.Select(attrs={'class': 'form-control'}),
            'estado': forms.Select(attrs={'class': 'form-control'}),
            'fecha_entrada': forms.DateInput(
                attrs={'class': 'form-control', 'type': 'date'},
                format='%Y-%m-%d'
            ),
            'archivo_pdf': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['fecha_entrada'].input_formats = ['%Y-%m-%d']

        campos_opcionales = [
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
            'fecha_entrada',
            'archivo_pdf',
            'observaciones',
        ]

        for campo in campos_opcionales:
            if campo in self.fields:
                self.fields[campo].required = False