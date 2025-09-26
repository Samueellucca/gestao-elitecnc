import sqlite3
import os

DB_FILE = "financeiro.db"

# Pergunta ao usuário para confirmar a ação, pois ela é irreversível
confirmacao = input(f"Tem certeza que deseja apagar TODOS os lançamentos de entradas e saídas do arquivo '{DB_FILE}'? \nIsso não pode ser desfeito. (digite 'sim' para confirmar): ")

if confirmacao.lower() == 'sim':
    if not os.path.exists(DB_FILE):
        print(f"O arquivo de banco de dados '{DB_FILE}' não foi encontrado.")
    else:
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()

            print("Limpando a tabela 'entradas'...")
            cursor.execute("DELETE FROM entradas;")

            print("Limpando a tabela 'saidas'...")
            cursor.execute("DELETE FROM saidas;")

            # Opcional: Para resetar os IDs que auto incrementam
            # cursor.execute("DELETE FROM sqlite_sequence WHERE name='entradas';")
            # cursor.execute("DELETE FROM sqlite_sequence WHERE name='saidas';")

            conn.commit()
            print("\nLançamentos de entradas e saídas foram apagados com sucesso!")

        except Exception as e:
            print(f"Ocorreu um erro: {e}")
        finally:
            conn.close()
else:
    print("Operação cancelada.")