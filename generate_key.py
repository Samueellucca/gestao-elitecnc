# generate_keys.py
import streamlit_authenticator as stauth

# Coloque a(s) senha(s) que você quer criptografar dentro da lista
passwords_to_hash = ["Elitecnc@2025"]

# Gera o hash das senhas
hashed_passwords = stauth.Hasher(passwords_to_hash).generate()

# Imprime o resultado no terminal
print(hashed_passwords)