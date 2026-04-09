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
            'linea',
            'operador',
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