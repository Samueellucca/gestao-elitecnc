# setup_nuvem.py
import sqlalchemy
from sqlalchemy import text

# 🔗 URL de conexão Supabase
# Troque "211218Lucca" pela sua senha real (faça URL encoding se tiver caracteres especiais)
DATABASE_URL = "postgresql://postgres.ipthtamwddcocqrpzkvh:sslguimaraes271821@aws-1-sa-east-1.pooler.supabase.com:6543/postgres"

try:
    engine = sqlalchemy.create_engine(DATABASE_URL)

    def create_tables():
        with engine.connect() as connection:
            print("Conectado ao banco de dados na nuvem!")

            # Apaga tabelas antigas (se existirem)
            connection.execute(text("DROP TABLE IF EXISTS entradas, saidas, clientes;"))

            # Cria tabela de clientes
            connection.execute(text("""
            CREATE TABLE clientes (
                id SERIAL PRIMARY KEY,
                nome VARCHAR(255) UNIQUE NOT NULL,
                telefone VARCHAR(255),
                email VARCHAR(255),
                endereco TEXT
            );"""))

            # Cria tabela de saídas
            connection.execute(text("""
            CREATE TABLE saidas (
                id SERIAL PRIMARY KEY,
                data TIMESTAMP NOT NULL,
                tipo_conta VARCHAR(255),
                descricao TEXT,
                valor NUMERIC(10, 2),
                usuario_lancamento VARCHAR(255)
            );"""))

            # Cria tabela de entradas
            connection.execute(text("""
            CREATE TABLE entradas (
                id SERIAL PRIMARY KEY,
                data TIMESTAMP NOT NULL,
                ordem_servico VARCHAR(255),
                descricao_servico TEXT,
                patrimonio VARCHAR(255),
                maquina VARCHAR(255),
                cliente VARCHAR(255),
                valor_atendimento NUMERIC(10, 2),
                horas_tecnicas NUMERIC(10, 2),
                horas_tecnicas_50 NUMERIC(10, 2),
                horas_tecnicas_100 NUMERIC(10, 2),
                km NUMERIC(10, 2),
                refeicao NUMERIC(10, 2),
                pecas NUMERIC(10, 2),
                pedagio NUMERIC(10, 2),
                usuario_lancamento VARCHAR(255),
                hora_inicio TEXT,
                hora_fim TEXT
            );"""))

            connection.commit()
            print("✅ Tabelas criadas com sucesso!")

    if __name__ == "__main__":
        create_tables()

except Exception as e:
    print(f"❌ Ocorreu um erro: {e}")
    print("Verifique a URL de conexão ou se o 'psycopg2-binary' está instalado.")
