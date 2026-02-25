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
        query = "SELECT id, nome, telefone, email, endereco, cnpj FROM clientes ORDER BY nome"
        clientes_df = pd.read_sql_query(query, engine)
        return clientes_df
    except Exception as e:
        st.error(f"Erro ao carregar clientes: {e}")
        return pd.DataFrame(columns=['id', 'nome', 'telefone', 'email', 'endereco'])

def deletar_cliente(id_cliente):
    with engine.connect() as con:
        con.execute(text("DELETE FROM clientes WHERE id = :id"), {"id": id_cliente})
        con.commit()

def atualizar_cliente(id_cliente, dados):
    with engine.connect() as con:
        set_clause = ", ".join([f"{key} = :{key}" for key in dados.keys()])
        dados['id'] = id_cliente
        con.execute(text(f"UPDATE clientes SET {set_clause} WHERE id = :id"), dados)
        con.commit()

# --- FORMULÁRIO PARA NOVO CLIENTE ---
st.subheader("Adicionar Novo Cliente")
with st.form("form_novo_cliente", clear_on_submit=True):
    nome = st.text_input("Nome do Cliente*")
    cnpj = st.text_input("CNPJ")
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
                    "cnpj": cnpj,
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

# Renomeia as colunas para exibição amigável no dataframe
df_clientes_display = df_clientes.rename(columns={
    'id': 'ID', 'nome': 'Nome', 'telefone': 'Telefone', 
    'email': 'Email', 'endereco': 'Endereço', 'cnpj': 'CNPJ'
})

if not df_clientes.empty:
    st.dataframe(df_clientes_display, use_container_width=True, hide_index=True)

    # --- FORMULÁRIO DE ATUALIZAÇÃO ---
    st.markdown("---")
    st.subheader("Atualizar Cadastro de Cliente")
    
    # Usa o dataframe original (colunas minúsculas) para criar a lista
    lista_clientes_display = [f"{row['nome']} (ID: {row['id']})" for index, row in df_clientes.iterrows()]
    cliente_para_atualizar_display = st.selectbox(
        "Selecione um cliente para editar",
        options=[""] + lista_clientes_display,
        key="select_update_cliente"
    )

    if cliente_para_atualizar_display:
        # Extrai o ID e busca no dataframe original
        id_cliente_atualizar = int(cliente_para_atualizar_display.split("(ID: ")[1].replace(")", ""))
        dados_cliente = df_clientes[df_clientes['id'] == id_cliente_atualizar].iloc[0]

        with st.form("form_atualizar_cliente"):
            st.info(f"Você está editando o cliente: **{dados_cliente['nome']}**")
            nome_upd = st.text_input("Nome do Cliente*", value=dados_cliente['nome'])
            cnpj_upd = st.text_input("CNPJ", value=dados_cliente['cnpj'] if pd.notnull(dados_cliente['cnpj']) else "")
            telefone_upd = st.text_input("Telefone", value=dados_cliente['telefone'])
            email_upd = st.text_input("Email", value=dados_cliente['email'])
            endereco_upd = st.text_area("Endereço", value=dados_cliente['endereco'])
            
            submit_update_button = st.form_submit_button("Salvar Alterações")

            if submit_update_button:
                if not nome_upd:
                    st.error("O campo 'Nome do Cliente' é obrigatório.")
                else:
                    try:
                        dados_atualizados = {"nome": nome_upd, "cnpj": cnpj_upd, "telefone": telefone_upd, "email": email_upd, "endereco": endereco_upd}
                        atualizar_cliente(id_cliente_atualizar, dados_atualizados)
                        
                        # --- CORREÇÃO: Atualizar nome nas entradas antigas se o nome mudou ---
                        nome_antigo = dados_cliente['nome']
                        if nome_antigo != nome_upd:
                            with engine.connect() as con:
                                con.execute(text("UPDATE entradas SET cliente = :novo WHERE cliente = :antigo"), {"novo": nome_upd, "antigo": nome_antigo})
                                con.commit()
                        
                        st.success(f"Cliente '{nome_upd}' atualizado com sucesso!")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao atualizar cliente: {e}")

    st.markdown("---")
    st.subheader("Excluir Cliente")
    
    cliente_para_excluir_display = st.selectbox(
        "Selecione um cliente para excluir",
        options=[""] + lista_clientes_display,
        key="select_delete_cliente"
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