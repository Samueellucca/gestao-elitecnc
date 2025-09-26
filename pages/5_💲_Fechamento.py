import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
from fpdf import FPDF
from datetime import datetime, date

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Fechamento Mensal", page_icon="💲", layout="centered")
st.title("💲 Relatório de Fechamento por Cliente")

DB_FILE = "financeiro.db"
engine = create_engine(f'sqlite:///{DB_FILE}')

# --- CLASSE PARA GERAR O PDF (reutilizada da página 4) ---
class PDF(FPDF):
    def header(self):
        empresa_razao_social = "Elite CNC Service"
        empresa_cnpj = "CNPJ: 61.159.425/0001-32"
        empresa_endereco = "Rua da Paz, 230 - Santa Rita - Monte Alto SP"
        empresa_contato = "Tel: (11) 97761-7009 | Email: elitecncservice@gmail.com"
        empresa_site = "www.elitecncservice.com.br"
        try:
            self.image('logo.png', 10, 8, 50)
        except FileNotFoundError:
            self.set_xy(10, 8); self.set_font('Arial', 'B', 12); self.cell(50, 10, 'Logo N/A', 0, 1, 'L')
        self.set_font('DejaVu', '', 9); self.set_y(8); self.set_x(-105)
        self.cell(100, 5, empresa_razao_social, 0, 1, 'R'); self.set_x(-105)
        self.cell(100, 5, empresa_cnpj, 0, 1, 'R'); self.set_x(-105)
        self.cell(100, 5, empresa_endereco, 0, 1, 'R'); self.set_x(-105)
        self.cell(100, 5, empresa_contato, 0, 1, 'R'); self.set_x(-105)
        self.cell(100, 5, empresa_site, 0, 1, 'R')
        self.set_y(35); self.set_line_width(0.5); self.line(10, self.get_y(), 200, self.get_y())
        self.ln(3); self.set_font('DejaVu', 'B', 16); self.cell(0, 10, 'RELATÓRIO DE FECHAMENTO', 0, 1, 'C'); self.ln(5)

    def footer(self):
        self.set_y(-15); self.set_font('DejaVu', 'I', 8); self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

# --- FUNÇÕES DE DADOS ---
@st.cache_data
def carregar_clientes():
    try:
        return pd.read_sql_query("SELECT nome FROM clientes ORDER BY nome", engine)['nome'].tolist()
    except:
        return []

def buscar_servicos_cliente(cliente, data_inicio, data_fim):
    try:
        query = f"""
        SELECT data, ordem_servico, maquina, valor_atendimento
        FROM entradas
        WHERE cliente = '{cliente}' AND date(data) BETWEEN '{data_inicio}' AND '{data_fim}'
        ORDER BY data ASC
        """
        return pd.read_sql_query(query, engine, parse_dates=['data'])
    except Exception as e:
        st.error(f"Erro ao buscar serviços: {e}")
        return pd.DataFrame()

# --- INTERFACE DO STREAMLIT ---
lista_clientes = carregar_clientes()

if not lista_clientes:
    st.warning("Nenhum cliente cadastrado. Por favor, cadastre um cliente na página 'Clientes'.")
else:
    col1, col2, col3 = st.columns(3)
    with col1:
        cliente_selecionado = st.selectbox("Selecione o Cliente:", options=lista_clientes)
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
                st.warning(f"Nenhum serviço encontrado para o cliente '{cliente_selecionado}' no período selecionado.")
            else:
                with st.spinner("Gerando PDF..."):
                    pdf = PDF()
                    try:
                        pdf.add_font('DejaVu', '', 'DejaVuSans.ttf'); pdf.add_font('DejaVu', 'B', 'DejaVuSans-Bold.ttf'); pdf.add_font('DejaVu', 'I', 'DejaVuSans-Oblique.ttf')
                    except FileNotFoundError: st.error("Arquivos de fonte (DejaVu) não encontrados.")
                    
                    pdf.add_page()
                    pdf.set_auto_page_break(auto=True, margin=15)
                    
                    # Seção de informações
                    pdf.set_font('DejaVu', 'B', 12)
                    pdf.cell(95, 8, 'DADOS DO CLIENTE', 'B', 1, 'L')
                    pdf.ln(2); pdf.set_font('DejaVu', '', 10)
                    pdf.multi_cell(95, 6, f"Nome: {cliente_selecionado}")
                    
                    pdf.set_y(pdf.get_y() - 16) # Volta para alinhar as colunas
                    pdf.set_x(105); pdf.set_font('DejaVu', 'B', 12)
                    pdf.cell(95, 8, 'PERÍODO REFERENTE', 'B', 1, 'L')
                    pdf.ln(2); pdf.set_x(105); pdf.set_font('DejaVu', '', 10)
                    pdf.multi_cell(95, 6, f"Data Inicial: {data_inicio.strftime('%d/%m/%Y')}\n"
                                         f"Data Final: {data_fim.strftime('%d/%m/%Y')}")
                    pdf.ln(10)
                    
                    # Tabela de serviços
                    pdf.set_font('DejaVu', 'B', 12)
                    pdf.cell(0, 8, 'SERVIÇOS REALIZADOS NO PERÍODO', 'B', 1, 'L')
                    pdf.ln(2)
                    
                    # Cabeçalho da tabela
                    pdf.set_font('DejaVu', 'B', 10)
                    pdf.cell(30, 7, 'Data', 1, 0, 'C')
                    pdf.cell(50, 7, 'Nº O.S.', 1, 0, 'C')
                    pdf.cell(70, 7, 'Máquina', 1, 0, 'C')
                    pdf.cell(40, 7, 'Valor Total', 1, 1, 'C')

                    # Corpo da tabela
                    pdf.set_font('DejaVu', '', 10)
                    total_a_pagar = 0
                    for index, row in servicos_df.iterrows():
                        pdf.cell(30, 7, row['data'].strftime('%d/%m/%Y'), 1, 0, 'C')
                        pdf.cell(50, 7, str(row['ordem_servico']), 1, 0, 'C')
                        pdf.cell(70, 7, str(row['maquina']), 1, 0, 'C')
                        pdf.cell(40, 7, f"R$ {row['valor_atendimento']:.2f}".replace('.',','), 1, 1, 'R')
                        total_a_pagar += row['valor_atendimento']

                    # Linha de Total
                    pdf.set_font('DejaVu', 'B', 11)
                    pdf.cell(150, 8, 'VALOR TOTAL A PAGAR', 1, 0, 'R')
                    pdf.cell(40, 8, f"R$ {total_a_pagar:.2f}".replace('.',','), 1, 1, 'R')
                    
                    pdf_bytes = bytes(pdf.output())
                    nome_arquivo = f"Fechamento_{cliente_selecionado}_{data_inicio.strftime('%Y%m%d')}-{data_fim.strftime('%Y%m%d')}.pdf"
                    
                    st.download_button(
                        label="✅ PDF Gerado! Clique para baixar.",
                        data=pdf_bytes,
                        file_name=nome_arquivo,
                        mime="application/pdf",
                        use_container_width=True
                    )