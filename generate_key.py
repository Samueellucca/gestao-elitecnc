# generate_key.py
import bcrypt
import getpass

print("Este script gera um hash de senha compatível com o sistema.")
print("Digite a senha que deseja criptografar. Ela não aparecerá na tela.")
print("Pressione Enter sem digitar nada para sair.")
print("-" * 30)

while True:
    # Pede a senha de forma segura, sem exibir na tela
    password = getpass.getpass("Digite a senha para gerar o hash (ou Enter para sair): ")

    if not password:
        print("Saindo do script.")
        break

    # Codifica a senha para bytes e gera o salt e o hash
    hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    # Decodifica o resultado para string para poder ser salvo no YAML
    hashed_password_str = hashed_pw.decode('utf-8')

    print("\nSenha criptografada (hash):")
    print(f"['{hashed_password_str}']\n")
