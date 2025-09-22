import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, time
from sqlalchemy import create_engine
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Dashboard Financeiro", page_icon="💰", layout="wide")

# --- CARREGANDO CONFIGURAÇÕES DE LOGIN ---
with open('config.yaml') as file:
    config = yaml.load(file, Loader=SafeLoader)

authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days']
)

# --- TELA DE LOGIN ---
authenticator.login()

if st.session_state["authentication_status"]:
    # --- APLICAÇÃO PRINCIPAL ---
    DB_FILE = "financeiro.db"
    engine = create_engine(f'sqlite:///{DB_FILE}')
    
    name = st.session_state["name"]
    username = st.session_state["username"]
    
    st.sidebar.title(f'Bem-vindo(a), *{name}*')
    authenticator.logout('Sair', 'sidebar')

    VALOR_POR_KM = 1.40
    VALOR_HORA_TECNICA = 90.00
    VALOR_HORA_TECNICA_50 = VALOR_HORA_TECNICA * 1.5

    @st.cache_data
    def carregar_dados():
        try:
            entradas_df = pd.read_sql_table('entradas', engine, parse_dates=['data'])
        except ValueError:
            entradas_df = pd.DataFrame()
        try:
            saidas_df = pd.read_sql_table('saidas', engine, parse_dates=['data'])
        except ValueError:
            saidas_df = pd.DataFrame()
        return entradas_df, saidas_df

    entradas_df, saidas_df = carregar_dados()

    # --- BARRA LATERAL PARA LANÇAMENTOS ---
    st.sidebar.header("Lançar Novos Dados")

    with st.sidebar.form("form_entradas", clear_on_submit=True):
        st.subheader("Nova Entrada (O.S.)")
        data_entrada_d = st.date_input("Data do Atendimento", value=datetime.now())
        data_entrada_t = st.time_input("Hora do Atendimento", value=datetime.now().time())
        os_id = st.text_input("Nº da O.S.")
        valor_fixo = st.number_input("Valor Fixo (se houver)", min_value=0.0, format="%.2f")
        qtd_horas_tecnicas = st.number_input(f"Qtd Horas Técnicas", min_value=0.0, format="%.2f")
        qtd_horas_tecnicas_50 = st.number_input(f"Qtd Horas Técnicas 50%", min_value=0.0, format="%.2f")
        qtd_km = st.number_input(f"Qtd KM Rodados", min_value=0.0, format="%.2f")
        refeicao = st.number_input("Valor da Refeição", min_value=0.0, format="%.2f")
        pecas_entrada = st.number_input("Valor das Peças (Venda)", min_value=0.0, format="%.2f")
        submit_entrada = st.form_submit_button("Lançar Entrada")

        if submit_entrada:
            data_entrada = datetime.combine(data_entrada_d, data_entrada_t)
            valor_km_final = qtd_km * VALOR_POR_KM
            valor_horas_tecnicas_final = qtd_horas_tecnicas * VALOR_HORA_TECNICA
            valor_horas_tecnicas_50_final = qtd_horas_tecnicas_50 * VALOR_HORA_TECNICA_50
            valor_atendimento_calculado = (valor_fixo + valor_horas_tecnicas_final + valor_horas_tecnicas_50_final + valor_km_final + refeicao + pecas_entrada)
            
            nova_entrada = pd.DataFrame([{
                'data': pd.to_datetime(data_entrada), 'ordem_servico': os_id, 'valor_atendimento': valor_atendimento_calculado,
                'horas_tecnicas': valor_horas_tecnicas_final, 'horas_tecnicas_50': valor_horas_tecnicas_50_final, 
                'km': valor_km_final, 'refeicao': refeicao, 'pecas': pecas_entrada,
                'usuario_lancamento': username
            }])
            nova_entrada.to_sql('entradas', engine, if_exists='append', index=False)
            st.cache_data.clear()
            st.sidebar.success(f"Entrada lançada!")
            st.rerun()

    with st.sidebar.form("form_saidas", clear_on_submit=True):
        st.subheader("Nova Saída")
        data_saida_d = st.date_input("Data da Despesa", value=datetime.now())
        data_saida_t = st.time_input("Hora da Despesa", value=datetime.now().time())
        tipo_conta = st.selectbox("Tipo de Conta", ["Fixa", "Variável"])
        descricao_saida = st.text_input("Descrição da Despesa")
        valor_saida = st.number_input("Valor da Despesa", min_value=0.0, format="%.2f")
        submit_saida = st.form_submit_button("Lançar Saída")

        if submit_saida:
            data_saida = datetime.combine(data_saida_d, data_saida_t)
            nova_saida = pd.DataFrame([{
                'data': pd.to_datetime(data_saida), 'tipo_conta': tipo_conta, 
                'descricao': descricao_saida, 'valor': valor_saida,
                'usuario_lancamento': username
            }])
            nova_saida.to_sql('saidas', engine, if_exists='append', index=False)
            st.cache_data.clear()
            st.sidebar.success("Saída lançada!")
            st.rerun()

    # --- PAINEL PRINCIPAL ---
    st.title("📊 Dashboard Financeiro")
    st.markdown("---")
    
    if not entradas_df.empty or not saidas_df.empty:
        dates = []
        if not entradas_df.empty:
            dates.append(entradas_df['data'].min().date())
            dates.append(entradas_df['data'].max().date())
        if not saidas_df.empty:
            dates.append(saidas_df['data'].min().date())
            dates.append(saidas_df['data'].max().date())
        
        min_date = min(dates)
        max_date = max(dates)
        
        date_range = st.date_input(
            "Filtre por período:",
            [min_date, max_date],
            min_value=min_date,
            max_value=max_date,
            format="DD/MM/YYYY"
        )

        if isinstance(date_range, tuple) and len(date_range) == 2:
            start_date, end_date = date_range
        else:
            start_date = end_date = date_range

        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date).replace(hour=23, minute=59, second=59)
        
        entradas_filtradas = entradas_df[(entradas_df['data'] >= start_date) & (entradas_df['data'] <= end_date)]
        saidas_filtradas = saidas_df[(saidas_df['data'] >= start_date) & (saidas_df['data'] <= end_date)]
    else:
        st.warning("Nenhum dado lançado ainda.")
        entradas_filtradas = pd.DataFrame()
        saidas_filtradas = pd.DataFrame()

    total_entradas = entradas_filtradas['valor_atendimento'].sum() if not entradas_filtradas.empty else 0
    total_saidas = saidas_filtradas['valor'].sum() if not saidas_filtradas.empty else 0
    lucro_real = total_entradas - total_saidas

    col1, col2, col3 = st.columns(3)
    col1.metric("Total de Entradas", f"R$ {total_entradas:,.2f}")
    col2.metric("Total de Saídas", f"R$ {total_saidas:,.2f}")
    col3.metric("Lucro Real", f"R$ {lucro_real:,.2f}")

    st.markdown("---")

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

    st.markdown("---")
    st.subheader("Registros Detalhados")

    with st.expander("Ver todas as entradas"):
        st.dataframe(entradas_df)

    with st.expander("Ver todas as saídas"):
        st.dataframe(saidas_df)

elif st.session_state["authentication_status"] is False:
    st.error('Usuário/senha incorreto')
elif st.session_state["authentication_status"] is None:
    st.warning('Por favor, insira seu usuário e senha para acessar.')