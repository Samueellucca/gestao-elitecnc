import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from sqlalchemy import create_engine
from datetime import date, timedelta

# --- VERIFICAÇÃO DE LOGIN ---
if "authentication_status" not in st.session_state or not st.session_state["authentication_status"]:
    st.error("Acesso negado. Por favor, faça login na página inicial.")
    st.stop()

st.sidebar.image("logo.png", width=150)
st.sidebar.button("Sair", on_click=lambda: st.session_state.update({"authentication_status": None}))


def main():
    """
    Função principal que executa a página do Fluxo de Caixa.
    Movido para dentro de uma função para organizar o escopo após a verificação de login.
    """
    st.set_page_config(page_title="Fluxo de Caixa", page_icon="🌊", layout="wide")

    st.title("🌊 Fluxo de Caixa Interativo")
    st.write("Analise a evolução do seu saldo com filtros e métricas detalhadas.")

    connection_url = st.secrets["database"]["connection_url"]
    engine = create_engine(connection_url)

    @st.cache_data
    def carregar_transacoes():
        try:
            # Para entradas, usamos a data_pagamento se o status for 'Pago'
            query_entradas = "SELECT data_pagamento as data, descricao_servico as descricao, valor_atendimento as valor FROM entradas WHERE status = 'Pago' AND data_pagamento IS NOT NULL"
            entradas_df = pd.read_sql_query(query_entradas, engine, parse_dates=['data'])
            
            # Para saídas, a mesma lógica
            query_saidas = "SELECT data_pagamento as data, descricao, valor FROM saidas WHERE status = 'Pago' AND data_pagamento IS NOT NULL"
            saidas_df = pd.read_sql_query(query_saidas, engine, parse_dates=['data'])
            
            entradas_df['tipo'] = 'Entrada'
            saidas_df['tipo'] = 'Saída'
            saidas_df['valor'] = saidas_df['valor'] * -1
            
            transacoes_df = pd.concat([entradas_df, saidas_df], ignore_index=True)
            # Remove linhas onde a data é nula (pode acontecer se houver dados inconsistentes)
            transacoes_df.dropna(subset=['data'], inplace=True)
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
        
        agrupamento = st.sidebar.selectbox(
            "Agrupar visualização por:",
            options=['Detalhado', 'Dia', 'Semana', 'Mês'],
            index=1 # Padrão para 'Dia'
        )
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

            # --- MÉTRICAS RESUMIDAS ---
            saldo_final = saldo_inicial + df_filtrado['valor'].sum()
            total_entradas = df_filtrado[df_filtrado['tipo'] == 'Entrada']['valor'].sum()
            total_saidas = df_filtrado[df_filtrado['tipo'] == 'Saída']['valor'].sum() # Já é negativo
            resultado_liquido = total_entradas + total_saidas # Soma de valores positivos e negativos
            
            # Calcula saldo para cada transação para encontrar picos e vales
            df_filtrado['saldo_acumulado'] = saldo_inicial + df_filtrado['valor'].cumsum()
            pico_saldo = df_filtrado['saldo_acumulado'].max()
            vale_saldo = df_filtrado['saldo_acumulado'].min()

            st.markdown("---")
            st.subheader("Resumo do Período")
            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("Saldo Inicial", f"R$ {saldo_inicial:,.2f}")
            col2.metric("Saldo Final", f"R$ {saldo_final:,.2f}")
            col3.metric("🟢 Entradas", f"R$ {total_entradas:,.2f}")
            col4.metric("🔴 Saídas", f"R$ {abs(total_saidas):,.2f}")
            col5.metric(" Resultado Líquido", f"R$ {resultado_liquido:,.2f}", delta=f"{resultado_liquido:,.2f}")
            
            col_extra1, col_extra2, _ = st.columns(3)
            col_extra1.metric("📈 Pico de Saldo", f"R$ {pico_saldo:,.2f}")
            col_extra2.metric("📉 Vale de Saldo", f"R$ {vale_saldo:,.2f}")

            st.markdown("---")

            # --- LÓGICA DE AGRUPAMENTO E GRÁFICOS ---
            st.subheader(f"Análise de Fluxo de Caixa por {agrupamento}")

            if agrupamento == 'Detalhado':
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=df_filtrado['data'], y=df_filtrado['valor'], name='Transação',
                    marker_color=['green' if v > 0 else 'red' for v in df_filtrado['valor']],
                    hovertemplate='<b>%{x|%d/%m/%Y}</b><br>Valor: R$ %{y:,.2f}<extra></extra>'
                ))
                fig.add_trace(go.Scatter(
                    x=df_filtrado['data'], y=df_filtrado['saldo_acumulado'], name='Saldo Acumulado',
                    mode='lines+markers', line=dict(color='blue', width=3),
                    hovertemplate='<b>%{x|%d/%m/%Y}</b><br>Saldo: R$ %{y:,.2f}<extra></extra>'
                ))
                fig.update_layout(title_text='Evolução do Saldo e Impacto das Transações', hovermode='x unified')
            else:
                # Lógica para agrupar por Dia, Semana ou Mês
                if agrupamento == 'Dia':
                    grouper = pd.Grouper(key='data', freq='D')
                    date_format = "%d/%m/%Y"
                elif agrupamento == 'Semana':
                    grouper = pd.Grouper(key='data', freq='W-MON')
                    date_format = "Semana de %d/%m/%Y"
                else: # Mês
                    grouper = pd.Grouper(key='data', freq='MS')
                    date_format = "%B/%Y"

                df_agrupado = df_filtrado.groupby(grouper)['valor'].sum().reset_index()
                df_agrupado = df_agrupado[df_agrupado['valor'] != 0]

                # Gráfico de Cascata (Waterfall)
                fig = go.Figure(go.Waterfall(
                    name = "Fluxo",
                    orientation = "v",
                    measure = ["relative"] * len(df_agrupado) + ["total"],
                    x = [d.strftime(date_format) for d in df_agrupado['data']] + ["Saldo Final"],
                    textposition = "outside",
                    text = [f"R${v:,.2f}" for v in df_agrupado['valor']] + [f"R${saldo_final:,.2f}"],
                    y = list(df_agrupado['valor']) + [saldo_final],
                    connector = {"line":{"color":"rgb(63, 63, 63)"}},
                    totals = {"marker":{"color":"#0000FF", "line":{"color":"blue", "width":2}}}, # Azul para o total
                    increasing = {"marker":{"color":"#28a745"}}, # Verde para entradas
                    decreasing = {"marker":{"color":"#dc3545"}}, # Vermelho para saídas
                ))

                # Adiciona o Saldo Inicial como a base
                fig.update_layout(waterfallgap = 0.3)
                fig.add_trace(go.Bar(
                    x=["Saldo Inicial"], y=[saldo_inicial],
                    marker_color="#4682B4", name="Saldo Inicial",
                    text=f"R${saldo_inicial:,.2f}", textposition="outside"
                ))
                fig.update_layout(
                    title=f"Fluxo de Caixa por {agrupamento}",
                    showlegend=False,
                    xaxis_title=agrupamento,
                    yaxis_title="Valor (R$)"
                )
            
            st.plotly_chart(fig, use_container_width=True)

            st.markdown("---")

            # --- TABELA DE EXTRATO COLORIDA ---
            with st.expander("Ver Extrato Detalhado do Período", expanded=False):
                def colorir_valores(val):
                    color = '#28a745' if val > 0 else '#dc3545' if val < 0 else 'black'
                    return f'color: {color}; font-weight: bold;'
                
                df_display = df_filtrado[['data', 'descricao', 'valor', 'saldo_acumulado']].copy()
                
                st.dataframe(
                    df_display.style.applymap(colorir_valores, subset=['valor']).format('R$ {:,.2f}', subset=['valor', 'saldo_acumulado']),
                    column_config={
                        "data": st.column_config.DatetimeColumn("Data", format="DD/MM/YYYY - HH:mm"), 
                        "descricao": "Descrição", 
                        "valor": "Valor (R$)", 
                        "saldo_acumulado": "Saldo (R$)"
                    },
                    use_container_width=True,
                    hide_index=True
                )

if __name__ == "__main__":
    if st.session_state.get("authentication_status"):
        main()
    else:
        st.warning("Você precisa fazer login para acessar esta página.")
        st.info("Por favor, volte à página principal para fazer o login.")