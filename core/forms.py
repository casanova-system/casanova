from django import forms

class UploadPDFForm(forms.Form):
    arquivo_pdf = forms.FileField(
        label="Selecione o Relatório PDF",
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.pdf'})
    )