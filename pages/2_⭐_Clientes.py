# pages/2_⭐_Clientes.py
import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
import pandas as pd
from sqlalchemy import create_engine, text

# --- VERIFICAÇÃO DE LOGIN ---
if "authentication_status" not in st.session_state:
    st.error("Por favor, faça login na página inicial.")
    st.stop()
elif st.session_state["authentication_status"] is False:
    st.error("Usuário ou senha inválidos. Volte à página inicial e tente novamente.")
    st.stop()
elif st.session_state["authentication_status"] is None:
    st.warning("Você precisa estar logado para acessar esta página.")
    st.stop()

# Se chegou aqui, está logado:
st.sidebar.image("logo.png", width=150)
st.sidebar.button("Sair", on_click=lambda: st.session_state.update({"authentication_status": None}))

# --- CONFIGURAÇÃO DA PÁGINA E CONEXÃO COM DB ---
st.set_page_config(page_title="Cadastro de Clientes", page_icon="⭐", layout="wide")
st.title("⭐ Cadastro de Clientes")

# Conexão com o banco de dados da nuvem a partir dos "Secrets"
connection_url = st.secrets["database"]["connection_url"]
engine = create_engine(connection_url)

# --- FUNÇÕES DE BANCO DE DADOS ---
@st.cache_data
def carregar_clientes_db():
    try:
        query = "SELECT id as ID, nome as Nome, telefone as Telefone, email as Email, endereco as Endereço FROM clientes ORDER BY Nome"
        clientes_df = pd.read_sql_query(query, engine)
        return clientes_df
    except Exception as e:
        st.error(f"Erro ao carregar clientes: {e}")
        return pd.DataFrame(columns=['ID', 'Nome', 'Telefone', 'Email', 'Endereço'])

def deletar_cliente(id_cliente):
    with engine.connect() as con:
        con.execute(text("DELETE FROM clientes WHERE id = :id"), {"id": id_cliente})
        con.commit()

# --- FORMULÁRIO PARA NOVO CLIENTE ---
st.subheader("Adicionar Novo Cliente")
with st.form("form_novo_cliente", clear_on_submit=True):
    nome = st.text_input("Nome do Cliente*")
    telefone = st.text_input("Telefone")
    email = st.text_input("Email")
    endereco = st.text_area("Endereço")
    
    submit_button = st.form_submit_button("Cadastrar Cliente")

    if submit_button:
        if not nome:
            st.error("O campo 'Nome do Cliente' é obrigatório.")
        else:
            try:
                novo_cliente = pd.DataFrame([{
                    "nome": nome,
                    "telefone": telefone,
                    "email": email,
                    "endereco": endereco
                }])
                novo_cliente.to_sql('clientes', engine, if_exists='append', index=False)
                st.success(f"Cliente '{nome}' cadastrado com sucesso!")
                st.cache_data.clear() # Limpa o cache para recarregar a lista
            except Exception as e:
                st.error(f"Erro ao cadastrar cliente: {e}. O nome do cliente já pode existir.")

st.markdown("---")

# --- VISUALIZAÇÃO E EXCLUSÃO DE CLIENTES ---
st.subheader("Clientes Cadastrados")
df_clientes = carregar_clientes_db()

if not df_clientes.empty:
    st.dataframe(df_clientes, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("Excluir Cliente")
    
    # Prepara a lista de nomes para o selectbox, no formato "Nome (ID: X)"
    lista_clientes_excluir = [f"{row['nome']} (ID: {row['id']})" for index, row in df_clientes.iterrows()]
    cliente_para_excluir_display = st.selectbox(
        "Selecione um cliente para excluir",
        options=[""] + lista_clientes_excluir
    )

    if cliente_para_excluir_display:
        if st.button("Excluir Cliente Selecionado", type="primary"):
            try:
                # Extrai o ID do texto "Nome (ID: X)"
                id_cliente_excluir = int(cliente_para_excluir_display.split("(ID: ")[1].replace(")", ""))
                deletar_cliente(id_cliente_excluir)
                st.success("Cliente excluído com sucesso!")
                st.cache_data.clear()
                st.rerun() # Recarrega a página para atualizar as listas
            except Exception as e:
                st.error(f"Erro ao excluir o cliente: {e}")
else:
    st.info("Nenhum cliente cadastrado ainda.")