from django import forms
from .models import ConfiguracionEmpresa


class ConfiguracionEmpresaForm(forms.ModelForm):
    class Meta:
        model  = ConfiguracionEmpresa
        fields = ['nombre_empresa', 'slogan', 'logo']
        widgets = {
            'nombre_empresa': forms.TextInput(attrs={'style': 'width:100%;padding:10px;border:1px solid #ccc;border-radius:8px;font-size:15px;'}),
            'slogan':         forms.TextInput(attrs={'style': 'width:100%;padding:10px;border:1px solid #ccc;border-radius:8px;font-size:15px;', 'placeholder': 'Opcional'}),
        }
        labels = {
            'nombre_empresa': 'Nombre de la empresa',
            'slogan':         'Slogan / descripción corta',
            'logo':           'Logo (PNG o JPG recomendado)',
        }