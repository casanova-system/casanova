from django import forms
from .models import PerfilUsuario, Veiculo  # Importado o model Veiculo aqui!

class UploadPDFForm(forms.Form):
    arquivo_pdf = forms.FileField(
        label="Selecione o Relatório PDF",
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.pdf'})
    )

class PerfilUsuarioForm(forms.ModelForm):
    class Meta:
        model = PerfilUsuario
        fields = ['nivel_acesso', 'setor', 'cpf', 'data_nascimento', 'cep', 'endereco']

class VeiculoForm(forms.ModelForm):
    class Meta:
        model = Veiculo
        fields = [
            'placa', 
            'chassi', 
            'marca_modelo', 
            'ano_fabricacao', 
            'cor', 
            'tipo_combustivel', 
            'litros_tanque', 
            'largura', 
            'altura', 
            'profundidade', 
            'capacidade_volumetrica', 
            'consumo_combustivel', 
            'especificacao_tecnica', 
            'ativo'
        ]
        widgets = {
            'placa': forms.TextInput(attrs={'class': 'form-control'}),
            'chassi': forms.TextInput(attrs={'class': 'form-control'}),
            'marca_modelo': forms.TextInput(attrs={'class': 'form-control'}),
            'ano_fabricacao': forms.NumberInput(attrs={'class': 'form-control'}),
            'cor': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo_combustivel': forms.TextInput(attrs={'class': 'form-control'}),
            'litros_tanque': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'largura': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'altura': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'profundidade': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'capacidade_volumetrica': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'consumo_combustivel': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'especificacao_tecnica': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }