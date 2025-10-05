import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
from email.message import EmailMessage
import smtplib
from datetime import datetime

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
st.set_page_config(page_title="Enviar Nota Fiscal", page_icon="🧾", layout="centered")
st.title("🧾 Enviar Nota Fiscal (NF)")
st.write("Selecione o cliente, anexe a Nota Fiscal em PDF e envie por email.")

# Conexão com o banco de dados
connection_url = st.secrets["database"]["connection_url"]
engine = create_engine(connection_url)

# --- FUNÇÕES AUXILIARES ---

@st.cache_data
def carregar_clientes():
    """Carrega os clientes do banco de dados para o selectbox."""
    try:
        clientes_df = pd.read_sql_query(
            "SELECT nome, email FROM clientes ORDER BY nome",
            engine
        )
        return clientes_df
    except Exception as e:
        st.error(f"Erro ao carregar clientes: {e}")
        return pd.DataFrame(columns=['nome', 'email'])

def enviar_email_com_anexo(destinatario, assunto, corpo, dados_anexo, nome_anexo):
    """Envia um email com um anexo em PDF."""
    try:
        remetente = st.secrets["email_credentials"]["username"]
        senha = st.secrets["email_credentials"]["password"]
        
        msg = EmailMessage()
        msg['Subject'] = assunto
        msg['From'] = remetente
        msg['To'] = destinatario
        msg.set_content(corpo)
        
        # Adiciona o anexo
        msg.add_attachment(dados_anexo, maintype='application', subtype='pdf', filename=nome_anexo)
        
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(remetente, senha)
            smtp.send_message(msg)
            
        st.success(f"Email com a Nota Fiscal enviado para {destinatario} com sucesso!")
        return True
    except Exception as e:
        st.error(f"Erro ao enviar email: {e}")
        st.error("Verifique as credenciais em secrets.toml e sua Senha de App.")
        return False

# --- INTERFACE PRINCIPAL ---

df_clientes = carregar_clientes()
lista_clientes_nomes = [""] + df_clientes['nome'].tolist() if not df_clientes.empty else []

if not lista_clientes_nomes:
    st.warning("Nenhum cliente cadastrado. Cadastre um cliente na página '⭐ Clientes' primeiro.")
else:
    col1, col2 = st.columns([2, 1])
    with col1:
        cliente_selecionado = st.selectbox("Selecione o Cliente:", options=lista_clientes_nomes)
    with col2:
        mes_referencia = st.text_input("Mês/Ano de Referência", placeholder="Ex: Janeiro/2024")

    uploaded_file = st.file_uploader("Anexe a Nota Fiscal (PDF)", type="pdf")

    if cliente_selecionado and mes_referencia and uploaded_file:
        dados_cliente = df_clientes[df_clientes['nome'] == cliente_selecionado].iloc[0]
        email_cliente = dados_cliente.get('email')

        if email_cliente and pd.notnull(email_cliente):
            st.markdown("---")
            st.subheader("Preparar e Enviar Email")

            assunto_padrao = f"Nota Fiscal de Serviços - {cliente_selecionado} - Ref. {mes_referencia}"
            corpo_padrao = f"""Prezado(a) {cliente_selecionado},

Segue em anexo a Nota Fiscal referente aos serviços prestados no período de {mes_referencia}.

Qualquer dúvida, estamos à disposição.

Filipe Guimarães
Sócio Proprietário
WhatsApp: (11) 97761-7009
elitecncservice@gmail.com
http://www.elitecncservice.com.br
"""


            assunto = st.text_input("Assunto do Email:", value=assunto_padrao)
            corpo_email = st.text_area("Corpo do Email:", value=corpo_padrao, height=200)

            if st.button(f"🚀 Enviar para {email_cliente}", type="primary", use_container_width=True):
                pdf_bytes = uploaded_file.getvalue()
                enviar_email_com_anexo(email_cliente, assunto, corpo_email, pdf_bytes, uploaded_file.name)
        else:
            st.error(f"O cliente '{cliente_selecionado}' não possui um email cadastrado. Por favor, atualize o cadastro na página '⭐ Clientes'.")