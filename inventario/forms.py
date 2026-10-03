from django import forms
from .models import MateriaPrima, Cliente, MovimientoMP


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['codigo_cliente', 'nombre', 'activo']
        widgets = {
            'codigo_cliente': forms.TextInput(attrs={'placeholder': 'Código del cliente'}),
            'nombre': forms.TextInput(attrs={'placeholder': 'Nombre del cliente'}),
            'activo': forms.CheckboxInput(),
        }


class PesoObligatorioMixin:
    """Peso obligatorio y mayor a 0 al capturar/editar una MP. Una MP sin
    peso no se puede consumir ni dar de salida bien (así se acumularon
    rollos "sin peso" que luego no se podían dar de baja). Única excepción:
    una MP que YA se dio de baja ('Terminado') sin peso — exigirlo ahí
    bloquearía editar cualquier otro dato de ese registro histórico.

    Lo usan tanto el formulario normal (captura/edición) como el del admin
    de Django, para que no quede ninguna puerta para crear MP sin peso."""

    def _configurar_peso_obligatorio(self):
        if 'peso' not in self.fields:
            return
        peso_field = self.fields['peso']
        peso_field.required = self._peso_obligatorio()
        peso_field.label = 'Peso (kg)'
        peso_field.error_messages['required'] = (
            'El peso es obligatorio. Si no se conoce el peso exacto, pésalo o captura el de la etiqueta del rollo.'
        )
        peso_field.widget.attrs['min'] = '0.01'

    def _peso_obligatorio(self):
        inst = self.instance
        if inst is not None and inst.pk and inst.estado == 'Terminado' and not inst.peso:
            return False
        return True

    def clean_peso(self):
        peso = self.cleaned_data.get('peso')
        if peso is not None and peso <= 0:
            raise forms.ValidationError('El peso debe ser mayor a 0 kg.')
        return peso


class MateriaPrimaAdminForm(PesoObligatorioMixin, forms.ModelForm):
    class Meta:
        model = MateriaPrima
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._configurar_peso_obligatorio()


class MateriaPrimaForm(PesoObligatorioMixin, forms.ModelForm):
    # OJO: hay que fijar tambien el "format" del widget (no solo
    # input_formats, que solo controla el parseo del POST). Sin esto,
    # Django renderiza el valor inicial con el formato local (es-mx:
    # "18/08/2026"), que un <input type="date"> del navegador no puede
    # interpretar y muestra el campo vacio. Al guardar sin tocarlo, el
    # navegador manda "" y se borra la fecha silenciosamente.
    fecha_entrada = forms.DateField(
        required=False,
        input_formats=['%Y-%m-%d'],
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'})
    )

    class Meta:
        model = MateriaPrima
        fields = [
            'numero_mp',
            'tipo_mp',
            'cliente',
            'origen_mp',
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
            'fecha_entrada': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
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

        self._configurar_peso_obligatorio()


class MovimientoMPForm(forms.ModelForm):
    class Meta:
        model = MovimientoMP
        fields = [
            'mp',
            'tipo_movimiento',
            'peso',
            'ubicacion_origen',
            'ubicacion_destino',
            'observaciones',
        ]
        widgets = {
            'mp': forms.Select(),
            'tipo_movimiento': forms.Select(),
            'peso': forms.NumberInput(attrs={'step': 'any', 'placeholder': 'Peso del movimiento'}),
            'ubicacion_origen': forms.TextInput(attrs={'placeholder': 'Ubicación origen'}),
            'ubicacion_destino': forms.TextInput(attrs={'placeholder': 'Ubicación destino'}),
            'observaciones': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Observaciones'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['mp'].queryset = MateriaPrima.objects.all().order_by('-id')
        self.fields['mp'].empty_label = 'Selecciona una MP'

        for field_name, field in self.fields.items():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault('class', 'form-control')



    def clean_peso(self):
        # El "min" del <input type=number> es solo una sugerencia del navegador
        # y no protege nada si el request se manda directo (o el navegador lo
        # ignora); sin este chequeo, un peso negativo en un movimiento de
        # CONSUMO/MERMA invierte la resta en MovimientoMP.save() y en vez de
        # descontar, SUMA al peso_restante de la MP.
        peso = self.cleaned_data.get('peso')
        if peso is not None and peso <= 0:
            raise forms.ValidationError('El peso debe ser un número positivo.')
        return peso


class RegistrarMovimientoForm(forms.ModelForm):
    """Form para registrar un movimiento sobre una MP específica (sin campo mp)."""
    class Meta:
        model = MovimientoMP
        fields = ['tipo_movimiento', 'peso', 'ubicacion_origen', 'ubicacion_destino', 'observaciones']
        widgets = {
            'tipo_movimiento': forms.Select(),
            'peso': forms.NumberInput(attrs={'step': 'any', 'placeholder': 'Peso (kg)', 'min': '0.01'}),
            'ubicacion_origen': forms.TextInput(attrs={'placeholder': 'Ubicación origen (opcional)'}),
            'ubicacion_destino': forms.TextInput(attrs={'placeholder': 'Ubicación destino (opcional)'}),
            'observaciones': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Observaciones (opcional)'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault('class', 'form-control')

    def clean_peso(self):
        # Ver comentario en MovimientoMPForm.clean_peso: sin este chequeo un
        # peso negativo aquí invierte el efecto del movimiento sobre el
        # peso_restante de la MP en vez de rechazarse.
        peso = self.cleaned_data.get('peso')
        if peso is not None and peso <= 0:
            raise forms.ValidationError('El peso debe ser un número positivo.')
        return peso
