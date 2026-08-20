import os
from pathlib import Path

from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-insecure-change-me')

DEBUG = os.environ.get('DEBUG', 'True').lower() in ('1', 'true', 'yes')

ALLOWED_HOSTS = [h.strip() for h in os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1,backend').split(',') if h.strip()]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.postgres',
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'apps.cadastros',
    'apps.auditoria',
    'apps.produtos',
    'apps.corridas',
    'apps.regras_fiscais',
    'apps.comercial',
    'apps.fiscal',
    'apps.qualidade',
    'apps.apuracao_fiscal',
    'apps.contabil',
    'apps.financeiro',
    'apps.relatorios',
    'apps.core',
    'apps.expedicao',
    'apps.crm',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'nexus_erp.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

WSGI_APPLICATION = 'nexus_erp.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'nexus_erp'),
        'USER': os.environ.get('DB_USER', 'postgres'),
        'PASSWORD': os.environ.get('DB_PASSWORD', 'postgres'),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ERP 4.0.14.x — política de ocupação do prefixo em codigo_figura automático.
# Decisão de produção (operador): PREFIXO_GLOBAL_UNICIDADE
#   — OD/STD/etc. vêm do template dimensional; não cadastrar famílias 6119 e 6119OD distintas.
# Valores aceitos: VALOR_COMPLETO | PREFIXO_GLOBAL_UNICIDADE | PREFIXO_GLOBAL_SEQUENCIAL
# Em produção definir explicitamente:
# FAMILIA_CODIGO_POLITICA_PREFIXO=PREFIXO_GLOBAL_UNICIDADE

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=8),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'AUTH_HEADER_TYPES': ('Bearer',),
}

CORS_ALLOWED_ORIGINS = [
    'http://localhost:5173',
    'http://127.0.0.1:5173',
    'http://localhost:5174',
    'http://127.0.0.1:5174',
]
CORS_ALLOW_CREDENTIALS = True

# Integração servidor a servidor do site com o CRM. Definir somente por ambiente;
# nunca versionar o segredo no repositório.
CRM_SITE_HMAC_SECRET = os.environ.get('CRM_SITE_HMAC_SECRET', '')

# Propostas: quando True, busca RegraFiscalSaida no cenário padrão antes do fallback legado.
USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS = os.environ.get(
    'USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS',
    'false',
).lower() in ('1', 'true', 'yes')

# ERP 4.0.13.6.13A — DANFE oficial exclusivamente via BrazilFiscalReport (BFR)
DANFE_RENDERER_OFICIAL = os.environ.get('DANFE_RENDERER_OFICIAL', 'BFR').strip().upper()
DANFE_ALLOW_HTML_FALLBACK = os.environ.get('DANFE_ALLOW_HTML_FALLBACK', 'false').lower() in (
    '1',
    'true',
    'yes',
)
DANFE_ALLOW_HTML_DIAGNOSTIC = os.environ.get('DANFE_ALLOW_HTML_DIAGNOSTIC', 'false').lower() in (
    '1',
    'true',
    'yes',
)
DANFE_BLOCK_EMISSION_IF_BFR_FAILS = os.environ.get('DANFE_BLOCK_EMISSION_IF_BFR_FAILS', 'true').lower() in (
    '1',
    'true',
    'yes',
)
DANFE_LOG_RENDERER = os.environ.get('DANFE_LOG_RENDERER', 'true').lower() in ('1', 'true', 'yes')
FISCAL_NFE_SERIE_PRELIMINAR = os.environ.get('FISCAL_NFE_SERIE_PRELIMINAR', '900').strip()
FISCAL_PERSISTIR_XML_PRELIMINAR = os.environ.get('FISCAL_PERSISTIR_XML_PRELIMINAR', 'false').lower() in (
    '1',
    'true',
    'yes',
)
NFE_PERF_LOGGING = os.environ.get('NFE_PERF_LOGGING', '').lower() in ('1', 'true', 'yes') or DEBUG
FISCAL_CODIGO_MUNICIPIO_FG = os.environ.get('FISCAL_CODIGO_MUNICIPIO_FG', '3550308').strip()

# Reforma Tributária NF-e (ERP 4.0.13.4) — camada isolada; produção bloqueada por padrão
REFORMA_TRIBUTARIA_NFE_ENABLED = os.environ.get('REFORMA_TRIBUTARIA_NFE_ENABLED', 'false').lower() in (
    '1',
    'true',
    'yes',
)
REFORMA_TRIBUTARIA_NFE_MODO = os.environ.get('REFORMA_TRIBUTARIA_NFE_MODO', 'pesquisa').strip().lower()
REFORMA_TRIBUTARIA_NFE_AMBIENTE_HOMOLOGACAO = os.environ.get(
    'REFORMA_TRIBUTARIA_NFE_AMBIENTE_HOMOLOGACAO',
    'true',
).lower() in ('1', 'true', 'yes')
REFORMA_TRIBUTARIA_NFE_INCLUIR_XML = os.environ.get('REFORMA_TRIBUTARIA_NFE_INCLUIR_XML', 'false').lower() in (
    '1',
    'true',
    'yes',
)
REFORMA_TRIBUTARIA_NFE_INCLUIR_DANFE = os.environ.get('REFORMA_TRIBUTARIA_NFE_INCLUIR_DANFE', 'false').lower() in (
    '1',
    'true',
    'yes',
)

# ERP 4.0.15.x Fase 3B — emissão NF-e Saída produção SEFAZ (default desligado)
NFE_PRODUCAO_HABILITADA = os.environ.get('NFE_PRODUCAO_HABILITADA', 'false').lower() in (
    '1',
    'true',
    'yes',
)


def _email_env_bool(key: str, default: str = 'False') -> bool:
    """Interpreta variáveis SMTP booleanas do ambiente (1/true/yes/on)."""
    return os.getenv(key, default).strip().lower() in ('1', 'true', 'yes', 'on')


def _email_env_int(key: str, default: str) -> int:
    """Interpreta porta SMTP do ambiente com fallback seguro."""
    raw = (os.getenv(key, default) or default).strip()
    try:
        return int(raw)
    except ValueError:
        return int(default)


# E-mail operacional (envio manual DANFE/XML NF-e) — valores reais apenas no .env do servidor
EMAIL_BACKEND = os.getenv(
    'EMAIL_BACKEND',
    'django.core.mail.backends.smtp.EmailBackend',
)
EMAIL_HOST = os.getenv('EMAIL_HOST', 'localhost').strip()
EMAIL_PORT = _email_env_int('EMAIL_PORT', '25')
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '').strip()
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '').strip()
EMAIL_USE_TLS = _email_env_bool('EMAIL_USE_TLS', 'False')
EMAIL_USE_SSL = _email_env_bool('EMAIL_USE_SSL', 'False')
DEFAULT_FROM_EMAIL = os.getenv(
    'DEFAULT_FROM_EMAIL',
    EMAIL_HOST_USER or 'webmaster@localhost',
).strip()
NEXUS_EMAIL_OPERACIONAL = os.getenv(
    'NEXUS_EMAIL_OPERACIONAL',
    DEFAULT_FROM_EMAIL,
).strip()

# ERP 4.0.13.7.2 — testes só em banco isolado (test_*)
TEST_RUNNER = 'nexus_erp.test_runner.NexusDiscoverRunner'
