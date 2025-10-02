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
                usuario_lancamento VARCHAR(255)
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

            # --- Garantir colunas adicionais em entradas ---
            connection.execute(text("ALTER TABLE entradas ADD COLUMN IF NOT EXISTS valor_deslocamento NUMERIC(10, 2);"))
            connection.execute(text("ALTER TABLE entradas ADD COLUMN IF NOT EXISTS qtd_tecnicos INTEGER;"))
            connection.execute(text("ALTER TABLE entradas ADD COLUMN IF NOT EXISTS valor_laboratorio NUMERIC(10, 2);"))

            # --- Ativar RLS e criar políticas ---
            tabelas = ["clientes", "saidas", "entradas"]
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

except Exception as e:
    print(f"❌ Erro: {e}")
