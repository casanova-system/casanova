from django import forms
from .models import PerfilUsuario  # Certifique-se de importar o seu model aqui!

class UploadPDFForm(forms.Form):
    arquivo_pdf = forms.FileField(
        label="Selecione o Relatório PDF",
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.pdf'})
    )

class PerfilUsuarioForm(forms.ModelForm):
    class Meta:
        model = PerfilUsuario
        fields = ['nivel_acesso', 'setor', 'cpf', 'data_nascimento', 'cep', 'endereco']