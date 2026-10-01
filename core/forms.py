from django import forms
from .models import PerfilUsuario, Veiculo, Custo  # Importado Custo e Veiculo

class UploadPDFForm(forms.Form):
    arquivo_pdf = forms.FileField(
        label="Selecione o Relatório PDF",
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.pdf'})
    )

class PerfilUsuarioForm(forms.ModelForm):
    class Meta:
        model = PerfilUsuario
        fields = [
            'nivel_acesso', 'setor', 'setor_producao',
            'cpf', 'data_nascimento', 'cep', 'endereco',
        ]

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
            'comprimento_bau',  # Corrigido para bater com o models.py
            'largura_bau',      # Corrigido para bater com o models.py
            'altura_bau',       # Corrigido para bater com o models.py
            'capacidade_volumetrica', 
            'consumo_combustivel', 
            'especificacao_tecnica', 
            'ativo'
        ]
        widgets = {
            'placa': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'chassi': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'marca_modelo': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'ano_fabricacao': forms.NumberInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'cor': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'tipo_combustivel': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'litros_tanque': forms.NumberInput(attrs={'class': 'form-control bg-dark text-light border-secondary', 'step': '0.01'}),
            'comprimento_bau': forms.NumberInput(attrs={'class': 'form-control bg-dark text-light border-secondary', 'step': '0.01'}),
            'largura_bau': forms.NumberInput(attrs={'class': 'form-control bg-dark text-light border-secondary', 'step': '0.01'}),
            'altura_bau': forms.NumberInput(attrs={'class': 'form-control bg-dark text-light border-secondary', 'step': '0.01'}),
            'capacidade_volumetrica': forms.NumberInput(attrs={'class': 'form-control bg-dark text-light border-secondary', 'step': '0.01'}),
            'consumo_combustivel': forms.NumberInput(attrs={'class': 'form-control bg-dark text-light border-secondary', 'step': '0.01'}),
            'especificacao_tecnica': forms.Textarea(attrs={'class': 'form-control bg-dark text-light border-secondary', 'rows': 3}),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class CustoForm(forms.ModelForm):
    class Meta:
        model = Custo
        fields = ['tipo', 'descricao', 'valor']
        widgets = {
            'tipo': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary', 'placeholder': 'Ex: Combustível, Hospedagem'}),
            'descricao': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary', 'placeholder': 'Detalhes do custo'}),
            'valor': forms.NumberInput(attrs={'class': 'form-control bg-dark text-light border-secondary', 'step': '0.01'}),
        }