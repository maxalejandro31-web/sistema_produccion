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
        # OJO: 'format' fijo en cada widget (no basta con input_formats).
        # Sin format='%Y-%m-%d'/'%H:%M', Django renderiza el valor inicial
        # con el formato local (es-mx), que un <input type="date"/"time">
        # del navegador no reconoce y muestra el campo vacio. Al editar y
        # guardar sin tocar ese campo, el navegador manda "" y la fecha/hora
        # ya capturada se borra sola.
        widgets = {
            'fecha_orden_corte': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'fecha_produccion_oc': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'hora_inicio': forms.TimeInput(format='%H:%M', attrs={'type': 'time'}),
            'hora_fin': forms.TimeInput(format='%H:%M', attrs={'type': 'time'}),
            'demora_hora_inicio': forms.TimeInput(format='%H:%M', attrs={'type': 'time'}),
            'demora_hora_fin': forms.TimeInput(format='%H:%M', attrs={'type': 'time'}),
            'observaciones': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from materia_terminada.models import ProductoTerminado
        # No solo "en_almacen": si otra orden de fleje YA tomó esta cinta
        # como origen (aunque esa orden todavía esté pendiente/en proceso,
        # sin terminar), hay que quitarla de la lista para que no se pueda
        # asignar por duplicado a dos órdenes de fleje al mismo tiempo. La
        # cinta se libera si esa orden se borra o se le quita el pt_origen
        # (related_name='ordenes_flejado' en OrdenProduccion.pt_origen).
        qs = ProductoTerminado.objects.filter(
            tipo_producto='cinta', estado='en_almacen'
        ).exclude(ordenes_flejado__isnull=False)
        if self.instance and self.instance.pk and self.instance.pt_origen_id:
            # Al editar una orden que ya trae una cinta asignada, hay que
            # seguir mostrándola en el combo (si no, el campo se vería vacío
            # aunque la orden sí tenga una cinta de origen).
            qs = qs | ProductoTerminado.objects.filter(pk=self.instance.pt_origen_id)
        self.fields['pt_origen'].queryset = qs.order_by('-fecha_ingreso')
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