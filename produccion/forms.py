from django import forms
from .models import OrdenProduccion, DetalleSlitter


class OrdenProduccionForm(forms.ModelForm):
    class Meta:
        model = OrdenProduccion
        fields = [
            'folio_orden',
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
            'cantidad_paquetes',
            'cantidad_piezas',
            'rendimiento_porcentaje',
            'merma_kg',
            'observaciones',
            'estado',
        ]
        widgets = {
            'observaciones': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Observaciones de la orden'}),
            'hora_inicio': forms.TimeInput(attrs={'type': 'time'}),
            'hora_fin': forms.TimeInput(attrs={'type': 'time'}),
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