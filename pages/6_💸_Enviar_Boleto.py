import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
from email.message import EmailMessage
import re
from urllib.parse import quote
import smtplib
from datetime import datetime, timedelta

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
import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from menu import exibir_menu
exibir_menu()

# --- CONFIGURAÇÃO DA PÁGINA E CONEXÃO COM DB ---
st.set_page_config(page_title="Enviar Boleto", page_icon="💸", layout="wide")
st.title("💸 Enviar Boleto Bancário")
st.markdown("Envie boletos de cobrança para seus clientes via E-mail e WhatsApp.")

# Conexão com o banco de dados
connection_url = st.secrets["database"]["connection_url"]
engine = create_engine(connection_url)

# --- FUNÇÕES AUXILIARES ---

@st.cache_data
def carregar_clientes():
    """Carrega os clientes do banco de dados para o selectbox."""
    try:
        clientes_df = pd.read_sql_query(
            "SELECT nome, email, telefone FROM clientes ORDER BY nome",
            engine
        )
        return clientes_df
    except Exception as e:
        st.error(f"Erro ao carregar clientes: {e}")
        return pd.DataFrame(columns=['nome', 'email'])

def enviar_email_com_anexos(destinatario, assunto, corpo, lista_anexos):
    """Envia um email com múltiplos anexos em PDF."""
    try:
        remetente = st.secrets["email_credentials"]["username"]
        senha = st.secrets["email_credentials"]["password"]
        
        msg = EmailMessage()
        msg['Subject'] = assunto
        msg['From'] = remetente
        msg['To'] = destinatario
        msg.set_content(corpo)
        
        corpo_html = corpo.replace('\n', '<br>')
        html_content = f"""\
        <html>
            <body style="font-family: Arial, sans-serif; color: #333333; line-height: 1.6;">
                <p>{corpo_html}</p>
                <br>
                <table border="0" cellpadding="0" cellspacing="0" style="font-family: Arial, sans-serif; color: #333333; line-height: 1.4;">
                    <tr>
                        <td style="padding-right: 15px; border-right: 2px solid #cccccc;">
                            <a href='https://postimg.cc/fVNyZqpf' target='_blank'>
                                <img src='https://i.postimg.cc/fVNyZqpf/Whats-App-Image-2025-01-06-at-16-03-50.jpg' border='0' alt='Elite CNC Service' style='max-width: 140px; height: auto;'>
                            </a>
                        </td>
                        <td style="padding-left: 15px;">
                            <strong style="font-size: 16px;">Filipe Guimarães</strong><br>
                            <span style="font-size: 14px; color: #666666;">Sócio Proprietário</span><br>
                            <span style="font-size: 13px;">
                            📞 WhatsApp: (11) 97761-7009<br>
                            ✉️ elitecncservice@gmail.com<br>
                            🌐 <a href="http://www.elitecncservice.com.br" style="color: #0056b3; text-decoration: none;">www.elitecncservice.com.br</a>
                            </span>
                        </td>
                    </tr>
                </table>
            </body>
        </html>
        """
        msg.add_alternative(html_content, subtype='html')
        
        # Adiciona os anexos
        for anexo in lista_anexos:
            msg.add_attachment(anexo['dados'], maintype='application', subtype='pdf', filename=anexo['nome'])
        
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(remetente, senha)
            smtp.send_message(msg)
            
        st.success(f"Email com boleto(s) enviado para {destinatario} com sucesso!")
        return True
    except Exception as e:
        st.error(f"Erro ao enviar email: {e}")
        st.error("Verifique as credenciais em secrets.toml e sua Senha de App.")
        return False

def get_sugestao_mes_anterior():
    """Retorna uma string com o Mês/Ano anterior ao atual (ex: Janeiro/2024)."""
    hoje = datetime.now()
    primeiro_deste_mes = hoje.replace(day=1)
    mes_passado = primeiro_deste_mes - timedelta(days=1)
    nomes_meses = {1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril', 5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto', 9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'}
    return f"{nomes_meses[mes_passado.month]}/{mes_passado.year}"

# --- INTERFACE PRINCIPAL ---

df_clientes = carregar_clientes()
lista_clientes_nomes = [""] + df_clientes['nome'].tolist() if not df_clientes.empty else []

if not lista_clientes_nomes:
    st.warning("Nenhum cliente cadastrado. Cadastre um cliente na página '⭐ Clientes' primeiro.")
else:
    col_left, col_right = st.columns([1, 1.2], gap="large")

    # --- COLUNA DA ESQUERDA: DADOS E UPLOAD ---
    with col_left:
        with st.container(border=True):
            st.subheader("1. Dados do Envio")
            cliente_selecionado = st.selectbox("Selecione o Cliente:", options=lista_clientes_nomes)
            
            sugestao_mes = get_sugestao_mes_anterior()
            mes_referencia = st.text_input("Mês/Ano de Referência", value=sugestao_mes, placeholder="Ex: Janeiro/2024")

            uploaded_files = st.file_uploader("Anexe o(s) Boleto(s) (PDF)", type="pdf", accept_multiple_files=True)

            if cliente_selecionado:
                dados_cliente = df_clientes[df_clientes['nome'] == cliente_selecionado].iloc[0]
                email_cliente = dados_cliente.get('email')
                telefone_cliente = dados_cliente.get('telefone')
                
                st.info(
                    f"**Conferência de Contato:**\n\n"
                    f"📧 Email: `{email_cliente if email_cliente else 'Não cadastrado'}`\n\n"
                    f"📱 Telefone: `{telefone_cliente if telefone_cliente else 'Não cadastrado'}`"
                )
                if not email_cliente:
                    st.error("⚠️ Este cliente não possui e-mail cadastrado. Atualize o cadastro em 'Clientes'.")

    # --- COLUNA DA DIREITA: PRÉVIA E AÇÕES ---
    with col_right:
        if cliente_selecionado and mes_referencia and uploaded_files and email_cliente:
            with st.container(border=True):
                st.subheader("2. Prévia e Envio")
                
                # Configuração do Email
                assunto_padrao = f"Boleto Bancário - {cliente_selecionado} - Ref. {mes_referencia}"
                corpo_padrao = f"""Prezado(a) {cliente_selecionado},

Segue em anexo os boletos referente ao fechamento de {mes_referencia}.

Qualquer dúvida, estamos à disposição.

Atenciosamente,
"""
                st.markdown("##### 📧 Configuração do Email")
                assunto = st.text_input("Assunto:", value=assunto_padrao)
                corpo_email = st.text_area("Mensagem:", value=corpo_padrao, height=150)

                st.markdown("---")
                st.markdown("##### 🚀 Ações")
                
                c_act1, c_act2 = st.columns(2)
                
                with c_act1:
                    # --- Botão WhatsApp ---
                    if telefone_cliente and pd.notnull(telefone_cliente):
                        numero_limpo = re.sub(r'\D', '', str(telefone_cliente))
                        if not numero_limpo.startswith('55'):
                            numero_limpo = '55' + numero_limpo
                        
                        mensagem_whatsapp = f"Olá {cliente_selecionado}, tudo bem?\n\nEstou enviando os boletos referentes a *{mes_referencia}* para o seu e-mail.\n\nPor favor, verifique sua caixa de entrada."
                        mensagem_url = quote(mensagem_whatsapp)
                        link_whatsapp = f"https://wa.me/{numero_limpo}?text={mensagem_url}"
                        st.markdown(
                            f'<a href="{link_whatsapp}" target="_blank" style="display: inline-block; text-align: center; width: 100%; padding: 0.5rem; background-color: #fafafa; color: #262730; border: 1px solid rgba(49, 51, 63, 0.2); border-radius: 0.5rem; text-decoration: none;">📲 Notificar via WhatsApp</a>',
                            unsafe_allow_html=True
                        )
                    else:
                        st.button("📲 Notificar via WhatsApp", disabled=True, use_container_width=True)
                        st.caption("Sem telefone.")

                with c_act2:
                    # --- Botão Email ---
                    if st.button(f"✉️ Enviar Email", type="primary", use_container_width=True):
                        lista_anexos = [{'nome': f.name, 'dados': f.getvalue()} for f in uploaded_files]
                        enviar_email_com_anexos(email_cliente, assunto, corpo_email, lista_anexos)
        elif not uploaded_files:
            st.info("👈 Selecione um cliente e anexe o(s) Boleto(s) para habilitar o envio.")