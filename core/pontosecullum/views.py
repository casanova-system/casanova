"""Views de visualização READ-ONLY dos bancos PontoSecullum (Casanova, ABRA, STEEL).

NENHUMA escrita é feita — apenas SELECT. O schema é descoberto dinamicamente
via INFORMATION_SCHEMA, então não precisamos de models fixos.
"""
from django.contrib.auth.decorators import login_required
from django.db import connections
from django.shortcuts import render

# Aliases amigáveis para as connections definidas em settings.py
BANCOS = {
    'casanova': 'pontosecullum',
    'abra': 'pontosecullum_abra',
    'steel': 'pontosecullum_steel',
}


def _get_cursor(banco_key):
    """Retorna cursor para o banco selecionado, ou None se indisponível."""
    conn_alias = BANCOS.get(banco_key)
    if not conn_alias:
        return None
    try:
        conn = connections[conn_alias]
        conn.ensure_connection()
        return conn.cursor()
    except Exception:
        return None


def _listar_tabelas(cursor):
    """Lista tabelas do banco (apenas do schema dbo), ordenadas por nome."""
    cursor.execute("""
        SELECT TABLE_NAME
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA = 'dbo' AND TABLE_TYPE = 'BASE TABLE'
        ORDER BY TABLE_NAME
    """)
    return [row[0] for row in cursor.fetchall()]


def _listar_colunas(cursor, tabela):
    """Lista colunas de uma tabela com seus tipos de dados."""
    cursor.execute("""
        SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, IS_NULLABLE
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = %s
        ORDER BY ORDINAL_POSITION
    """, [tabela])
    return cursor.fetchall()


@login_required
def listar_tabelas_ponto(request, banco='casanova'):
    """Lista todas as tabelas do banco PontoSecullum selecionado."""
    context = {'banco': banco, 'bancos': BANCOS.keys()}
    cursor = _get_cursor(banco)
    if cursor is None:
        context['erro'] = f'Conexão com o banco {banco} falhou. Verifique as configurações.'
        return render(request, 'pontosecullum/listar_tabelas.html', context)

    try:
        tabelas = _listar_tabelas(cursor)
        context['tabelas'] = tabelas
        context['total_tabelas'] = len(tabelas)
    except Exception as e:
        context['erro'] = str(e)
    finally:
        cursor.close()

    return render(request, 'pontosecullum/listar_tabelas.html', context)


@login_required
def ver_tabela_ponto(request, banco='casanova', tabela=''):
    """Mostra os dados de uma tabela (SELECT * com LIMIT 500)."""
    context = {'banco': banco, 'tabela': tabela, 'bancos': BANCOS.keys()}
    cursor = _get_cursor(banco)
    if cursor is None:
        context['erro'] = f'Conexão com o banco {banco} falhou.'
        return render(request, 'pontosecullum/ver_tabela.html', context)

    try:
        colunas = _listar_colunas(cursor, tabela)
        context['colunas'] = colunas

        # SELECT * com LIMIT para não sobrecarregar
        # Identificador vem do INFORMATION_SCHEMA (controlado pelo SQL Server),
        # não diretamente do usuário, mas garantimos que é um nome válido.
        cursor.execute(f"SELECT TOP 500 * FROM [{tabela}]")
        col_names = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()

        context['col_names'] = col_names
        context['rows'] = rows
        context['total_rows'] = len(rows)
        context['limit_atingido'] = len(rows) == 500
    except Exception as e:
        context['erro'] = str(e)
    finally:
        cursor.close()

    return render(request, 'pontosecullum/ver_tabela.html', context)


@login_required
def consultar_ponto(request, banco='casanova'):
    """Consulta livre: executa um SELECT informado pelo usuário (somente leitura)."""
    context = {'banco': banco, 'bancos': BANCOS.keys()}
    cursor = _get_cursor(banco)
    if cursor is None:
        context['erro'] = f'Conexão com o banco {banco} falhou.'
        return render(request, 'pontosecullum/consultar.html', context)

    sql = request.GET.get('sql', '').strip()
    if sql:
        # Segurança: bloqueia qualquer coisa que não seja SELECT
        sql_upper = sql.upper().lstrip()
        if not sql_upper.startswith('SELECT'):
            context['erro'] = 'Somente consultas SELECT são permitidas.'
            return render(request, 'pontosecullum/consultar.html', context)
        try:
            cursor.execute(sql)
            col_names = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            context['col_names'] = col_names
            context['rows'] = rows
            context['total_rows'] = len(rows)
        except Exception as e:
            context['erro'] = str(e)
        finally:
            cursor.close()
    else:
        cursor.close()

    return render(request, 'pontosecullum/consultar.html', context)
