# setup_nuvem.py
import sqlalchemy
from sqlalchemy import text

# 🔗 URL de conexão Supabase
DATABASE_URL = "postgresql://postgres.ipthtamwddcocqrpzkvh:sslguimaraes271821@aws-1-sa-east-1.pooler.supabase.com:6543/postgres"

try:
    engine = sqlalchemy.create_engine(DATABASE_URL)

    def create_or_update_tables():
        with engine.connect() as connection:
            print("🔗 Conectado ao banco de dados!")

            # --- Criar tabelas se não existirem ---
            connection.execute(text("""
            CREATE TABLE IF NOT EXISTS clientes (
                id SERIAL PRIMARY KEY,
                nome VARCHAR(255) UNIQUE NOT NULL,
                telefone VARCHAR(255),
                email VARCHAR(255),
                endereco TEXT
            );"""))

            connection.execute(text("""
            CREATE TABLE IF NOT EXISTS saidas (
                id SERIAL PRIMARY KEY,
                data TIMESTAMP NOT NULL,
                tipo_conta VARCHAR(255),
                descricao TEXT,
                valor NUMERIC(10, 2),
                usuario_lancamento VARCHAR(255),
                status VARCHAR(50) DEFAULT 'Pendente'
            );"""))

            connection.execute(text("""
            CREATE TABLE IF NOT EXISTS entradas (
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

            connection.execute(text("""
            CREATE TABLE IF NOT EXISTS configuracoes (
                id SERIAL PRIMARY KEY,
                chave VARCHAR(255) UNIQUE NOT NULL,
                valor TEXT,
                descricao TEXT
            );"""))

            connection.execute(text("""
            CREATE TABLE IF NOT EXISTS estoque_componentes (
                id SERIAL PRIMARY KEY,
                nome VARCHAR(255) UNIQUE NOT NULL,
                categoria VARCHAR(255),
                estoque_minimo INTEGER DEFAULT 0,
                qtd_laboratorio INTEGER DEFAULT 0,
                qtd_assistencia INTEGER DEFAULT 0
            );"""))

            connection.execute(text("""
            CREATE TABLE IF NOT EXISTS estoque_movimentacao (
                id SERIAL PRIMARY KEY,
                componente_id INTEGER REFERENCES estoque_componentes(id) ON DELETE CASCADE,
                data TIMESTAMP NOT NULL,
                tipo_movimento VARCHAR(50), -- 'Entrada' ou 'Saída'
                local VARCHAR(100), -- 'Laboratório' ou 'Assistência Técnica'
                quantidade INTEGER,
                observacao TEXT,
                usuario_lancamento VARCHAR(255)
            );"""))

            # --- Garantir colunas adicionais em entradas ---
            connection.execute(text("ALTER TABLE entradas ADD COLUMN IF NOT EXISTS valor_deslocamento NUMERIC(10, 2);"))
            connection.execute(text("ALTER TABLE entradas ADD COLUMN IF NOT EXISTS qtd_tecnicos INTEGER;"))
            connection.execute(text("ALTER TABLE entradas ADD COLUMN IF NOT EXISTS valor_laboratorio NUMERIC(10, 2);"))
            connection.execute(text("ALTER TABLE entradas ADD COLUMN IF NOT EXISTS data_pagamento TIMESTAMP;"))
            connection.execute(text("ALTER TABLE saidas ADD COLUMN IF NOT EXISTS data_pagamento TIMESTAMP;"))
            connection.execute(text("ALTER TABLE entradas ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'Pendente';"))
            connection.execute(text("ALTER TABLE entradas ADD COLUMN IF NOT EXISTS nome_tecnicos VARCHAR(255);"))

            # --- Inserir valores padrão na tabela de configurações se não existirem ---
            connection.execute(text("INSERT INTO configuracoes (chave, valor, descricao) VALUES ('valor_por_km', '2.45', 'Valor cobrado por KM rodado.') ON CONFLICT (chave) DO NOTHING;"))
            connection.execute(text("INSERT INTO configuracoes (chave, valor, descricao) VALUES ('valor_hora_tecnica', '100.00', 'Valor padrão da hora técnica.') ON CONFLICT (chave) DO NOTHING;"))
            connection.execute(text("INSERT INTO configuracoes (chave, valor, descricao) VALUES ('empresa_razao_social', 'Elite CNC Service', 'Razão Social ou Nome da Empresa para PDFs.') ON CONFLICT (chave) DO NOTHING;"))
            connection.execute(text("INSERT INTO configuracoes (chave, valor, descricao) VALUES ('empresa_cnpj', 'CNPJ: 61.159.425/0001-32', 'CNPJ da empresa para PDFs.') ON CONFLICT (chave) DO NOTHING;"))

            # --- Ativar RLS e criar políticas ---
            tabelas = ["clientes", "saidas", "entradas", "estoque_componentes", "estoque_movimentacao"]
            for tabela in tabelas:
                connection.execute(text(f"ALTER TABLE {tabela} ENABLE ROW LEVEL SECURITY;"))

                # Política de leitura: usuário só vê seus registros
                connection.execute(text(f"""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_policies
                        WHERE schemaname = 'public'
                        AND tablename = '{tabela}'
                        AND policyname = 'user_can_select_own'
                    ) THEN
                        CREATE POLICY user_can_select_own ON {tabela}
                        FOR SELECT
                        USING (usuario_lancamento = auth.uid()::text);
                    END IF;
                END
                $$;
                """))

                # Política de inserção: usuário só pode inserir registros próprios
                connection.execute(text(f"""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_policies
                        WHERE schemaname = 'public'
                        AND tablename = '{tabela}'
                        AND policyname = 'user_can_insert_own'
                    ) THEN
                        CREATE POLICY user_can_insert_own ON {tabela}
                        FOR INSERT
                        WITH CHECK (usuario_lancamento = auth.uid()::text);
                    END IF;
                END
                $$;
                """))

            connection.commit()
            print("✅ Estrutura atualizada + RLS ativado com políticas seguras!")

    if __name__ == "__main__":
        create_or_update_tables()
        print("\nLembre-se de executar este script para aplicar as alterações no banco de dados!")

except Exception as e:
    print(f"❌ Erro: {e}")
