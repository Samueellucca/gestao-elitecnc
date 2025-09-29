import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
from datetime import date

# --- VERIFICAÇÃO DE LOGIN ---
try:
    with open('config.yaml', 'r', encoding='utf-8') as file:
        config = yaml.load(file, Loader=SafeLoader)
except FileNotFoundError:
    st.error("Arquivo de configuração 'config.yaml' não encontrado.")
    st.stop()

authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days']
)

if st.session_state.get("authentication_status"):
    authenticator.logout('Sair', 'sidebar')
    
    # --- AQUI COMEÇA O CÓDIGO DA PÁGINA ---
    st.set_page_config(page_title="Fluxo de Caixa", page_icon="🌊", layout="wide")
    st.title("🌊 Fluxo de Caixa Interativo")
    st.write("Analise a evolução do seu saldo com filtros e métricas detalhadas.")

    DB_FILE = "financeiro.db"
    engine = create_engine(f'sqlite:///{DB_FILE}')

    @st.cache_data
    def carregar_transacoes():
        try:
            entradas_df = pd.read_sql_query("SELECT data, descricao_servico as descricao, valor_atendimento as valor FROM entradas", engine, parse_dates=['data'])
            saidas_df = pd.read_sql_query("SELECT data, descricao, valor FROM saidas", engine, parse_dates=['data'])
            
            entradas_df['tipo'] = 'Entrada'
            saidas_df['tipo'] = 'Saída'
            saidas_df['valor'] = saidas_df['valor'] * -1
            
            transacoes_df = pd.concat([entradas_df, saidas_df], ignore_index=True)
            transacoes_df.sort_values(by='data', inplace=True)
            return transacoes_df
            
        except Exception:
            return pd.DataFrame()

    df_transacoes = carregar_transacoes()

    if df_transacoes.empty:
        st.info("Não há lançamentos de entrada ou saída para exibir o fluxo de caixa.")
    else:
        # --- BARRA LATERAL COM FILTROS ---
        st.sidebar.header("Filtros e Opções")
        saldo_inicial = st.sidebar.number_input("Saldo Inicial (R$)", value=0.0, step=100.0)
        
        min_date = df_transacoes['data'].min().date()
        max_date = df_transacoes['data'].max().date()
        
        data_inicio, data_fim = st.sidebar.date_input(
            "Selecione o Período:",
            [min_date, max_date],
            min_value=min_date,
            max_value=max_date
        )

        # --- FILTRANDO OS DADOS ---
        df_filtrado = df_transacoes[
            (df_transacoes['data'].dt.date >= data_inicio) & 
            (df_transacoes['data'].dt.date <= data_fim)
        ].copy()

        # Recalcula o saldo com base no saldo inicial e no período filtrado
        df_filtrado['saldo'] = saldo_inicial + df_filtrado['valor'].cumsum()

        st.markdown("---")

        # --- MÉTRICAS RESUMIDAS ---
        total_entradas = df_filtrado[df_filtrado['valor'] > 0]['valor'].sum()
        total_saidas = df_filtrado[df_filtrado['valor'] < 0]['valor'].sum()
        resultado_liquido = total_entradas + total_saidas

        col1, col2, col3 = st.columns(3)
        col1.metric("🟢 Total de Entradas", f"R$ {total_entradas:,.2f}")
        col2.metric("🔴 Total de Saídas", f"R$ {abs(total_saidas):,.2f}")
        col3.metric("💰 Resultado Líquido", f"R$ {resultado_liquido:,.2f}", delta=f"{resultado_liquido:,.2f} R$")

        st.markdown("---")

        # --- GRÁFICO DE EVOLUÇÃO DO SALDO ---
        st.subheader("Evolução do Saldo no Período")
        fig = px.line(
            df_filtrado, 
            x='data', 
            y='saldo', 
            title='Evolução do Saldo ao Longo do Tempo',
            markers=True,
            labels={'data': 'Data', 'saldo': 'Saldo (R$)'}
        )
        fig.update_traces(hovertemplate='<b>%{x|%d/%m/%Y}</b><br>Saldo: R$ %{y:,.2f}')
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")

        # --- TABELA DE EXTRATO COLORIDA ---
        st.subheader("Extrato de Transações no Período")
        
        def colorir_valores(val):
            color = 'green' if val > 0 else 'red' if val < 0 else 'black'
            return f'color: {color}; font-weight: bold;'
        
        df_display = df_filtrado[['data', 'descricao', 'valor', 'saldo']].copy()
        
        st.dataframe(
            df_display.style.applymap(colorir_valores, subset=['valor']),
            column_config={
                "data": st.column_config.DatetimeColumn("Data", format="DD/MM/YYYY - HH:mm"),
                "descricao": "Descrição",
                "valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f"),
                "saldo": st.column_config.NumberColumn("Saldo (R$)", format="R$ %.2f")
            },
            use_container_width=True,
            hide_index=True
        )

else:
    # Mensagens de erro para quem não está logado
    if st.session_state.get("authentication_status") is False:
        st.error('Usuário ou senha incorreto.')
        st.warning('Por favor, volte à página principal para tentar novamente.')
    else:
        st.warning('Você precisa fazer login para acessar esta página.')
        st.info('Por favor, volte à página principal (Dashboard) para fazer o login.')