# App Mobile — Casanova Esquadrias (Flutter)

Aplicativo mobile para **Rastreio de Produção (OP)**. O sistema web Django
continua funcionando normalmente — este app é uma **opção adicional** para
acessar pelo celular (iOS e Android).

## Arquitetura

```
Celular (Flutter)  ──HTTP/JSON──►  Django REST API  ──►  PostgreSQL
                                    (/api/...)
```

O app consome a API REST criada em `core/api.py`.

## Pré-requisitos

1. **Flutter SDK** — https://docs.flutter.dev/get-started/install
2. Verificar instalação:
   ```bash
   flutter doctor
   ```

## Como rodar

```bash
cd mobile

# Baixar dependências
flutter pub get

# Rodar no emulador/dispositivo conectado
flutter run
```

### Rodar no navegador (teste rápido)

```bash
# Modo debug (requer debug service — pode falhar atrás de firewall)
flutter run -d chrome

# Modo release (recomendado — autocontido, sem debug service)
flutter build web --release
cd build/web
python -m http.server 5600
# abra http://127.0.0.1:5600
```

### Gerar APK para Android

```bash
flutter build apk --release
# saída: build/app/outputs/flutter-apk/app-release.apk
```

## Configurar o endereço do servidor

Edite `lib/config.dart` e ajuste `baseUrl`:

- **Servidor da empresa (celular físico)**: `http://10.12.50.53:8000`
- **Emulador Android**: `http://10.0.2.2:8000`
- **Simulador iOS**: `http://127.0.0.1:8000`
- **Dev local (web/desktop)**: `http://127.0.0.1:8000`

## Funcionalidades

- **Login** com usuário/senha do sistema (token)
- **Escanear** código de barras da OP (câmera ou leitor Bluetooth)
- **Registro automático** por setor (mesmas regras do web)
- **Painel** com as OPs em rastreio
- **Detalhe** da OP com histórico de movimentações

## Regras de negócio (iguais ao web)

- Só **Gerência** registra movimentação
- O **setor do usuário** define a etapa
- **Estoque** inicia o rastreio
- Cada setor só avança se for o **próximo do fluxo**
- **Mesa** pergunta se tem vidro
- Chegar na **Expedição** conclui a OP

## Estrutura

```
mobile/
├── pubspec.yaml
└── lib/
    ├── main.dart              # Entrada + navegação
    ├── config.dart            # URL da API
    ├── models.dart            # Modelos de dados
    ├── api_service.dart       # Cliente HTTP
    └── screens/
        ├── login_screen.dart
        ├── home_screen.dart
        ├── scan_screen.dart
        └── detail_screen.dart
```
