# setup_database.py (Versão com Hora de Início/Fim)
import sqlite3

DB_FILE = "financeiro.db"

def get_table_columns(cursor, table_name):
    """Retorna uma lista com os nomes das colunas de uma tabela."""
    try:
        cursor.execute(f"PRAGMA table_info({table_name});")
        return [row[1] for row in cursor.fetchall()]
    except sqlite3.OperationalError:
        return []

conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()

print("Verificando/Criando tabelas...")

cursor.execute("""
CREATE TABLE IF NOT EXISTS entradas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data TEXT NOT NULL,
    ordem_servico TEXT,
    valor_atendimento REAL,
    horas_tecnicas REAL,
    horas_tecnicas_50 REAL,
    horas_tecnicas_100 REAL,
    km REAL,
    refeicao REAL,
    pecas REAL,
    hora_inicio TEXT,
    hora_fim TEXT
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS saidas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data TEXT NOT NULL,
    tipo_conta TEXT,
    descricao TEXT,
    valor REAL
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS clientes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT UNIQUE NOT NULL,
    telefone TEXT,
    email TEXT,
    endereco TEXT
);
""")

colunas_entradas = {
    "usuario_lancamento": "TEXT",
    "descricao_servico": "TEXT",
    "pedagio": "REAL",
    "cliente": "TEXT",
    "horas_tecnicas_100": "REAL",
    "hora_inicio": "TEXT",      # <-- ADICIONADO AQUI
    "hora_fim": "TEXT"          # <-- E AQUI
}
colunas_existentes_entradas = get_table_columns(cursor, 'entradas')
for col, tipo in colunas_entradas.items():
    if col not in colunas_existentes_entradas:
        cursor.execute(f"ALTER TABLE entradas ADD COLUMN {col} {tipo};")
        print(f"Coluna '{col}' adicionada à tabela 'entradas'.")

colunas_saidas = {
    "usuario_lancamento": "TEXT"
}
colunas_existentes_saidas = get_table_columns(cursor, 'saidas')
for col, tipo in colunas_saidas.items():
    if col not in colunas_existentes_saidas:
        cursor.execute(f"ALTER TABLE saidas ADD COLUMN {col} {tipo};")
        print(f"Coluna '{col}' adicionada à tabela 'saidas'.")

conn.commit()
conn.close()

print("\nBanco de dados preparado com sucesso!")