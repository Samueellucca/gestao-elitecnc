import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
from urllib.parse import quote
import re
import smtplib
from email.message import EmailMessage

# --- CONFIGURAÇÃO DA PÁGINA E CONEXÃO COM DB ---
st.set_page_config(page_title="Enviar Relatório", page_icon="📧", layout="centered")
st.title("📧 Enviar Relatório de O.S.")
st.write("Selecione uma Ordem de Serviço abaixo para gerar a mensagem de envio para o cliente.")

DB_FILE = "financeiro.db"
engine = create_engine(f'sqlite:///{DB_FILE}')

# --- FUNÇÃO PARA ENVIAR EMAIL ---
def enviar_email(destinatario, assunto, corpo_mensagem):
    try:
        remetente = st.secrets["email_credentials"]["username"]
        senha = st.secrets["email_credentials"]["password"]
        msg = EmailMessage()
        msg['Subject'] = assunto
        msg['From'] = remetente
        msg['To'] = destinatario
        msg.set_content(corpo_mensagem)
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(remetente, senha)
            smtp.send_message(msg)
        st.success("Email enviado com sucesso!")
        return True
    except Exception as e:
        st.error(f"Falha ao enviar o email. Erro: {e}")
        st.error("Verifique as credenciais em secrets.toml e sua Senha de App.")
        return False

# --- FUNÇÃO PARA CARREGAR DADOS ---
@st.cache_data
def carregar_dados_completos():
    try:
        entradas_df = pd.read_sql("SELECT rowid as id, * FROM entradas", engine, parse_dates=['data'])
        clientes_df = pd.read_sql("SELECT nome, telefone, email FROM clientes", engine)
        
        clientes_df.rename(columns={'nome': 'cliente'}, inplace=True)
        
        if not entradas_df.empty:
            if 'cliente' in entradas_df.columns:
                merged_df = pd.merge(entradas_df, clientes_df, on='cliente', how='left')
                return merged_df
            else:
                return entradas_df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Ocorreu um erro crítico ao buscar os dados: {e}")
        return pd.DataFrame()

df_os = carregar_dados_completos()

if not df_os.empty and 'ordem_servico' in df_os.columns and not df_os['ordem_servico'].isnull().all():
    df_os_validas = df_os.dropna(subset=['ordem_servico']).copy()

    df_os_validas['display'] = df_os_validas.apply(
        lambda row: f"O.S. {row['ordem_servico']} - {row['cliente']} ({row['data'].strftime('%d/%m/%Y')})",
        axis=1
    )
    
    os_selecionada_display = st.selectbox(
        "Selecione a Ordem de Serviço que deseja enviar:",
        options=[""] + df_os_validas['display'].tolist()
    )

    if os_selecionada_display:
        os_details = df_os_validas[df_os_validas['display'] == os_selecionada_display].iloc[0]

        st.markdown("---")
        st.subheader("Resumo da Ordem de Serviço")

        # --- NOVA MENSAGEM PERSONALIZADA ---
        
        # Pega as variáveis para usar na mensagem
        cliente_nome = os_details.get('cliente', 'Cliente')
        dia_servico = os_details.get('data', pd.Timestamp.now()).strftime('%d/%m/%Y')
        hora_servico = os_details.get('data', pd.Timestamp.now()).strftime('%H:%M')
        os_numero = os_details.get('ordem_servico', 'N/A')
        servico_realizado = os_details.get('descricao_servico', 'Serviço não detalhado.')
        valor_formatado = f"R$ {os_details.get('valor_atendimento', 0):.2f}".replace('.', ',')

        # Monta a nova mensagem
        mensagem = f"""Prezado(a) {cliente_nome},

Segue um resumo da sua Ordem de Serviço realizado dia {dia_servico} às {hora_servico}.

Qualquer duvida estou a disposição.

- *O.S. Nº:* {os_numero}
- *Data:* {dia_servico}
- *Serviço Realizado:* {servico_realizado}

- *Valor Total:* {valor_formatado}
"""
        st.text_area("Prévia da Mensagem:", value=mensagem, height=250)
        
        st.markdown("---")
        st.subheader("Opções de Envio")

        telefone = os_details.get('telefone')
        if telefone and pd.notnull(telefone):
            numero_limpo = re.sub(r'\D', '', str(telefone))
            if not numero_limpo.startswith('55'):
                numero_limpo = '55' + numero_limpo
            mensagem_url = quote(mensagem)
            link_whatsapp = f"https://wa.me/{numero_limpo}?text={mensagem_url}"
            st.link_button("📲 Enviar via WhatsApp", url=link_whatsapp, use_container_width=True)
        else:
            st.warning(f"O cliente {os_details.get('cliente')} não possui um número de telefone cadastrado.")

        with st.expander("✉️ Enviar via Email", expanded=True):
            email = os_details.get('email')
            if email and pd.notnull(email):
                st.write(f"O email será enviado para: **{email}**")
                assunto_email = f"Relatório de Atendimento - O.S. {os_details.get('ordem_servico')}"
                if st.button("Enviar Email Agora", use_container_width=True, type="primary", key="btn_enviar_email"):
                    with st.spinner("Enviando email..."):
                        enviar_email(destinatario=email, assunto=assunto_email, corpo_mensagem=mensagem)
            else:
                st.warning(f"O cliente {os_details.get('cliente')} não possui um email cadastrado para envio.")
else:
    st.info("Nenhuma Ordem de Serviço válida foi encontrada nos lançamentos de entrada.")