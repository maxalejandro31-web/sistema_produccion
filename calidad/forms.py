from django import forms

from .models import CertificadoCalidad, NoConformidad, ToleranciaProceso


class CertificadoCalidadForm(forms.ModelForm):
    class Meta:
        model = CertificadoCalidad
        fields = [
            'numero_certificado',
            'numero_colada',
            'norma',
            'limite_fluencia_mpa',
            'resistencia_tension_mpa',
            'elongacion_pct',
            'dureza',
            'proveedor_emisor',
            'fecha_emision',
            'archivo_pdf',
            'aprobado',
            'observaciones',
        ]
        widgets = {
            'fecha_emision': forms.DateInput(attrs={'type': 'date'}),
            'observaciones': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if not isinstance(field.widget, (forms.CheckboxInput, forms.ClearableFileInput)):
                field.widget.attrs.setdefault('class', 'form-control')


class NoConformidadForm(forms.ModelForm):
    class Meta:
        model = NoConformidad
        fields = [
            'tipo',
            'severidad',
            'descripcion',
            'accion_correctiva',
            'evidencia_foto',
        ]
        widgets = {
            'descripcion': forms.Textarea(attrs={'rows': 3, 'placeholder': '¿Qué se encontró?'}),
            'accion_correctiva': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Opcional por ahora'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if not isinstance(field.widget, (forms.CheckboxInput, forms.ClearableFileInput)):
                field.widget.attrs.setdefault('class', 'form-control')


class CambiarEstadoNoConformidadForm(forms.ModelForm):
    class Meta:
        model = NoConformidad
        fields = ['estado', 'accion_correctiva']
        widgets = {
            'accion_correctiva': forms.Textarea(attrs={'rows': 3}),
        }


class ToleranciaProcesoForm(forms.ModelForm):
    class Meta:
        model = ToleranciaProceso
        fields = ['tipo_proceso', 'material', 'tolerancia_ancho_mm', 'tolerancia_espesor_mm', 'activa']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault('class', 'form-control')
