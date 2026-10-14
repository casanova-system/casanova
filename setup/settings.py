from pathlib import Path
import os
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent

# A chave do Render será lida da variável de ambiente se existir, senão usa a padrão
SECRET_KEY = config('SECRET_KEY', default='django-insecure-chave-temporaria-para-desenvolvimento-local')

# Forçado como True temporariamente para exibir a tela de erro detalhada do Django
DEBUG = config('DEBUG', default=True, cast=bool)

# Permite acesso de qualquer host para testes
ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',  # API REST (app mobile Flutter)
    'rest_framework.authtoken',  # Token de autenticação para o app
    'corsheaders',  # CORS para o app Flutter (web/mobile)
    'core',  # Seu app principal
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Servidor de arquivos estáticos para produção
    'corsheaders.middleware.CorsMiddleware',  # CORS (deve vir antes do CommonMiddleware)
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # MobileRedirectMiddleware DESATIVADO: o celular agora usa a mesma tela
    # responsiva do PC (rotina de Produção com leitor de QR pela câmera).
    # O app Flutter continua acessível manualmente em /app/ se necessário.
    # 'core.middleware.MobileRedirectMiddleware',
]

ROOT_URLCONF = 'setup.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'setup.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
    },
    'faktory': {
        'ENGINE': 'mssql',
        # Sem valores default: as credenciais do ERP vem SEMPRE do .env.
        # Isso evita credencial fixa no codigo e falha explicita se faltar.
        'NAME': config('FAKTORY_DB_NAME', default='faktory_CASANOVA'),
        'USER': config('FAKTORY_DB_USER'),
        'PASSWORD': config('FAKTORY_DB_PASSWORD'),
        'HOST': config('FAKTORY_DB_HOST'),
        'PORT': config('FAKTORY_DB_PORT', default='1433'),
        'OPTIONS': {
            'driver': config('FAKTORY_DB_DRIVER', default='ODBC Driver 18 for SQL Server'),
            'extra_params': 'TrustServerCertificate=yes;Encrypt=no;',
            'timeout': 15,
        },
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'pt-br'

TIME_ZONE = 'America/Cuiaba'

USE_I18N = True

USE_TZ = True

# Autenticação: rota de login padrão usada pelo @login_required
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'menu_principal'
LOGOUT_REDIRECT_URL = 'login'

# Arquivos Estáticos (CSS, JavaScript, Imagens)
STATIC_URL = '/static/'

# Adiciona STATICFILES_DIRS apenas se a pasta 'static' existir
STATIC_DIR = BASE_DIR / 'static'
if STATIC_DIR.exists():
    STATICFILES_DIRS = [STATIC_DIR]
else:
    STATICFILES_DIRS = []

# Configurações do WhiteNoise para coletar estáticos na hospedagem
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Arquivos de Mídia (Uploads de usuários / Fotos de perfil)
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# ==========================================
# HTTPS atrás do nginx (proxy reverso)
# ==========================================
# O nginx termina o TLS e repassa X-Forwarded-Proto. Sem isto o Django acharia
# que a requisição é HTTP e geraria redirects/URLs erradas (loop de redirecionamento).
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Origens confiáveis para CSRF (acesso via HTTPS pelo IP da rede interna).
# Necessário para a câmera funcionar: navegador só libera getUserMedia em HTTPS.
CSRF_TRUSTED_ORIGINS = [
    'https://10.12.50.53',
    'https://casanova.sistema',
    'http://10.12.50.53:8000',
    'http://10.12.50.53',
]

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ==========================================
# API REST — App Mobile (Flutter)
# ==========================================
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        # Apenas Token: evita o CSRF do SessionAuthentication quando o app
        # Flutter roda na mesma origem do Django (navegador do celular).
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
}

# CORS — permite que o app Flutter (web/mobile) acesse a API.
# Em produção, restrinja CORS_ALLOWED_ORIGINS aos domínios reais.
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True