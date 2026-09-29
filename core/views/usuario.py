from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from core.models import PerfilUsuario
from core.views.permissao import requer_rotina

@login_required(login_url='login')
@requer_rotina('lista_usuarios')
def lista_usuarios(request):
    query = request.GET.get('q', '')
    ordenacao = request.GET.get('ordenar', 'recentes')
    
    # Como o acesso agora é exclusivo para administração, tratamos a listagem global por padrão
    usuarios = User.objects.all()
    
    # Aplica o filtro de busca textual se houver termo digitado
    if query:
        usuarios = usuarios.filter(
            Q(username__icontains=query) | 
            Q(email__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)
        )
        
    # Mapeamento das opções de ordenação para a listagem
    opcoes_ordenacao = {
        'recentes': '-date_joined',
        'antigos': 'date_joined',
        'nome_asc': 'username',
        'nome_desc': '-username',
        'id_asc': 'id',
        'id_desc': '-id',
    }
    
    campo_ordenacao = opcoes_ordenacao.get(ordenacao, '-date_joined')
    usuarios = usuarios.order_by(campo_ordenacao)
        
    context = {
        "usuarios": usuarios,
        "query": query,
        "ordenacao_atual": ordenacao,
    }
    return render(request, "core/usuarios/lista_usuarios.html", context)

@login_required(login_url='login')
@requer_rotina('lista_usuarios')
def criar_usuario(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        first_name = request.POST.get('first_name', '') # <--- CAPTURA O NOME
        last_name = request.POST.get('last_name', '')   # <--- CAPTURA O SOBRENOME
        email = request.POST.get('email')
        password = request.POST.get('password')
        cpf = request.POST.get('cpf')
        data_nascimento = request.POST.get('data_nascimento')
        cep = request.POST.get('cep')
        endereco = request.POST.get('endereco')
        nivel_acesso = request.POST.get('nivel_acesso')
        setor = request.POST.get('setor')  # Captura o setor enviado pelo form
        foto = request.FILES.get('foto')   # <--- CAPTURA A FOTO ENVIADA
        
        # Validação de campos obrigatórios (incluindo o setor)
        if not username or not email or not cpf or not data_nascimento or not setor:
            messages.error(request, "Preencha todos os campos obrigatórios (Nome, E-mail, CPF, Data de Nascimento e Setor).")
            return redirect('criar_usuario')
            
        if User.objects.filter(username=username).exists():
            messages.error(request, "Este nome de usuário já está em uso!")
            return redirect('criar_usuario')
            
        user = User.objects.create_user(username=username, email=email, password=password)
        user.first_name = first_name
        user.last_name = last_name
        user.save()
        
        # Cria o perfil estendido com os novos dados, o setor e a foto
        perfil, _ = PerfilUsuario.objects.update_or_create(
            user=user,
            defaults={
                'cpf': cpf,
                'data_nascimento': data_nascimento,
                'cep': cep,
                'endereco': endereco,
                'nivel_acesso': nivel_acesso,
                'setor': setor
            }
        )
        
        # Se uma foto foi enviada, salva no perfil
        if foto:
            perfil.foto = foto
            perfil.save()
        
        messages.success(request, "Usuário cadastrado com sucesso!")
        return redirect('lista_usuarios')
        
    return render(request, "core/usuarios/form_usuario.html", {"acao": "Cadastrar"})

@login_required(login_url='login')
@requer_rotina('lista_usuarios')
def detalhe_usuario(request, pk):
    usuario = get_object_or_404(User, pk=pk)
    return render(request, "core/usuarios/detalhe_usuario.html", {"usuario": usuario})

@login_required(login_url='login')
@requer_rotina('lista_usuarios')
def editar_usuario(request, pk):
    usuario = get_object_or_404(User, pk=pk)
    
    if request.method == 'POST':
        username = request.POST.get('username')
        first_name = request.POST.get('first_name', '') # <--- CAPTURA O NOME
        last_name = request.POST.get('last_name', '')   # <--- CAPTURA O SOBRENOME
        email = request.POST.get('email')
        cpf = request.POST.get('cpf')
        data_nascimento = request.POST.get('data_nascimento')
        setor = request.POST.get('setor')
        foto = request.FILES.get('foto')  # <--- CAPTURA A NOVA FOTO SE HOUVER
        
        # Validação de campos obrigatórios na edição
        if not username or not email or not cpf or not data_nascimento or not setor:
            messages.error(request, "Preencha todos os campos obrigatórios (Nome, E-mail, CPF, Data de Nascimento e Setor).")
            return redirect('editar_usuario', pk=pk)

        usuario.username = username
        usuario.first_name = first_name
        usuario.last_name = last_name
        usuario.email = email
        
        nova_senha = request.POST.get('password')
        if nova_senha:
            usuario.set_password(nova_senha)
        usuario.save()
        
        # Atualiza os dados do perfil, o setor e a foto
        perfil, _ = PerfilUsuario.objects.get_or_create(user=usuario)
        perfil.cpf = cpf
        perfil.data_nascimento = data_nascimento
        perfil.cep = request.POST.get('cep')
        perfil.endereco = request.POST.get('endereco')
        perfil.nivel_acesso = request.POST.get('nivel_acesso')
        perfil.setor = setor
        
        # Atualiza a foto apenas se o usuário enviou uma nova
        if foto:
            perfil.foto = foto
            
        perfil.save()
        
        messages.success(request, "Usuário atualizado com sucesso!")
        return redirect('lista_usuarios')
        
    return render(request, "core/usuarios/form_usuario.html", {"usuario": usuario, "acao": "Editar"})

@login_required(login_url='login')
@requer_rotina('lista_usuarios')
def excluir_usuario(request, pk):
    usuario = get_object_or_404(User, pk=pk)
    if usuario == request.user:
        messages.error(request, "Você não pode excluir seu próprio usuário logado!")
    else:
        usuario.delete()
        messages.success(request, "Usuário excluído com sucesso!")
    return redirect('lista_usuarios')