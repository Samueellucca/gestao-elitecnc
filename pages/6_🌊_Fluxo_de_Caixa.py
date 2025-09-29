import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader

# --- VERIFICAÇÃO DE LOGIN ---
with open('config.yaml', 'r', encoding='utf-8') as file:
    config = yaml.load(file, Loader=SafeLoader)

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
    st.title("🌊 Fluxo de Caixa")
    st.write("Acompanhe a evolução do seu saldo com cada entrada e saída.")

    DB_FILE = "financeiro.db"
    engine = create_engine(f'sqlite:///{DB_FILE}')

    @st.cache_data
    def carregar_fluxo_de_caixa():
        try:
            entradas_df = pd.read_sql_query("SELECT data, descricao_servico as descricao, valor_atendimento as valor FROM entradas", engine, parse_dates=['data'])
            saidas_df = pd.read_sql_query("SELECT data, descricao, valor FROM saidas", engine, parse_dates=['data'])
            
            # Marca saídas como valores negativos
            saidas_df['valor'] = saidas_df['valor'] * -1
            
            # Junta as duas tabelas
            fluxo_df = pd.concat([entradas_df, saidas_df], ignore_index=True)
            
            # Ordena por data
            fluxo_df.sort_values(by='data', inplace=True)
            
            # Calcula o saldo acumulado
            fluxo_df['saldo'] = fluxo_df['valor'].cumsum()
            
            return fluxo_df
            
        except Exception as e:
            st.error(f"Erro ao carregar os dados do fluxo de caixa: {e}")
            return pd.DataFrame(columns=['data', 'descricao', 'valor', 'saldo'])

    df_fluxo = carregar_fluxo_de_caixa()

    if df_fluxo.empty:
        st.info("Não há lançamentos de entrada ou saída para exibir o fluxo de caixa.")
    else:
        st.markdown("---")
        
        # --- GRÁFICO DE EVOLUÇÃO DO SALDO ---
        st.subheader("Evolução do Saldo")
        fig = px.line(
            df_fluxo, 
            x='data', 
            y='saldo', 
            title='Evolução do Saldo ao Longo do Tempo',
            markers=True,
            labels={'data': 'Data', 'saldo': 'Saldo (R$)'}
        )
        fig.update_traces(hovertemplate='<b>%{x|%d/%m/%Y}</b><br>Saldo: R$ %{y:,.2f}')
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")

        # --- TABELA DE EXTRATO ---
        st.subheader("Extrato de Transações")
        st.dataframe(
            df_fluxo,
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
    else: # se for None
        st.warning('Você precisa fazer login para acessar esta página.')
        st.info('Por favor, volte à página principal (Dashboard) para fazer o login.')