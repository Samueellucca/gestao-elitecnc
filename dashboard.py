import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import sqlite3
from sqlalchemy import create_engine

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Dashboard Financeiro",
    page_icon="💰",
    layout="wide"
)

# --- CONSTANTES ---
VALOR_POR_KM = 1.40
VALOR_HORA_TECNICA = 90.00
VALOR_HORA_TECNICA_50 = VALOR_HORA_TECNICA * 1.5
DB_FILE = "financeiro.db"

# --- CONEXÃO COM O BANCO DE DADOS SQLITE ---
engine = create_engine(f'sqlite:///{DB_FILE}')

# --- FUNÇÃO PARA CARREGAR DADOS DO SQLITE ---
@st.cache_data
def carregar_dados():
    try:
        # CORREÇÃO APLICADA AQUI: Adicionado o parse_dates
        entradas_df = pd.read_sql_table('entradas', engine, parse_dates=['data'])
    except ValueError:
        entradas_df = pd.DataFrame(columns=['data', 'ordem_servico', 'valor_atendimento', 'horas_tecnicas', 'horas_tecnicas_50', 'km', 'refeicao', 'pecas'])

    try:
        # CORREÇÃO APLICADA AQUI: Adicionado o parse_dates
        saidas_df = pd.read_sql_table('saidas', engine, parse_dates=['data'])
    except ValueError:
        saidas_df = pd.DataFrame(columns=['data', 'tipo_conta', 'descricao', 'valor'])

    # As linhas de conversão manual abaixo não são mais necessárias,
    # mas não causam problema se permanecerem.
    if not entradas_df.empty:
        entradas_df['data'] = pd.to_datetime(entradas_df['data'])
    if not saidas_df.empty:
        saidas_df['data'] = pd.to_datetime(saidas_df['data'])
    
    return entradas_df, saidas_df

# Carrega os dados
entradas_df, saidas_df = carregar_dados()

# --- BARRA LATERAL (SIDEBAR) PARA NOVOS LANÇAMENTOS ---
st.sidebar.header("Lançar Novos Dados")

# Formulário para lançar ENTRADAS
with st.sidebar.form("form_entradas", clear_on_submit=True):
    st.subheader("Nova Entrada (Ordem de Serviço)")
    data_entrada = st.date_input("Data do Atendimento")
    os_id = st.text_input("Nº da Ordem de Serviço")
    
    st.markdown("---")
    st.write("Componentes para cálculo do valor final:")
    
    valor_fixo = st.number_input("Valor Fixo do Serviço (se houver)", min_value=0.0, format="%.2f")
    qtd_horas_tecnicas = st.number_input(f"Quantidade de Horas Técnicas (R$ {VALOR_HORA_TECNICA:.2f}/h)", min_value=0.0, format="%.2f")
    qtd_horas_tecnicas_50 = st.number_input(f"Quantidade de Horas Técnicas 50% (R$ {VALOR_HORA_TECNICA_50:.2f}/h)", min_value=0.0, format="%.2f")
    qtd_km = st.number_input(f"Quantidade de KM Rodados (R$ {VALOR_POR_KM:.2f}/km)", min_value=0.0, format="%.2f")
    refeicao = st.number_input("Valor da Refeição", min_value=0.0, format="%.2f")
    pecas_entrada = st.number_input("Valor das Peças (Venda)", min_value=0.0, format="%.2f")
    
    submit_entrada = st.form_submit_button("Lançar Entrada")

    if submit_entrada:
        valor_km_final = qtd_km * VALOR_POR_KM
        valor_horas_tecnicas_final = qtd_horas_tecnicas * VALOR_HORA_TECNICA
        valor_horas_tecnicas_50_final = qtd_horas_tecnicas_50 * VALOR_HORA_TECNICA_50

        valor_atendimento_calculado = (
            valor_fixo + valor_horas_tecnicas_final + valor_horas_tecnicas_50_final +
            valor_km_final + refeicao + pecas_entrada
        )

        nova_entrada = pd.DataFrame([{
            'data': pd.to_datetime(data_entrada), 'ordem_servico': os_id, 'valor_atendimento': valor_atendimento_calculado,
            'horas_tecnicas': valor_horas_tecnicas_final, 'horas_tecnicas_50': valor_horas_tecnicas_50_final, 
            'km': valor_km_final, 'refeicao': refeicao, 'pecas': pecas_entrada
        }])
        
        nova_entrada.to_sql('entradas', engine, if_exists='append', index=False)
        st.cache_data.clear()
        st.sidebar.success(f"Entrada de R$ {valor_atendimento_calculado:,.2f} lançada!")

# Formulário para lançar SAÍDAS
with st.sidebar.form("form_saidas", clear_on_submit=True):
    st.subheader("Nova Saída (Despesa)")
    data_saida = st.date_input("Data da Despesa")
    tipo_conta = st.selectbox("Tipo de Conta", ["Fixa", "Variável"])
    descricao_saida = st.text_input("Descrição da Despesa (Ex: Aluguel, Peça XYZ)")
    valor_saida = st.number_input("Valor da Despesa", min_value=0.0, format="%.2f")
    
    submit_saida = st.form_submit_button("Lançar Saída")

    if submit_saida:
        nova_saida = pd.DataFrame([{
            'data': pd.to_datetime(data_saida), 'tipo_conta': tipo_conta, 
            'descricao': descricao_saida, 'valor': valor_saida
        }])
        nova_saida.to_sql('saidas', engine, if_exists='append', index=False)
        st.cache_data.clear()
        st.sidebar.success("Saída lançada com sucesso!")

# --- PAINEL PRINCIPAL ---
st.title("📊 Dashboard Financeiro da Empresa")
st.markdown("---")

if entradas_df.empty and saidas_df.empty:
    st.warning("Nenhum dado lançado ainda. Use a barra lateral para começar.")
    entradas_filtradas = pd.DataFrame()
    saidas_filtradas = pd.DataFrame()
else:
    dates = []
    if not entradas_df.empty:
        dates.append(entradas_df['data'].min().date())
        dates.append(entradas_df['data'].max().date())
    if not saidas_df.empty:
        dates.append(saidas_df['data'].min().date())
        dates.append(saidas_df['data'].max().date())
    
    if dates:
        min_date = min(dates)
        max_date = max(dates)
        
        start_date, end_date = st.date_input(
            "Filtre por período:",
            [min_date, max_date],
            min_value=min_date,
            max_value=max_date,
            format="DD/MM/YYYY"
        )

        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)
        
        entradas_filtradas = entradas_df[(entradas_df['data'].dt.date >= start_date.date()) & (entradas_df['data'].dt.date <= end_date.date())]
        saidas_filtradas = saidas_df[(saidas_df['data'].dt.date >= start_date.date()) & (saidas_df['data'].dt.date <= end_date.date())]
    else:
        # Define dataframes vazios se 'dates' estiver vazia após os filtros
        entradas_filtradas = pd.DataFrame(columns=entradas_df.columns)
        saidas_filtradas = pd.DataFrame(columns=saidas_df.columns)


# --- CÁLCULOS E MÉTRICAS PRINCIPAIS ---
total_entradas = entradas_filtradas['valor_atendimento'].sum() if not entradas_filtradas.empty else 0
total_saidas = saidas_filtradas['valor'].sum() if not saidas_filtradas.empty else 0
lucro_real = total_entradas - total_saidas

# Exibindo as métricas
col1, col2, col3 = st.columns(3)
col1.metric("Total de Entradas", f"R$ {total_entradas:,.2f}")
col2.metric("Total de Saídas", f"R$ {total_saidas:,.2f}")
col3.metric("Lucro Real", f"R$ {lucro_real:,.2f}")

st.markdown("---")

# --- GRÁFICOS ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("Composição das Saídas")
    if not saidas_filtradas.empty:
        fig_saidas = px.pie(saidas_filtradas, names='descricao', values='valor', title="Distribuição de Despesas")
        st.plotly_chart(fig_saidas, use_container_width=True)
    else:
        st.info("Nenhuma saída registrada no período.")

with col2:
    st.subheader("Composição das Entradas")
    if not entradas_filtradas.empty:
        entradas_plot = entradas_filtradas[['horas_tecnicas', 'horas_tecnicas_50', 'km', 'refeicao', 'pecas']].sum().reset_index()
        entradas_plot.columns = ['Tipo de Entrada', 'Valor']
        valor_fixo_total = entradas_filtradas['valor_atendimento'].sum() - entradas_plot['Valor'].sum()
        if valor_fixo_total > 0:
            fixo_df = pd.DataFrame([{'Tipo de Entrada': 'Valor Fixo Serviço', 'Valor': valor_fixo_total}])
            entradas_plot = pd.concat([entradas_plot, fixo_df], ignore_index=True)

        fig_entradas = px.pie(entradas_plot, names='Tipo de Entrada', values='Valor', title="Distribuição de Receitas")
        st.plotly_chart(fig_entradas, use_container_width=True)
    else:
        st.info("Nenhuma entrada registrada no período.")
        
# Gráfico de Lucro ao Longo do Tempo
st.subheader("Balanço (Entradas vs. Saídas) por Dia")
if not entradas_filtradas.empty or not saidas_filtradas.empty:
    entradas_diarias = entradas_filtradas.groupby(entradas_filtradas['data'].dt.date)['valor_atendimento'].sum().reset_index(name='Total Entrada')
    saidas_diarias = saidas_filtradas.groupby(saidas_filtradas['data'].dt.date)['valor'].sum().reset_index(name='Total Saída')
    
    balanco_df = pd.merge(entradas_diarias, saidas_diarias, on='data', how='outer').fillna(0)
    balanco_df['Lucro'] = balanco_df['Total Entrada'] - balanco_df['Total Saída']

    fig_balanco = px.bar(balanco_df, x='data', y=['Total Entrada', 'Total Saída'], title="Entradas vs. Saídas por Dia", barmode='group')
    st.plotly_chart(fig_balanco, use_container_width=True)
else:
    st.info("Sem dados para exibir o balanço diário.")

# --- EXIBIR TABELAS DE DADOS ---
st.markdown("---")
st.subheader("Registros Detalhados")

expander_entradas = st.expander("Ver todas as entradas")
with expander_entradas:
    st.dataframe(entradas_df)

expander_saidas = st.expander("Ver todas as saídas")
with expander_saidas:
    st.dataframe(saidas_df)