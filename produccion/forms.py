from django import forms
from django.forms import inlineformset_factory
from .models import OrdenProduccion, DetalleSlitter, DetalleFleje


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
            'fecha_orden_corte',
            'fecha_produccion_oc',
            'hora_inicio',
            'hora_fin',
            'tiempo_preparacion_min',
            'tiempo_proceso_min',
            'tiempo_muerto_min',
            'peso_usado',
            'peso_producido',
            'scrap_total',
            'merma_kg',
            'cantidad_paquetes',
            'cantidad_piezas',
            'folio_rollo_padre',
            'espesor_rollo_padre',
            'peso_rollo_padre',
            'tipo_fleje',
            'temp_zona_1',
            'temp_zona_2',
            'temp_zona_3',
            'temp_zona_4',
            'temp_zona_5',
            'demora_hora_inicio',
            'demora_hora_fin',
            'observaciones',
            'estado',
        ]
        widgets = {
            'fecha_orden_corte': forms.DateInput(attrs={'type': 'date'}),
            'fecha_produccion_oc': forms.DateInput(attrs={'type': 'date'}),
            'hora_inicio': forms.TimeInput(attrs={'type': 'time'}),
            'hora_fin': forms.TimeInput(attrs={'type': 'time'}),
            'demora_hora_inicio': forms.TimeInput(attrs={'type': 'time'}),
            'demora_hora_fin': forms.TimeInput(attrs={'type': 'time'}),
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
            'clasificacion',
            'peso_merma',
            'observaciones',
        ]


DetalleSlitterFormSet = inlineformset_factory(
    OrdenProduccion,
    DetalleSlitter,
    form=DetalleSlitterForm,
    extra=5,
    can_delete=True
)


class DetalleFlejeForm(forms.ModelForm):
    class Meta:
        model = DetalleFleje
        fields = [
            'no_fleje',
            'folio_descarga',
            'porcentaje_rebaba',
            'numero_descarga',
            'peso_descarga',
            'ancho',
            'numero_flejes',
            'observaciones',
        ]


DetalleFlejeFormSet = inlineformset_factory(
    OrdenProduccion,
    DetalleFleje,
    form=DetalleFlejeForm,
    extra=15,
    can_delete=True
)