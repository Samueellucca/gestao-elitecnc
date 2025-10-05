import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
from fpdf import FPDF
from datetime import datetime, date
import smtplib
from email.message import EmailMessage
from pypdf import PdfWriter
import io

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
st.set_page_config(page_title="Compilar Relatórios", page_icon="📦", layout="centered")
st.title("📦 Compilar Relatórios de O.S.")
st.write("Selecione um cliente e um período para juntar múltiplos relatórios de serviço em um único PDF.")

connection_url = st.secrets["database"]["connection_url"]
engine = create_engine(connection_url)

# --- CLASSE PARA GERAR O PDF INDIVIDUAL (Reutilizada de Gerar_Relatório_PDF.py) ---
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
            self.set_xy(10, 8); self.set_font('Arial', 'B', 12); self.cell(50, 10, 'Logo N/A', 0, 1, 'L')
        self.set_font('DejaVu', '', 9); self.set_y(8); self.set_x(-105)
        self.cell(100, 5, empresa_razao_social, 0, 1, 'R'); self.set_x(-105)
        self.cell(100, 5, empresa_cnpj, 0, 1, 'R'); self.set_x(-105)
        self.cell(100, 5, empresa_endereco, 0, 1, 'R'); self.set_x(-105)
        self.cell(100, 5, empresa_contato, 0, 1, 'R'); self.set_x(-105)
        self.cell(100, 5, empresa_site, 0, 1, 'R')
        self.set_y(35); self.set_line_width(0.5); self.line(10, self.get_y(), 200, self.get_y())
        self.ln(3); self.set_font('DejaVu', 'B', 16); self.cell(0, 10, 'RELATÓRIO DE SERVIÇOS', 0, 1, 'C'); self.ln(8)

    def footer(self):
        self.set_y(-15); self.set_font('DejaVu', 'I', 8); self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

# --- FUNÇÕES AUXILIARES ---

@st.cache_data
def carregar_clientes_e_dados():
    try:
        clientes_df = pd.read_sql_query("SELECT nome, telefone, email, endereco FROM clientes ORDER BY nome", engine)
        return clientes_df
    except Exception as e:
        st.error(f"Erro ao carregar clientes: {e}"); return pd.DataFrame()

def buscar_servicos_completos_cliente(cliente, data_inicio, data_fim):
    query = f"""
    SELECT e.*, c.telefone, c.email as email_cliente, c.endereco
    FROM entradas e
    LEFT JOIN clientes c ON e.cliente = c.nome
    WHERE e.cliente = '{cliente}' AND date(e.data) BETWEEN '{data_inicio}' AND '{data_fim}'
    ORDER BY e.data ASC
    """
    return pd.read_sql_query(query, engine, parse_dates=['data'])

def gerar_pdf_os(os_details):
    """Gera um PDF para uma única Ordem de Serviço e retorna os bytes."""
    pdf = PDF()
    try:
        pdf.add_font('DejaVu', '', 'DejaVuSans.ttf')
        pdf.add_font('DejaVu', 'B', 'DejaVuSans-Bold.ttf')
        pdf.add_font('DejaVu', 'I', 'DejaVuSans-Oblique.ttf')
    except RuntimeError:
        pass # Fonte não encontrada, FPDF usará a padrão.

    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    y_inicial_colunas = pdf.get_y()
    pdf.set_font('DejaVu', 'B', 12); pdf.cell(95, 8, 'DADOS DO CLIENTE', 'B', 1, 'L'); pdf.ln(2)
    pdf.set_font('DejaVu', '', 10)
    pdf.multi_cell(95, 6, f"Nome: {os_details.get('cliente', 'N/A')}\n"
                         f"Telefone: {os_details.get('telefone', 'N/A')}\n"
                         f"Endereço: {os_details.get('endereco', 'N/A')}")

    y_final_coluna_esquerda = pdf.get_y()
    pdf.set_y(y_inicial_colunas); pdf.set_x(105)
    pdf.set_font('DejaVu', 'B', 12); pdf.cell(95, 8, 'DADOS DO SERVIÇO', 'B', 1, 'L'); pdf.ln(2)
    pdf.set_x(105); pdf.set_font('DejaVu', '', 10)

    detalhes_servico = [
        f"Nº da O.S.: {os_details.get('ordem_servico', 'N/A')}",
        f"Data: {os_details['data'].strftime('%d/%m/%Y') if pd.notnull(os_details.get('data')) else 'N/A'}",
    ]
    if os_details.get('maquina') and pd.notnull(os_details.get('maquina')): detalhes_servico.append(f"Máquina: {os_details.get('maquina')}")
    if os_details.get('patrimonio') and pd.notnull(os_details.get('patrimonio')): detalhes_servico.append(f"Patrimônio: {os_details.get('patrimonio')}")
    detalhes_servico.extend([
        f"Técnicos: {os_details.get('qtd_tecnicos', 1)}",
        f"Início: {os_details.get('hora_inicio', 'N/A')}",
        f"Fim: {os_details.get('hora_fim', 'N/A')}"
    ])
    pdf.multi_cell(95, 6, "\n".join(detalhes_servico))

    y_final_coluna_direita = pdf.get_y()
    pdf.set_y(max(y_final_coluna_esquerda, y_final_coluna_direita) + 5)
    pdf.set_font('DejaVu', 'B', 12); pdf.cell(0, 8, 'DESCRIÇÃO DOS SERVIÇOS REALIZADOS', 'B', 1, 'L'); pdf.ln(2)
    pdf.set_font('DejaVu', '', 10); pdf.multi_cell(0, 6, os_details.get('descricao_servico', 'Nenhuma descrição fornecida.'))
    pdf.ln(10)
    pdf.set_font('DejaVu', 'B', 12); pdf.cell(0, 8, 'VALORES', 'B', 1, 'L'); pdf.ln(2)
    pdf.set_font('DejaVu', 'B', 10); pdf.cell(150, 7, 'Descrição', 1, 0, 'C'); pdf.cell(40, 7, 'Valor', 1, 1, 'C')
    pdf.set_font('DejaVu', '', 10)
    valores = {
        "Horas Técnicas Normais": os_details.get('horas_tecnicas', 0), "Horas Técnicas 50%": os_details.get('horas_tecnicas_50', 0),
        "Horas Técnicas 100%": os_details.get('horas_tecnicas_100', 0), "Valor de Deslocamento": os_details.get('valor_deslocamento_total', 0),
        "Deslocamento (KM)": os_details.get('km', 0), "Refeição": os_details.get('refeicao', 0),
        "Peças": os_details.get('pecas', 0), "Pedágio": os_details.get('pedagio', 0),
        "Valor Laboratório": os_details.get('valor_laboratorio', 0)
    }
    for descricao, valor in valores.items():
        if isinstance(valor, (int, float)) and valor > 0:
            pdf.cell(150, 7, f"   {descricao}", 'LR', 0); pdf.cell(40, 7, f"R$ {valor:.2f}".replace('.', ','), 'LR', 1, 'R')
    pdf.set_font('DejaVu', 'B', 11)
    pdf.cell(150, 8, 'VALOR TOTAL', 1, 0, 'R'); pdf.cell(40, 8, f"R$ {os_details.get('valor_atendimento', 0):.2f}".replace('.', ','), 1, 1, 'R')

    return pdf.output()

def enviar_email_com_anexos(destinatario, assunto, corpo, anexos):
    """Envia um email com um ou mais anexos em PDF."""
    try:
        remetente = st.secrets["email_credentials"]["username"]
        senha = st.secrets["email_credentials"]["password"]
        msg = EmailMessage()
        msg['Subject'], msg['From'], msg['To'] = assunto, remetente, destinatario
        msg.set_content(corpo)

        # Adiciona múltiplos anexos
        for anexo in anexos:
            msg.add_attachment(anexo['data'], maintype='application', subtype='pdf', filename=anexo['name'])

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(remetente, senha)
            smtp.send_message(msg)
        st.success(f"Email com relatórios compilados enviado para {destinatario} com sucesso!")
    except Exception as e:
        st.error(f"Erro ao enviar email: {e}")

# --- INTERFACE PRINCIPAL ---

df_clientes = carregar_clientes_e_dados()
lista_clientes_nomes = [""] + df_clientes['nome'].tolist() if not df_clientes.empty else []

if not lista_clientes_nomes:
    st.warning("Nenhum cliente cadastrado. Cadastre um cliente na página '⭐ Clientes' primeiro.")
else:
    col1, col2, col3 = st.columns(3)
    with col1:
        cliente_selecionado = st.selectbox("Selecione o Cliente:", options=lista_clientes_nomes)
    with col2:
        data_inicio_default = datetime.now().replace(day=1)
        data_inicio = st.date_input("Data Inicial", value=data_inicio_default)
    with col3:
        data_fim = st.date_input("Data Final", value=date.today())

    if cliente_selecionado:
        servicos_df = buscar_servicos_completos_cliente(cliente_selecionado, data_inicio, data_fim)

        if servicos_df.empty:
            st.info(f"Nenhum serviço encontrado para '{cliente_selecionado}' no período selecionado.")
        else:
            st.markdown("---")
            st.subheader(f"Relatórios a serem compilados ({len(servicos_df)})")
            st.dataframe(
                servicos_df[['data', 'ordem_servico', 'descricao_servico', 'valor_atendimento']],
                use_container_width=True, hide_index=True
            )

            if st.button(f"📦 Gerar PDF Compilado com {len(servicos_df)} Relatório(s)", type="primary", use_container_width=True):
                with st.spinner("Gerando e unindo os relatórios em PDF... Por favor, aguarde."):
                    merger = PdfWriter()
                    
                    # Gera um PDF para cada O.S. e adiciona ao 'merger'
                    for _, os_details in servicos_df.iterrows():
                        pdf_bytes = gerar_pdf_os(os_details)
                        pdf_stream = io.BytesIO(pdf_bytes)
                        merger.append(pdf_stream)

                    # Salva o PDF final mesclado em um stream de bytes
                    output_stream = io.BytesIO()
                    merger.write(output_stream)
                    merger.close()
                    
                    pdf_final_bytes = output_stream.getvalue()

                    # Salva no session_state para os botões de ação
                    st.session_state.pdf_compilado_bytes = pdf_final_bytes
                    st.session_state.nome_arquivo_compilado = f"Relatorios_{cliente_selecionado.replace(' ', '_')}_{data_inicio.strftime('%Y%m%d')}-{data_fim.strftime('%Y%m%d')}.pdf"
                    st.session_state.email_cliente_compilado = servicos_df.iloc[0]['email_cliente']
                    st.session_state.cliente_selecionado_compilado = cliente_selecionado

    # Botões de Ação (aparecem após gerar o PDF)
    if 'pdf_compilado_bytes' in st.session_state:
        st.markdown("---")
        st.subheader("Anexar Arquivos Adicionais")
        uploaded_files = st.file_uploader(
            "Selecione um ou mais arquivos PDF para enviar junto (ex: Nota Fiscal)",
            type="pdf",
            accept_multiple_files=True
        )

        st.subheader("Ações do PDF Compilado")
        col_acao1, col_acao2 = st.columns(2)

        with col_acao1:
            st.download_button(
                label="📥 Baixar PDF Compilado",
                data=st.session_state.pdf_compilado_bytes,
                file_name=st.session_state.nome_arquivo_compilado,
                mime="application/pdf",
                use_container_width=True
            )

        with col_acao2:
            email_cliente = st.session_state.get('email_cliente_compilado')
            if email_cliente and pd.notnull(email_cliente):
                if st.button(f"✉️ Enviar para {email_cliente}", use_container_width=True):
                    assunto = f"Relatórios de Serviço Compilados - {st.session_state.cliente_selecionado_compilado}"
                    corpo = (
                        f"Prezado(a) {st.session_state.cliente_selecionado_compilado},\n\n"
                        f"Conforme solicitado, segue em anexo o arquivo PDF consolidado com todas as Ordens de Serviço (O.S.) relacionadas ao período de "
                        f"{data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}.\n\n"
                        "Este documento reúne os detalhes de cada atendimento realizado para sua referência e controle.\n\n"
                        "Caso tenha qualquer dúvida ou necessite de esclarecimentos adicionais, permanecemos à sua inteira disposição.\n\n"
                        "Atenciosamente,\n\n"
                        "Filipe Guimarães\n"
                        "Sócio Proprietário\n"
                        "WhatsApp: (11) 97761-7009\n"
                        "elitecncservice@gmail.com\n"
                        "http://www.elitecncservice.com.br"
                    )

                    # Prepara a lista de anexos
                    anexos_para_envio = [{
                        'data': st.session_state.pdf_compilado_bytes,
                        'name': st.session_state.nome_arquivo_compilado
                    }]

                    # Adiciona os arquivos extras que o usuário subiu
                    if uploaded_files:
                        for uploaded_file in uploaded_files:
                            anexos_para_envio.append({
                                'data': uploaded_file.getvalue(),
                                'name': uploaded_file.name
                            })

                    enviar_email_com_anexos(email_cliente, assunto, corpo, anexos_para_envio)

            else:
                st.button("✉️ Enviar por Email", disabled=True, use_container_width=True)
                st.caption("Cliente sem email cadastrado.")
