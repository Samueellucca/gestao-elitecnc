import streamlit as st
import pandas as pd
import io
import plotly.graph_objects as go
import plotly.express as px
from sqlalchemy import create_engine
from datetime import date, timedelta

# --- CONFIGURAÇÃO DA PÁGINA ---
# Deve ser o primeiro comando Streamlit
st.set_page_config(page_title="Fluxo de Caixa", page_icon="🌊", layout="wide")

# --- VERIFICAÇÃO DE LOGIN ---
if "authentication_status" not in st.session_state or not st.session_state["authentication_status"]:
    st.error("Acesso negado. Por favor, faça login na página inicial.")
    st.stop()

st.sidebar.image("logo.png", width=150)
st.sidebar.button("Sair", on_click=lambda: st.session_state.update({"authentication_status": None}))

def main():
    st.title("🌊 Fluxo de Caixa")

    connection_url = st.secrets["database"]["connection_url"]
    engine = create_engine(connection_url)

    @st.cache_data(ttl=300)
    def carregar_transacoes(incluir_pendentes):
        try:
            # 1. REALIZADO (Pago) - Baseado na data de pagamento
            q_ent_pago = "SELECT data_pagamento as data, descricao_servico as descricao, valor_atendimento as valor, 'Pago' as status_pagamento, cliente as categoria FROM entradas WHERE status = 'Pago' AND data_pagamento IS NOT NULL"
            q_sai_pago = "SELECT data_pagamento as data, descricao, valor, 'Pago' as status_pagamento, tipo_conta as categoria FROM saidas WHERE status = 'Pago' AND data_pagamento IS NOT NULL"
            
            entradas_df = pd.read_sql_query(q_ent_pago, engine, parse_dates=['data'])
            saidas_df = pd.read_sql_query(q_sai_pago, engine, parse_dates=['data'])
            
            # 2. PROJETADO (Pendente) - Baseado na data de vencimento (se solicitado)
            if incluir_pendentes:
                q_ent_pend = "SELECT data, descricao_servico as descricao, valor_atendimento as valor, 'Previsto' as status_pagamento, cliente as categoria FROM entradas WHERE status = 'Pendente'"
                q_sai_pend = "SELECT data, descricao, valor, 'Previsto' as status_pagamento, tipo_conta as categoria FROM saidas WHERE status = 'Pendente'"
                
                ent_pend_df = pd.read_sql_query(q_ent_pend, engine, parse_dates=['data'])
                sai_pend_df = pd.read_sql_query(q_sai_pend, engine, parse_dates=['data'])
                
                entradas_df = pd.concat([entradas_df, ent_pend_df])
                saidas_df = pd.concat([saidas_df, sai_pend_df])

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

    # --- FILTROS NO TOPO (LAYOUT MELHORADO) ---
    with st.container(border=True):
        col_f1, col_f2, col_f3 = st.columns([1, 1, 2])
        
        saldo_inicial = col_f1.number_input("💰 Saldo Inicial (R$)", value=0.0, step=100.0)
        incluir_previsao = col_f1.checkbox("Incluir Previsão (Pendentes)?", value=False)
        
        agrupamento = col_f2.selectbox(
            "📅 Agrupar por:",
            options=['Detalhado', 'Dia', 'Semana', 'Mês'],
            index=1 # Padrão para 'Dia'
        )
        
        df_transacoes = carregar_transacoes(incluir_previsao)

        if not df_transacoes.empty:
            min_date = df_transacoes['data'].min().date()
            max_date = df_transacoes['data'].max().date()
        else:
            min_date = date.today()
            max_date = date.today()
            
        data_range = col_f3.date_input(
            "🗓️ Período de Análise:",
            value=[min_date, max_date],
            min_value=min_date,
            max_value=max_date
        )
        
        if isinstance(data_range, list) and len(data_range) == 2:
            data_inicio, data_fim = data_range
        else:
            data_inicio, data_fim = min_date, max_date

    if df_transacoes.empty:
        st.info("Não há lançamentos para exibir o fluxo de caixa com os filtros atuais.")
    else:
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
            
            with st.container(border=True):
                st.subheader("📊 Resumo Financeiro")
                col1, col2, col3, col4, col5 = st.columns(5)
                col1.metric("Saldo Inicial", f"R$ {saldo_inicial:,.2f}")
                col2.metric("Saldo Final", f"R$ {saldo_final:,.2f}", delta=f"{(saldo_final - saldo_inicial):,.2f}")
                col3.metric("🟢 Entradas", f"R$ {total_entradas:,.2f}")
                col4.metric("🔴 Saídas", f"R$ {abs(total_saidas):,.2f}")
                col5.metric("💧 Líquido", f"R$ {resultado_liquido:,.2f}", delta_color="normal" if resultado_liquido >= 0 else "inverse")

            # --- ALERTA DE SALDO NEGATIVO ---
            min_saldo = df_filtrado['saldo_acumulado'].min()
            if min_saldo < 0:
                data_negativo = df_filtrado[df_filtrado['saldo_acumulado'] < 0]['data'].iloc[0]
                st.error(f"🚨 ALERTA DE CAIXA: O saldo ficará negativo (R$ {min_saldo:,.2f}) em {data_negativo.strftime('%d/%m/%Y')}. Verifique as previsões!", icon="📉")

            # --- LÓGICA DE AGRUPAMENTO E GRÁFICOS ---
            with st.container(border=True):
                st.subheader(f"📈 Evolução do Caixa ({agrupamento})")

                if agrupamento == 'Detalhado':
                    fig = go.Figure()
                    fig.add_trace(go.Bar(
                        x=df_filtrado['data'], y=df_filtrado['valor'], name='Transação',
                        marker_color=['#28a745' if v > 0 else '#dc3545' for v in df_filtrado['valor']],
                        hovertemplate='<b>%{x|%d/%m/%Y}</b><br>Valor: R$ %{y:,.2f}<extra></extra>'
                    ))
                    fig.add_trace(go.Scatter(
                        x=df_filtrado['data'], y=df_filtrado['saldo_acumulado'], name='Saldo Acumulado',
                        mode='lines+markers', line=dict(color='#007bff', width=3),
                        hovertemplate='<b>%{x|%d/%m/%Y}</b><br>Saldo: R$ %{y:,.2f}<extra></extra>'
                    ))
                    fig.update_layout(hovermode='x unified', margin=dict(l=0, r=0, t=30, b=0))
                else:
                    # Lógica para agrupar por Dia, Semana ou Mês
                    if agrupamento == 'Dia':
                        grouper = pd.Grouper(key='data', freq='D')
                        date_format = "%d/%m/%Y"
                    elif agrupamento == 'Semana':
                        grouper = pd.Grouper(key='data', freq='W-MON')
                        date_format = "Semana %d/%m"
                    else: # Mês
                        grouper = pd.Grouper(key='data', freq='MS')
                        date_format = "%B/%Y"

                    df_agrupado = df_filtrado.groupby(grouper)['valor'].sum().reset_index()
                    # df_agrupado = df_agrupado[df_agrupado['valor'] != 0]

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
                        totals = {"marker":{"color":"#007bff", "line":{"color":"#0056b3", "width":2}}}, # Azul para o total
                        increasing = {"marker":{"color":"#28a745"}}, # Verde para entradas
                        decreasing = {"marker":{"color":"#dc3545"}}, # Vermelho para saídas
                    ))

                    # Adiciona o Saldo Inicial como a base
                    fig.add_trace(go.Bar(
                        x=["Saldo Inicial"], y=[saldo_inicial],
                        marker_color="#6c757d", name="Saldo Inicial",
                        text=f"R${saldo_inicial:,.2f}", textposition="outside"
                    ))
                    
                    # Ordenação do eixo X para garantir que Saldo Inicial venha primeiro
                    x_order = ["Saldo Inicial"] + [d.strftime(date_format) for d in df_agrupado['data']] + ["Saldo Final"]
                    fig.update_layout(xaxis={'categoryorder':'array', 'categoryarray':x_order})

                    fig.update_layout(
                        showlegend=False,
                        yaxis_title="Valor (R$)",
                        margin=dict(l=0, r=0, t=30, b=0)
                    )
                
                st.plotly_chart(fig, use_container_width=True)

            # --- GRÁFICOS DE COMPOSIÇÃO (PIZZA) ---
            with st.container(border=True):
                st.subheader("🍰 Composição do Fluxo")
                col_pie1, col_pie2 = st.columns(2)
                
                with col_pie1:
                    df_entradas_pie = df_filtrado[df_filtrado['valor'] > 0]
                    if not df_entradas_pie.empty:
                        fig_pie1 = px.pie(df_entradas_pie, values='valor', names='categoria', title='Receitas por Cliente', hole=0.4)
                        st.plotly_chart(fig_pie1, use_container_width=True)
                    else:
                        st.info("Sem entradas no período.")

                with col_pie2:
                    df_saidas_pie = df_filtrado[df_filtrado['valor'] < 0].copy()
                    df_saidas_pie['valor'] = df_saidas_pie['valor'].abs() # Converte para positivo para o gráfico
                    if not df_saidas_pie.empty:
                        fig_pie2 = px.pie(df_saidas_pie, values='valor', names='categoria', title='Despesas por Categoria', hole=0.4)
                        st.plotly_chart(fig_pie2, use_container_width=True)
                    else:
                        st.info("Sem saídas no período.")

            # --- RANKINGS (TOP 5) ---
            with st.container(border=True):
                st.subheader("🏆 Top 5 - Maiores Movimentações")
                col_top1, col_top2 = st.columns(2)
                
                with col_top1:
                    st.markdown("##### 🟢 Principais Clientes (Receita)")
                    # Agrupa por cliente (categoria para entradas)
                    df_top_receitas = df_filtrado[df_filtrado['valor'] > 0].groupby('categoria')['valor'].sum().reset_index()
                    df_top_receitas = df_top_receitas.sort_values(by='valor', ascending=False).head(5)
                    
                    if not df_top_receitas.empty:
                        fig_top_rec = px.bar(
                            df_top_receitas, 
                            x='valor', 
                            y='categoria', 
                            orientation='h', 
                            text_auto='.2s',
                            color_discrete_sequence=['#28a745']
                        )
                        fig_top_rec.update_layout(
                            yaxis={'categoryorder':'total ascending'}, 
                            showlegend=False, 
                            margin=dict(l=0, r=0, t=0, b=0), 
                            height=250,
                            xaxis_title=None,
                            yaxis_title=None
                        )
                        st.plotly_chart(fig_top_rec, use_container_width=True)
                    else:
                        st.info("Sem dados de receita para ranking.")

                with col_top2:
                    st.markdown("##### 🔴 Principais Despesas (Descrição)")
                    # Agrupa por descrição para detalhar a despesa
                    df_top_despesas = df_filtrado[df_filtrado['valor'] < 0].copy()
                    df_top_despesas['valor'] = df_top_despesas['valor'].abs()
                    df_top_despesas = df_top_despesas.groupby('descricao')['valor'].sum().reset_index()
                    df_top_despesas = df_top_despesas.sort_values(by='valor', ascending=False).head(5)
                    
                    if not df_top_despesas.empty:
                        fig_top_desp = px.bar(
                            df_top_despesas, 
                            x='valor', 
                            y='descricao', 
                            orientation='h', 
                            text_auto='.2s', 
                            color_discrete_sequence=['#dc3545']
                        )
                        fig_top_desp.update_layout(
                            yaxis={'categoryorder':'total ascending'}, 
                            showlegend=False, 
                            margin=dict(l=0, r=0, t=0, b=0), 
                            height=250,
                            xaxis_title=None,
                            yaxis_title=None
                        )
                        st.plotly_chart(fig_top_desp, use_container_width=True)
                    else:
                        st.info("Sem dados de despesa para ranking.")

            # --- TABELA DE EXTRATO COLORIDA ---
            with st.container(border=True):
                st.subheader("📝 Extrato Detalhado")
                
                # Botão de Exportação
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    df_filtrado.to_excel(writer, index=False, sheet_name='Extrato')
                
                st.download_button(
                    label="📥 Baixar Extrato em Excel",
                    data=buffer.getvalue(),
                    file_name=f"Fluxo_Caixa_{data_inicio}_{data_fim}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

                def colorir_valores(val):
                    color = '#28a745' if val > 0 else '#dc3545' if val < 0 else 'black'
                    return f'color: {color}; font-weight: bold;'
                
                df_display = df_filtrado[['data', 'descricao', 'categoria', 'status_pagamento', 'valor', 'saldo_acumulado']].copy()
                
                st.dataframe(
                    df_display.style.applymap(colorir_valores, subset=['valor']).format({'valor': 'R$ {:,.2f}', 'saldo_acumulado': 'R$ {:,.2f}'}),
                    column_config={
                        "data": st.column_config.DatetimeColumn("Data", format="DD/MM/YYYY - HH:mm"), 
                        "descricao": "Descrição", 
                        "categoria": "Categoria/Cliente",
                        "status_pagamento": "Status",
                        "valor": "Valor (R$)", 
                        "saldo_acumulado": "Saldo (R$)"
                    },
                    use_container_width=True,
                    hide_index=True,
                    height=400
                )

if __name__ == "__main__":
    if st.session_state.get("authentication_status"):
        main()
    else:
        st.warning("Você precisa fazer login para acessar esta página.")
        st.info("Por favor, volte à página principal para fazer o login.")