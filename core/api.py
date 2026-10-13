"""API REST — App Mobile (Flutter).

Endpoints JSON consumidos pelo aplicativo Flutter. O sistema web continua
funcionando normalmente; esta API é uma camada adicional.

Autenticação: Token (POST /api/login/ devolve o token).
"""
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from core.models import (
    MovimentacaoOP,
    RastreioOP,
    SetorProducao,
    garantir_setores_padrao,
)
from core.views.rastreio import (
    _extrair_op_id_do_qr,
    _pode_gerenciar,
    _registrar_por_setor,
    _setor_do_usuario,
    _setores_ativos,
)


def _serializar_setor(setor):
    return {
        'codigo': setor.codigo,
        'nome': setor.nome,
        'ordem': setor.ordem,
        'requer_vidro': setor.requer_vidro,
    }


def _serializar_rastreio(rastreio):
    if not rastreio:
        return None
    return {
        'op_id': rastreio.op_id,
        'op_numero': rastreio.op_numero,
        'obra': rastreio.obra,
        'produto': rastreio.produto,
        'variante': rastreio.variante,
        'tem_vidro': rastreio.tem_vidro,
        'setor_atual': rastreio.setor_atual,
        'setor_atual_nome': rastreio.setor_atual_nome,
        'status': rastreio.status,
        'concluida': rastreio.concluida,
        'atualizado_em': rastreio.atualizado_em.isoformat(),
    }


def _serializar_movimentacoes(rastreio):
    return [
        {
            'setor': m.setor,
            'setor_nome': m.setor_nome,
            'usuario_entrada': m.usuario_entrada.username if m.usuario_entrada else None,
            'usuario_saida': m.usuario_saida.username if m.usuario_saida else None,
            'observacao_entrada': m.observacao_entrada,
            'observacao_saida': m.observacao_saida,
            'data_entrada': m.data_entrada.isoformat() if m.data_entrada else None,
            'data_saida': m.data_saida.isoformat() if m.data_saida else None,
        }
        for m in rastreio.movimentacoes.select_related('usuario_entrada', 'usuario_saida').all()
    ]


@api_view(['POST'])
@permission_classes([AllowAny])
def api_login(request):
    """Autentica e devolve o token + dados do usuário/setor."""
    username = request.data.get('username', '').strip()
    password = request.data.get('password', '')

    user = authenticate(username=username, password=password)
    if not user:
        return Response(
            {'erro': 'Usuário ou senha inválidos.'},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    token, _ = Token.objects.get_or_create(user=user)
    perfil = getattr(user, 'perfil', None)
    setor = _setor_do_usuario(user)

    return Response({
        'token': token.key,
        'usuario': {
            'id': user.id,
            'username': user.username,
            'nome': user.get_full_name() or user.username,
            'nivel_acesso': perfil.nivel_acesso if perfil else None,
            'setor_producao': _serializar_setor(setor) if setor else None,
            'pode_gerenciar': _pode_gerenciar(user),
        },
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_logout(request):
    """Invalida o token do usuário."""
    Token.objects.filter(user=request.user).delete()
    return Response({'ok': True})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_perfil(request):
    """Dados do usuário logado."""
    perfil = getattr(request.user, 'perfil', None)
    setor = _setor_do_usuario(request.user)
    return Response({
        'id': request.user.id,
        'username': request.user.username,
        'nome': request.user.get_full_name() or request.user.username,
        'nivel_acesso': perfil.nivel_acesso if perfil else None,
        'setor_producao': _serializar_setor(setor) if setor else None,
        'pode_gerenciar': _pode_gerenciar(request.user),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_setores(request):
    """Lista os setores do fluxo de produção."""
    try:
        garantir_setores_padrao()
    except Exception:  # noqa: BLE001
        pass
    return Response([_serializar_setor(s) for s in _setores_ativos()])


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_rastreios(request):
    """Lista as OPs em rastreio (com filtros opcionais).
    
    Gerentes veem apenas OPs do seu próprio setor.
    Superusuários veem todas as OPs.
    """
    try:
        garantir_setores_padrao()
    except Exception:  # noqa: BLE001
        pass

    qs = RastreioOP.objects.all()
    q = request.GET.get('q', '').strip()
    setor = request.GET.get('setor', '').strip()
    status_filtro = request.GET.get('status', '').strip()

    # Filtra por setor do usuário (apenas gerentes)
    setor_usuario = _setor_do_usuario(request.user)
    if setor_usuario and not request.user.is_superuser:
        qs = qs.filter(setor_atual=setor_usuario.codigo)

    if q:
        from django.db.models import Q
        qs = qs.filter(
            Q(op_numero__icontains=q) | Q(obra__icontains=q) | Q(produto__icontains=q)
        )
    if setor:
        qs = qs.filter(setor_atual=setor)
    if status_filtro:
        qs = qs.filter(status=status_filtro)

    return Response([_serializar_rastreio(r) for r in qs[:200]])


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_rastreio_detalhe(request, op_id):
    """Detalhe do rastreio de uma OP (com histórico)."""
    try:
        garantir_setores_padrao()
    except Exception:  # noqa: BLE001
        pass

    rastreio = RastreioOP.objects.filter(op_id=op_id).first()
    if not rastreio:
        return Response(
            {'erro': 'Rastreio não encontrado para esta OP.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    dados = _serializar_rastreio(rastreio)
    dados['movimentacoes'] = _serializar_movimentacoes(rastreio)
    return Response(dados)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_escanear(request):
    """Registra a leitura do QR Code (mesma lógica do web).

    Body: { "codigo": "31449", "vidro": "sim"|"nao" (opcional) }
    """
    try:
        garantir_setores_padrao()
    except Exception:  # noqa: BLE001
        return Response(
            {'erro': 'Rotina de rastreio não instalada no servidor.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    codigo = str(request.data.get('codigo', '')).strip()
    vidro = str(request.data.get('vidro', '')).strip()

    op_id = _extrair_op_id_do_qr(codigo)
    if not op_id:
        return Response(
            {'erro': f'Código inválido: "{codigo}".'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not _pode_gerenciar(request.user):
        return Response(
            {'erro': 'Apenas usuários de nível Gerência podem registrar a movimentação.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    setor_usuario = _setor_do_usuario(request.user)
    if not setor_usuario:
        return Response(
            {'erro': 'Seu usuário não está vinculado a um setor de produção.'},
            status=status.HTTP_403_FORBIDDEN,
        )
    erro, resultado, precisa_vidro = _registrar_por_setor(
        request, op_id, setor_usuario, vidro
    )

    if erro:
        return Response({'erro': erro}, status=status.HTTP_409_CONFLICT)

    if precisa_vidro:
        return Response({
            'precisa_vidro': True,
            'op_id': op_id,
            'mensagem': 'Esta OP tem vidro?',
        })

    rastreio = resultado['rastreio']
    return Response({
        'ok': True,
        'iniciou': resultado.get('iniciou', False),
        'setor': _serializar_setor(resultado['setor']),
        'rastreio': _serializar_rastreio(rastreio),
    })
