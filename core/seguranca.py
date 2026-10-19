"""Criptografia reversível da senha do usuário (para o admin poder ver).

POR QUE ISSO EXISTE
    O Django guarda a senha como HASH PBKDF2 — irreversível por design. Isso
    protege os usuários se o banco vazar, mas impede o administrador de
    lembrar a senha de alguém que esqueceu. Numa fábrica, o gestor precisa
    repassar a senha para o funcionário no chão de fábrica.

COMO FUNCIONA
    Guardamos a senha TAMBÉM em `PerfilUsuario.senha_visivel`, cifrada com
    Fernet (AES-128-CBC + HMAC-SHA256). A chave é derivada da SECRET_KEY do
    projeto — que vive no .env, NÃO no banco.

O QUE ISSO PROTEGE E O QUE NÃO PROTEGE
    Protege: quem obtiver só um dump do banco (backup vazado, SQL injection)
    não consegue ler as senhas — falta a SECRET_KEY.
    NÃO protege: quem tiver acesso ao servidor (código + .env) lê tudo. Isso
    é inerente a qualquer esquema reversível.

    O hash do Django continua sendo a fonte de verdade para o login. Este
    campo é só conveniência do administrador; se ele estiver vazio ou
    corrompido, o login funciona igual.
"""
import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def _fernet():
    """Deriva uma chave Fernet estável a partir da SECRET_KEY do projeto."""
    chave = hashlib.sha256(
        ('casanova-senha-visivel:' + settings.SECRET_KEY).encode('utf-8')
    ).digest()
    return Fernet(base64.urlsafe_b64encode(chave))


def cifrar(senha):
    """Devolve a senha cifrada, ou '' se não houver senha."""
    if not senha:
        return ''
    return _fernet().encrypt(senha.encode('utf-8')).decode('ascii')


def decifrar(valor):
    """Devolve a senha em texto claro, ou '' se não der para decifrar.

    Devolver '' em vez de estourar exceção é proposital: se a SECRET_KEY
    mudar (troca de servidor, rotação de chave), o campo fica ilegível mas
    o sistema continua funcionando — o admin só recadastra a senha.
    """
    if not valor:
        return ''
    try:
        return _fernet().decrypt(valor.encode('ascii')).decode('utf-8')
    except (InvalidToken, ValueError, TypeError):
        return ''
