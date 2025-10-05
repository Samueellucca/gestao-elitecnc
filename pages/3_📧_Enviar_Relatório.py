import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
import pandas as pd
from sqlalchemy import create_engine
from urllib.parse import quote
import re
import smtplib
from email.message import EmailMessage

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
authenticator = None  # só para manter compatibilidade se precisar do logout
st.sidebar.image("logo.png", width=150)
st.sidebar.button("Sair", on_click=lambda: st.session_state.update({"authentication_status": None}))
    

st.set_page_config(page_title="Enviar Relatório", page_icon="📧", layout="centered")
st.title("📧 Enviar Relatório de O.S.")
st.write("Selecione uma Ordem de Serviço abaixo para gerar a mensagem de envio para o cliente.")

# Conexão com o banco de dados da nuvem a partir dos "Secrets"
connection_url = st.secrets["database"]["connection_url"]
engine = create_engine(connection_url)

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

@st.cache_data
def carregar_os_e_clientes():
    try:
        # CORREÇÃO: Voltamos a usar "e.rowid as id"
        query = """
         SELECT 
            e.id as id, 
            e.ordem_servico, 
            e.cliente, 
            e.data,
            e.descricao_servico,
            e.valor_atendimento,
            e.patrimonio,
            e.maquina,
            c.telefone,
            c.email
        FROM entradas e
        LEFT JOIN clientes c ON e.cliente = c.nome
        ORDER BY e.data DESC
        """
        df = pd.read_sql_query(query, engine, parse_dates=['data'])
        return df
    except Exception as e:
        st.error(f"Ocorreu um erro ao buscar os dados: {e}")
        return pd.DataFrame()

df_os = carregar_os_e_clientes()

if not df_os.empty:
    df_os['display'] = df_os.apply(
        lambda row: f"O.S. {row['ordem_servico']} - {row['cliente']} ({(row['data'].strftime('%d/%m/%Y') if pd.notnull(row['data']) else 'Data N/A')})",
        axis=1
    )
    
    os_selecionada_display = st.selectbox(
        "Selecione a Ordem de Serviço que deseja enviar:",
        options=[""] + df_os['display'].tolist()
    )

    if os_selecionada_display:
        os_details = df_os[df_os['display'] == os_selecionada_display].iloc[0]

        st.markdown("---")
        st.subheader("Resumo da Ordem de Serviço")

        valor_formatado = f"R$ {os_details.get('valor_atendimento', 0):.2f}".replace('.', ',')
        data_formatada = os_details['data'].strftime('%d/%m/%Y') if pd.notnull(os_details['data']) else 'N/A'
        hora_formatada = os_details['data'].strftime('%H:%M') if pd.notnull(os_details['data']) else 'N/A'

        # BLOCO NOVO E CORRIGIDO
        
        # Monta a lista de detalhes do serviço dinamicamente
        detalhes_servico = []
        detalhes_servico.append(f"- *O.S. Nº:* {os_details.get('ordem_servico')}")
        detalhes_servico.append(f"- *Data:* {data_formatada}")

        # Adiciona máquina e patrimônio apenas se existirem
        if os_details.get('maquina') and pd.notnull(os_details.get('maquina')):
            detalhes_servico.append(f"- *Máquina:* {os_details.get('maquina')}")
        if os_details.get('patrimonio') and pd.notnull(os_details.get('patrimonio')):
            detalhes_servico.append(f"- *Patrimônio:* {os_details.get('patrimonio')}")
        
        detalhes_servico.append(f"- *Serviço Realizado:* {os_details.get('descricao_servico')}")
        detalhes_servico.append(f"\n- *Valor Total:* {valor_formatado}")

        # Junta as linhas em um único texto
        corpo_detalhes = "\n".join(detalhes_servico)

        mensagem = f"""Prezado(a) {os_details.get('cliente')},

Segue um resumo da sua Ordem de Serviço realizado dia {data_formatada} às {hora_formatada}.

Qualquer duvida estou a disposição.


- *O.S. Nº:* {os_details.get('ordem_servico')}
- *Data:* {data_formatada}
- *Máquina:* {os_details.get('maquina', 'N/A')}
- *Patrimônio:* {os_details.get('patrimonio', 'N/A')}
- *Serviço Realizado:* {os_details.get('descricao_servico')}

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