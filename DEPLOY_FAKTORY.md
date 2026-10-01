# Deploy — Integração com o ERP Faktory (MSSQL)

A rotina **Ordem de Produção (OP)** consulta o banco `faktory_CASANOVA` (SQL Server).
Para isso o servidor precisa de **duas** coisas: os pacotes Python e o **driver ODBC do sistema**.

> Erro `'mssql' isn't an available database backend` = falta o pacote Python `mssql-django`
> no interpretador que roda o serviço (gunicorn/systemd).

---

## 1. Pacotes Python

No ambiente virtual do servidor (o mesmo que roda o gunicorn):

```bash
source /caminho/do/venv/bin/activate
pip install -r requirements.txt
```

Ou diretamente:

```bash
pip install mssql-django==2.0.0 pyodbc==5.3.0
```

Confirme:

```bash
python -c "import mssql, pyodbc; print('OK')"
```

---

## 2. Driver ODBC do sistema (obrigatório)

O `pyodbc` precisa do driver **ODBC Driver 18 for SQL Server** instalado no SO.
Ele **não** vem pelo pip.

### Ubuntu / Debian

```bash
# Dependências
sudo apt-get update
sudo apt-get install -y curl gnupg2 apt-transport-https unixodbc unixodbc-dev

# Repositório da Microsoft (Ubuntu 22.04 — ajuste a versão se necessário)
curl -sSL https://packages.microsoft.com/keys/microsoft.asc | sudo gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg
curl -sSL https://packages.microsoft.com/config/ubuntu/22.04/prod.list | sudo tee /etc/apt/sources.list.d/mssql-release.list

sudo apt-get update
sudo ACCEPT_EULA=Y apt-get install -y msodbcsql18
```

### Verificar se o driver foi instalado

```bash
odbcinst -q -d
# Deve listar: [ODBC Driver 18 for SQL Server]
```

Ou via Python:

```bash
python -c "import pyodbc; print(pyodbc.drivers())"
```

---

## 3. Variáveis de ambiente

Adicione ao `.env` do servidor (ou ao `Environment=` do systemd):

```env
FAKTORY_DB_NAME=faktory_CASANOVA
FAKTORY_DB_USER=pb
FAKTORY_DB_PASSWORD=prefbrasil
FAKTORY_DB_HOST=10.12.50.90
FAKTORY_DB_PORT=1433
FAKTORY_DB_DRIVER=ODBC Driver 18 for SQL Server
```

> Se o servidor Linux tiver apenas o driver **17**, ajuste `FAKTORY_DB_DRIVER=ODBC Driver 17 for SQL Server`.

---

## 4. Testar a conexão

```bash
python manage.py shell -c "
from django.db import connections
c = connections['faktory']
c.ensure_connection()
print('CONEXAO FAKTORY OK')
cur = c.cursor()
cur.execute('SELECT COUNT(*) FROM dbo.ORDEMPRODUCAO')
print('Total OPs:', cur.fetchone()[0])
"
```

Saída esperada:

```
CONEXAO FAKTORY OK
Total OPs: 33885
```

---

## 5. Reiniciar o serviço

```bash
sudo systemctl restart casanova
```

---

## Checklist rápido

| Item | Comando de verificação |
|---|---|
| Pacote Python | `python -c "import mssql"` |
| Driver ODBC | `odbcinst -q -d` |
| Rede até o SQL Server | `nc -zv 10.12.50.90 1433` |
| Conexão Django | `python manage.py shell -c "from django.db import connections; connections['faktory'].ensure_connection(); print('OK')"` |
