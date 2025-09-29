import streamlit as st
import pandas as pd
import plotly.graph_objects as go
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

    # Conexão com o banco de dados da nuvem a partir dos "Secrets"
    connection_url = st.secrets["database"]["connection_url"]
    engine = create_engine(connection_url)

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

        if df_filtrado.empty:
            st.warning("Nenhum dado encontrado para o período selecionado.")
        else:
            df_filtrado.reset_index(drop=True, inplace=True)
            df_filtrado['saldo'] = saldo_inicial + df_filtrado['valor'].cumsum()

            st.markdown("---")

            # --- MÉTRICAS RESUMIDAS ---
            total_entradas = df_filtrado[df_filtrado['valor'] > 0]['valor'].sum()
            total_saidas = df_filtrado[df_filtrado['valor'] < 0]['valor'].sum()
            resultado_liquido = total_entradas + total_saidas

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Saldo Inicial", f"R$ {saldo_inicial:,.2f}")
            col2.metric("🟢 Entradas", f"R$ {total_entradas:,.2f}")
            col3.metric("🔴 Saídas", f"R$ {abs(total_saidas):,.2f}")
            col4.metric("💰 Resultado Líquido", f"R$ {resultado_liquido:,.2f}", delta=f"{resultado_liquido:,.2f} R$")

            st.markdown("---")

            # --- NOVO GRÁFICO COMBINADO ---
            st.subheader("Evolução do Saldo e Transações no Período")

            fig = go.Figure()

            # Adiciona as barras de transações (entradas e saídas)
            fig.add_trace(go.Bar(
                x=df_filtrado['data'],
                y=df_filtrado['valor'],
                name='Transação',
                marker_color=['green' if v > 0 else 'red' for v in df_filtrado['valor']],
                hovertemplate='<b>%{x|%d/%m/%Y}</b><br>Valor da Transação: R$ %{y:,.2f}<extra></extra>'
            ))

            # Adiciona a linha de saldo acumulado
            fig.add_trace(go.Scatter(
                x=df_filtrado['data'],
                y=df_filtrado['saldo'],
                name='Saldo Acumulado',
                mode='lines+markers',
                line=dict(color='blue', width=3),
                hovertemplate='<b>%{x|%d/%m/%Y}</b><br>Saldo Acumulado: R$ %{y:,.2f}<extra></extra>'
            ))
            
            fig.update_layout(
                title_text='Evolução do Saldo e Impacto das Transações',
                xaxis_title='Data',
                yaxis_title='Valor (R$)',
                legend_title='Legenda',
                hovermode='x unified'
            )
            
            st.plotly_chart(fig, use_container_width=True)

            st.markdown("---")

            # --- TABELA DE EXTRATO COLORIDA ---
            st.subheader("Extrato de Transações no Período")
            def colorir_valores(val):
                color = '#2E8B57' if val > 0 else '#C70039' if val < 0 else 'black'
                return f'color: {color}; font-weight: bold;'
            
            df_display = df_filtrado[['data', 'descricao', 'valor', 'saldo']].copy()
            
            st.dataframe(
                df_display.style.applymap(colorir_valores, subset=['valor']).format('R$ {:,.2f}', subset=['valor', 'saldo']),
                column_config={"data": st.column_config.DatetimeColumn("Data", format="DD/MM/YYYY - HH:mm"), "descricao": "Descrição", "valor": "Valor (R$)", "saldo": "Saldo (R$)"},
                use_container_width=True,
                hide_index=True
            )

else:
    if st.session_state.get("authentication_status") is False:
        st.error('Usuário ou senha incorreto.')
        st.warning('Por favor, volte à página principal para tentar novamente.')
    else:
        st.warning('Você precisa fazer login para acessar esta página.')
        st.info('Por favor, volte à página principal (Dashboard) para fazer o login.')