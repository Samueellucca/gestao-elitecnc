# limpar_banco.py
import sqlite3
import os

DB_FILE = "financeiro.db"

# Pergunta ao usuário para confirmar a ação, pois ela é irreversível
print("--- ATENÇÃO: AÇÃO DE EXCLUSÃO PERMANENTE DE DADOS ---")
confirmacao = input(f"Tem certeza que deseja apagar TODOS os dados das tabelas 'entradas', 'saidas' e 'clientes' do arquivo '{DB_FILE}'? \nEsta ação não pode ser desfeita. (digite 'sim' para confirmar): ")

if confirmacao.lower() == 'sim':
    if not os.path.exists(DB_FILE):
        print(f"O arquivo de banco de dados '{DB_FILE}' não foi encontrado.")
    else:
        try:
            # Conecta ao banco de dados
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()

            print("\nIniciando limpeza...")

            print("Limpando a tabela 'entradas'...")
            cursor.execute("DELETE FROM entradas;")

            print("Limpando a tabela 'saidas'...")
            cursor.execute("DELETE FROM saidas;")

            print("Limpando a tabela 'clientes'...")
            cursor.execute("DELETE FROM clientes;")

            # Salva as alterações no banco de dados
            conn.commit()
            print("\n✅ Limpeza concluída com sucesso! Todas as tabelas estão vazias.")

        except Exception as e:
            print(f"Ocorreu um erro: {e}")
        finally:
            # Fecha a conexão com o banco de dados
            conn.close()
else:
    print("\nOperação cancelada pelo usuário.")