from django import forms
from .models import MateriaPrima, Cliente


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['codigo_cliente', 'nombre', 'activo']
        widgets = {
            'codigo_cliente': forms.TextInput(attrs={
                'placeholder': 'Código del cliente'
            }),
            'nombre': forms.TextInput(attrs={
                'placeholder': 'Nombre del cliente'
            }),
            'activo': forms.CheckboxInput(),
        }


class MateriaPrimaForm(forms.ModelForm):
    fecha_entrada = forms.DateField(
        required=False,
        input_formats=['%Y-%m-%d'],
        widget=forms.DateInput(attrs={'type': 'date'})
    )

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
            'numero_mp': forms.TextInput(attrs={'placeholder': 'Número de MP'}),
            'tipo_mp': forms.Select(),
            'cliente': forms.Select(),
            'origen_mp': forms.TextInput(attrs={'placeholder': 'Origen de la MP'}),
            'lote': forms.TextInput(attrs={'placeholder': 'Lote'}),
            'codigo': forms.TextInput(attrs={'placeholder': 'Código'}),
            'descripcion': forms.TextInput(attrs={'placeholder': 'Descripción'}),
            'material': forms.TextInput(attrs={'placeholder': 'Material'}),
            'grado': forms.TextInput(attrs={'placeholder': 'Grado'}),
            'acabado': forms.TextInput(attrs={'placeholder': 'Acabado'}),
            'espesor_valor': forms.NumberInput(attrs={'step': 'any', 'placeholder': 'Espesor'}),
            'unidad_espesor': forms.Select(),
            'ancho': forms.NumberInput(attrs={'step': 'any', 'placeholder': 'Ancho'}),
            'largo': forms.NumberInput(attrs={'step': 'any', 'placeholder': 'Largo'}),
            'peso': forms.NumberInput(attrs={'step': 'any', 'placeholder': 'Peso'}),
            'diametro_interior': forms.NumberInput(attrs={'step': 'any', 'placeholder': 'Diámetro interior'}),
            'diametro_exterior': forms.NumberInput(attrs={'step': 'any', 'placeholder': 'Diámetro exterior'}),
            'proveedor': forms.TextInput(attrs={'placeholder': 'Proveedor'}),
            'ubicacion': forms.Select(),
            'estado': forms.Select(),
            'fecha_entrada': forms.DateInput(attrs={'type': 'date'}),
            'archivo_pdf': forms.ClearableFileInput(),
            'observaciones': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Observaciones'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if 'cliente' in self.fields:
            self.fields['cliente'].queryset = Cliente.objects.all().order_by('nombre')
            self.fields['cliente'].empty_label = 'Selecciona un cliente'

        for field_name, field in self.fields.items():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault('class', 'form-control')