import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
import pandas as pd
from sqlalchemy import create_engine
from fpdf import FPDF
from datetime import datetime, date
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
authenticator = None
st.sidebar.button("Sair", on_click=lambda: st.session_state.update({"authentication_status": None}))

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Fechamento Mensal", page_icon="💲", layout="centered")
st.title("💲 Relatório de Fechamento por Cliente")

# Conexão com o banco de dados
connection_url = st.secrets["database"]["connection_url"]
engine = create_engine(connection_url)

# --- CLASSE PDF ---
class PDF(FPDF):
    def header(self):
        empresa_razao_social = "Elite CNC Service"
        empresa_cnpj = "CNPJ: 61.159.425/0001-32"
        empresa_endereco = "Rua da Paz, 230 - Santa Rita - Monte Alto SP"
        empresa_contato = "Tel: (11) 97761-7009 | Email: elitecncservice@gmail.com"
        empresa_site = "www.elitecncservice.com.br"
        try:
            self.image('logo.png', 10, 1, 50)
        except FileNotFoundError:
            self.set_xy(10, 8)
            self.set_font('Arial', 'B', 12)
            self.cell(50, 10, 'Logo N/A', 0, 1, 'L')
        self.set_font('DejaVu', '', 9)
        self.set_y(8); self.set_x(-105)
        self.cell(100, 5, empresa_razao_social, 0, 1, 'R'); self.set_x(-105)
        self.cell(100, 5, empresa_cnpj, 0, 1, 'R'); self.set_x(-105)
        self.cell(100, 5, empresa_endereco, 0, 1, 'R'); self.set_x(-105)
        self.cell(100, 5, empresa_contato, 0, 1, 'R'); self.set_x(-105)
        self.cell(100, 5, empresa_site, 0, 1, 'R')
        self.set_y(35)
        self.set_line_width(0.5)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(3)
        self.set_font('DejaVu', 'B', 16)
        self.cell(0, 10, 'RELATÓRIO DE FECHAMENTO', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('DejaVu', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

# --- FUNÇÃO EMAIL ---
def enviar_pdf_por_email(destinatario, assunto, corpo, dados_pdf, nome_arquivo_pdf):
    try:
        remetente = st.secrets["email_credentials"]["username"]
        senha = st.secrets["email_credentials"]["password"]
        msg = EmailMessage()
        msg['Subject'], msg['From'], msg['To'] = assunto, remetente, destinatario
        msg.set_content(corpo)
        msg.add_attachment(dados_pdf, maintype='application', subtype='pdf', filename=nome_arquivo_pdf)
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(remetente, senha)
            smtp.send_message(msg)
        st.success(f"Email enviado para {destinatario} com sucesso!")
        return True
    except Exception as e:
        st.error(f"Erro ao enviar email: {e}")
        return False

# --- FUNÇÕES DE DADOS ---
@st.cache_data
def carregar_clientes_e_dados():
    try:
        clientes_df = pd.read_sql_query(
            "SELECT nome, telefone, email FROM clientes ORDER BY nome",
            engine
        )
        return clientes_df
    except:
        return pd.DataFrame()

def buscar_servicos_cliente(cliente, data_inicio, data_fim):
    try:
        query = f"""
        SELECT data, ordem_servico, maquina, patrimonio, valor_atendimento
        FROM entradas
        WHERE cliente = '{cliente}' 
          AND date(data) BETWEEN '{data_inicio}' AND '{data_fim}'
        ORDER BY data ASC
        """
        return pd.read_sql_query(query, engine, parse_dates=['data'])
    except Exception as e:
        st.error(f"Erro ao buscar serviços: {e}")
        return pd.DataFrame()

# --- INTERFACE STREAMLIT ---
df_clientes = carregar_clientes_e_dados()
lista_clientes_nomes = df_clientes['nome'].tolist() if not df_clientes.empty else []

if not lista_clientes_nomes:
    st.warning("Nenhum cliente cadastrado. Cadastre um cliente na página 'Clientes'.")
else:
    col1, col2, col3 = st.columns(3)
    with col1:
        cliente_selecionado = st.selectbox("Selecione o Cliente:", options=lista_clientes_nomes)
    with col2:
        data_inicio = st.date_input("Data Inicial", value=datetime.now().replace(day=1))
    with col3:
        data_fim = st.date_input("Data Final", value=date.today())

    if st.button("Gerar Relatório de Fechamento", type="primary", use_container_width=True):
        if not cliente_selecionado:
            st.error("Por favor, selecione um cliente.")
        else:
            servicos_df = buscar_servicos_cliente(cliente_selecionado, data_inicio, data_fim)
            if servicos_df.empty:
                st.warning(f"Nenhum serviço encontrado para '{cliente_selecionado}' no período.")
            else:
                st.session_state.servicos_df = servicos_df
                st.session_state.cliente_selecionado = cliente_selecionado
                st.session_state.periodo = (data_inicio, data_fim)

# --- EXIBIÇÃO DO RELATÓRIO ---
if 'servicos_df' in st.session_state and not st.session_state.servicos_df.empty:
    servicos_df = st.session_state.servicos_df
    cliente_selecionado = st.session_state.cliente_selecionado
    data_inicio, data_fim = st.session_state.periodo

    st.markdown("---")
    st.subheader("Prévia do Relatório")
    st.dataframe(servicos_df, hide_index=True)
    total_a_pagar = servicos_df['valor_atendimento'].sum()
    st.metric("Valor Total a Pagar", f"R$ {total_a_pagar:,.2f}")
    st.markdown("---")
    st.subheader("Ações do Relatório")

    # --- PDF ---
    pdf = PDF()
    try:
        pdf.add_font('DejaVu', '', 'DejaVuSans.ttf')
        pdf.add_font('DejaVu', 'B', 'DejaVuSans-Bold.ttf')
        pdf.add_font('DejaVu', 'I', 'DejaVuSans-Oblique.ttf')
    except:
        pass

    dados_cliente = df_clientes[df_clientes['nome'] == cliente_selecionado].iloc[0]
    telefone_cliente = dados_cliente.get('telefone')
    email_cliente = dados_cliente.get('email')

    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Blocos de cabeçalho
    pdf.set_font('DejaVu', 'B', 12)
    pdf.cell(95, 8, 'DADOS DO CLIENTE', 'B', 0, 'L')
    pdf.set_x(105)
    pdf.cell(95, 8, 'PERÍODO REFERENTE', 'B', 1, 'L')

    # Cliente
    pdf.set_font('DejaVu', '', 10)
    pdf.set_x(10)
    pdf.multi_cell(
        95, 6,
        f"Nome: {cliente_selecionado}\n"
        f"Telefone: {telefone_cliente if pd.notnull(telefone_cliente) else 'N/A'}\n"
        f"Email: {email_cliente if pd.notnull(email_cliente) else 'N/A'}"
    )

    # Período
    pdf.set_y(35)
    pdf.set_x(105)
    pdf.set_font('DejaVu', '', 10)
    pdf.multi_cell(
        95, 6,
        f"Data Inicial: {data_inicio.strftime('%d/%m/%Y')}\n"
        f"Data Final: {data_fim.strftime('%d/%m/%Y')}"
    )

    # Tabela
    pdf.ln(10)
    pdf.set_font('DejaVu', 'B', 12)
    pdf.cell(0, 8, 'SERVIÇOS REALIZADOS NO PERÍODO', 'B', 1, 'L')
    pdf.ln(2)

    pdf.set_font('DejaVu', 'B', 10)
    pdf.cell(25, 7, 'Data', 1, 0, 'C')
    pdf.cell(25, 7, 'Nº O.S.', 1, 0, 'C')
    pdf.cell(80, 7, 'Máquina', 1, 0, 'C')
    pdf.cell(30, 7, 'Patrimônio', 1, 0, 'C')
    pdf.cell(30, 7, 'Valor Total', 1, 1, 'C')

    pdf.set_font('DejaVu', '', 10)
    for _, row in servicos_df.iterrows():
        pdf.cell(25, 7, row['data'].strftime('%d/%m/%Y'), 1, 0, 'C')
        pdf.cell(25, 7, str(row['ordem_servico']), 1, 0, 'C')
        pdf.cell(80, 7, str(row['maquina']), 1, 0, 'L')
        pdf.cell(30, 7, str(row.get('patrimonio', '')), 1, 0, 'C')
        pdf.cell(30, 7, f"R$ {row['valor_atendimento']:.2f}".replace('.',','), 1, 1, 'R')

    pdf.set_font('DejaVu', 'B', 11)
    pdf.cell(160, 8, 'VALOR TOTAL A PAGAR', 1, 0, 'R')
    pdf.cell(30, 8, f"R$ {total_a_pagar:.2f}".replace('.',','), 1, 1, 'R')

    pdf_bytes = bytes(pdf.output())
    nome_arquivo = f"Fechamento_{cliente_selecionado.replace(' ', '_')}_{data_inicio.strftime('%Y%m%d')}-{data_fim.strftime('%Y%m%d')}.pdf"

    # Botão Download
    st.download_button(
        label="📥 Baixar PDF",
        data=pdf_bytes,
        file_name=nome_arquivo,
        mime="application/pdf",
        use_container_width=True
    )

    # --- WhatsApp e Email ---
    mensagem_envio = f"""Prezado(a) {cliente_selecionado},

Segue em anexo o relatório de fechamento dos serviços prestados entre {data_inicio.strftime('%d/%m/%Y')} e {data_fim.strftime('%d/%m/%Y')}, totalizando {f'R$ {total_a_pagar:,.2f}'.replace('.',',')}.

Qualquer dúvida, estamos à disposição.

Atenciosamente,

Filipe Guimarães
Sócio Proprietário
WhatsApp: (11) 97761-7009
elitecncservice@gmail.com
http://www.elitecncservice.com.br
"""

    col1, col2 = st.columns(2)
    with col1:
        if telefone_cliente and pd.notnull(telefone_cliente):
            numero_limpo = re.sub(r'\D', '', str(telefone_cliente))
            if not numero_limpo.startswith('55'):
                numero_limpo = '55' + numero_limpo
            mensagem_url = quote(mensagem_envio)
            link_whatsapp = f"https://wa.me/{numero_limpo}?text={mensagem_url}"
            st.link_button("📲 Enviar via WhatsApp", url=link_whatsapp, use_container_width=True)
        else:
            st.button("📲 Enviar via WhatsApp", use_container_width=True, disabled=True)
            st.caption("Cliente sem telefone.")

    with col2:
        if email_cliente and pd.notnull(email_cliente):
            if st.button("✉️ Enviar por Email com Anexo", use_container_width=True, type="primary"):
                with st.spinner(f"Enviando para {email_cliente}..."):
                    enviar_pdf_por_email(
                        destinatario=email_cliente,
                        assunto=f"Fechamento de Serviços - {cliente_selecionado}",
                        corpo=mensagem_envio,
                        dados_pdf=pdf_bytes,
                        nome_arquivo_pdf=nome_arquivo
                    )
        else:
            st.button("✉️ Enviar por Email com Anexo", use_container_width=True, disabled=True)
            st.caption("Cliente sem email.")
