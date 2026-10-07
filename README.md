<p align="center">
  <img src="core/static/img/casanovaimg.png" alt="Casanova Esquadrias Prime" width="280"/>
</p>

<h1 align="center">Sistema de Controle de Produção</h1>

<p align="center">
  <strong>Casanova Esquadrias Prime</strong><br/>
  Plataforma integrada para gestão completa da produção de esquadrias de alumínio e vidro.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Django-5.x-092E20?logo=django&logoColor=white" alt="Django"/>
  <img src="https://img.shields.io/badge/Flutter-3.x-02569B?logo=flutter&logoColor=white" alt="Flutter"/>
  <img src="https://img.shields.io/badge/Bootstrap-5.x-7952B3?logo=bootstrap&logoColor=white" alt="Bootstrap"/>
  <img src="https://img.shields.io/badge/PostgreSQL-16-336791?logo=postgresql&logoColor=white" alt="PostgreSQL"/>
  <img src="https://img.shields.io/badge/Nginx-009639?logo=nginx&logoColor=white" alt="Nginx"/>
  <img src="https://img.shields.io/badge/Gunicorn-499848?logo=gunicorn&logoColor=white" alt="Gunicorn"/>
</p>

---

## Visão Geral

O **Sistema de Controle de Produção Casanova** é uma solução desenvolvida para gerenciar de forma integrada todo o ciclo produtivo da Casanova Esquadrias Prime — desde a entrada de matéria-prima no estoque até a expedição do produto final.

A plataforma combina um **painel web administrativo** (Django) com um **aplicativo mobile** (Flutter) para registro em chão de fábrica, garantindo rastreabilidade total de cada ordem de produção em tempo real.

---

## Fluxo Produtivo

O sistema acompanha cada OP (Ordem de Produção) através das seguintes etapas:

```
Estoque → Separação → Corte → Usinagem → Mesa → Encaixilhamento* → Expedição
```

> *A etapa de Encaixilhamento é aplicável apenas aos produtos que utilizam vidro, com decisão registrada na etapa de Mesa.

Cada etapa é registrada via **QR Code** contendo os dados estruturados da Obra/OP, permitindo:
- Rastreamento em tempo real do status de cada peça
- Identificação de gargalos na produção
- Histórico completo por obra, OP ou período

---

## Funcionalidades

### Módulo de Produção
- Cadastro e gestão de Ordens de Produção (OP)
- Rastreamento por QR Code em cada etapa do fluxo produtivo
- Visualização de status em tempo real (painel Kanban)
- Controle de decisão de vidro na etapa de Mesa
- Histórico completo de movimentações

### Módulo de Estoque
- Controle de matéria-prima (alumínio, vidro, acessórios)
- Entrada e saída de materiais vinculadas às OPs
- Alertas de estoque mínimo

### Módulo de Obras
- Cadastro de obras com dados do cliente
- Vinculação de múltiplas OPs por obra
- Acompanhamento de progresso geral da obra

### Módulo de Usuários e Permissões
- Controle de acesso por perfil (administrador, produção, expedição)
- Registro de responsável por cada etapa
- Logs de auditoria

### Módulo de Veículos e Frete
- Cadastro de veículos da frota
- Planejamento de rotas de entrega
- Cálculo de frete por distância e peso
- Vinculação de expedições a veículos e motoristas

### Módulo de Custos
- Apuração de custo por OP (materiais + mão de obra)
- Relatórios de custo por obra
- Comparativo de custo estimado vs. realizado

### Aplicativo Mobile (Flutter)
- Leitura de QR Code via câmera do dispositivo
- Registro de etapas de produção offline/online
- Interface otimizada para uso em chão de fábrica
- Sincronização automática com o servidor

---

## Stack Tecnológica

| Camada | Tecnologia |
|--------|-----------|
| **Backend** | Python 3.14 + Django 5.x |
| **Frontend Web** | Django Templates + Bootstrap 5 + JavaScript |
| **Mobile** | Flutter (Android / iOS / Web) |
| **Banco de Dados** | PostgreSQL 16 |
| **Servidor de Aplicação** | Gunicorn |
| **Proxy Reverso** | Nginx |
| **Biblioteca QR Code** | Python `qrcode` |

---

## Estrutura do Projeto

```
projeto_vidros/
├── core/                    # Aplicação principal Django
│   ├── static/              # Arquivos estáticos (CSS, JS, imagens)
│   │   └── img/             # Logos e imagens institucionais
│   ├── templates/           # Templates HTML
│   ├── models.py            # Modelos de dados
│   ├── views.py             # Views e lógica de negócio
│   └── urls.py              # Rotas da aplicação
├── mobile/                  # Aplicativo Flutter
│   ├── lib/                 # Código Dart
│   ├── android/             # Configuração Android
│   └── ios/                 # Configuração iOS
├── setup/                   # Configurações do projeto Django
│   └── settings.py          # Configurações (banco, apps, etc.)
├── manage.py                # Gerenciador Django
├── requirements.txt         # Dependências Python
└── README.md                # Este arquivo
```

---

## Instalação e Configuração

### Pré-requisitos

- Python 3.14+
- PostgreSQL 16+
- Node.js (para assets, se necessário)
- Flutter SDK (para o mobile)

### Backend (Django)

```bash
# 1. Clone o repositório
git clone https://github.com/casanova-system/casanova.git
cd casanova

# 2. Crie e ative o ambiente virtual
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Configure o banco de dados em setup/settings.py
# (ou via variáveis de ambiente)

# 5. Execute as migrações
python manage.py migrate

# 6. Crie um superusuário
python manage.py createsuperuser

# 7. Inicie o servidor de desenvolvimento
python manage.py runserver 0.0.0.0:8000
```

### Produção (Gunicorn + Nginx)

```bash
# Inicie o Gunicorn
gunicorn setup.wsgi:application --bind 0.0.0.0:8000 --workers 4

# Configure o Nginx como proxy reverso
# (ver arquivo de configuração nginx disponível na documentação)
```

### Mobile (Flutter)

```bash
cd mobile

# Instale as dependências
flutter pub get

# Execute no dispositivo/emulador
flutter run

# Build para produção
flutter build apk --release      # Android
flutter build ios --release      # iOS
```

---

## Acesso ao Sistema

| Ambiente | URL | Credenciais |
|----------|-----|-------------|
| Desenvolvimento | `http://localhost:8000` | Superusuário criado localmente |
| Produção | `http://10.12.50.53` | Contatar administrador |

---

## Equipe

Desenvolvido e mantido pela equipe de tecnologia da **Casanova Esquadrias Prime**.

---

## Licença

Uso interno — Casanova Esquadrias Prime. Todos os direitos reservados.

---

<p align="center">
  <img src="core/static/app/assets/assets/logo_full.png" alt="Casanova Esquadrias Prime" width="180"/>
  <br/>
  <em>Qualidade e precisão em cada esquadria.</em>
</p>
