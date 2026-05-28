from django import forms
from .models import ConfiguracionEmpresa

_input_style = 'width:100%;padding:10px;border:1px solid #ccc;border-radius:8px;font-size:15px;box-sizing:border-box;'

class ConfiguracionEmpresaForm(forms.ModelForm):
    class Meta:
        model  = ConfiguracionEmpresa
        fields = ['nombre_empresa', 'slogan', 'logo_url']
        widgets = {
            'nombre_empresa': forms.TextInput(attrs={'style': _input_style}),
            'slogan':         forms.TextInput(attrs={'style': _input_style, 'placeholder': 'Opcional'}),
            'logo_url':       forms.URLInput(attrs={'style': _input_style, 'placeholder': 'https://...'}),
        }
        labels = {
            'nombre_empresa': 'Nombre de la empresa',
            'slogan':         'Slogan / descripción corta',
            'logo_url':       'URL del logo',
        }