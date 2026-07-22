from django import forms
from django.forms import inlineformset_factory
from .models import OrdenProduccion, DetalleSlitter


class OrdenProduccionForm(forms.ModelForm):
    class Meta:
        model = OrdenProduccion
        fields = [
            'folio_orden',
            'tipo_proceso',
            'cliente',
            'mp',
            'pt_origen',
            'linea',
            'operador_nombre',
            'turno',
            'prioridad',
            'hora_inicio',
            'hora_fin',
            'tiempo_preparacion_min',
            'tiempo_proceso_min',
            'tiempo_muerto_min',
            'peso_usado',
            'peso_producido',
            'scrap_total',
            'merma_kg',
            'rendimiento_porcentaje',
            'cantidad_paquetes',
            'cantidad_piezas',
            'observaciones',
            'estado',
        ]
        widgets = {
            'hora_inicio': forms.TimeInput(attrs={'type': 'time'}),
            'hora_fin': forms.TimeInput(attrs={'type': 'time'}),
            'observaciones': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from materia_terminada.models import ProductoTerminado
        self.fields['pt_origen'].queryset = ProductoTerminado.objects.filter(
            tipo_producto='cinta', estado='en_almacen'
        ).order_by('-fecha_ingreso')
        self.fields['pt_origen'].label = 'Cinta origen (Fleje)'
        self.fields['pt_origen'].required = False


class DetalleSlitterForm(forms.ModelForm):
    class Meta:
        model = DetalleSlitter
        fields = [
            'no_corte',
            'ancho',
            'espesor',
            'rebaba',
            'peso',
            'camber',
            'material_ok',
            'observaciones',
        ]


DetalleSlitterFormSet = inlineformset_factory(
    OrdenProduccion,
    DetalleSlitter,
    form=DetalleSlitterForm,
    extra=5,
    can_delete=True
)