import streamlit as st
import pandas as pd
from datetime import date, datetime
from sqlalchemy import create_engine, text

# --- VERIFICAÇÃO DE LOGIN ---
if "authentication_status" not in st.session_state or not st.session_state["authentication_status"]:
    st.error("Acesso negado. Por favor, faça login na página inicial.")
    st.stop()

st.sidebar.image("logo.png", width=150)
st.sidebar.button("Sair", on_click=lambda: st.session_state.update({"authentication_status": None}))

# --- CONFIGURAÇÃO DA PÁGINA E CONEXÃO COM DB ---
st.set_page_config(page_title="Controle Financeiro", page_icon="💰", layout="wide")
st.title("💰 Controle de Contas a Pagar e a Receber")
st.write("Gerencie aqui os lançamentos pendentes. Ao marcar um item como 'Pago', ele será movido para o seu Fluxo de Caixa.")

connection_url = st.secrets["database"]["connection_url"]
engine = create_engine(connection_url)

# --- FUNÇÕES DE DADOS ---

@st.cache_data(ttl=300)
def carregar_dados(tabela, status="'Pendente'"):
    """Carrega dados de uma tabela com um status específico."""
    try:
        query = f"SELECT * FROM {tabela} WHERE status IN ({status}) ORDER BY data ASC"
        df = pd.read_sql_query(query, engine, parse_dates=['data'])
        return df
    except Exception as e:
        st.error(f"Erro ao carregar dados da tabela {tabela}: {e}")
        return pd.DataFrame()

def marcar_como_pago(tabela, pagamentos):
    """Atualiza o status e a data de pagamento de uma lista de IDs."""
    if not pagamentos:
        return
    try:
        with engine.connect() as con:
            for pagamento in pagamentos:
                query = text(f"UPDATE {tabela} SET status = 'Pago', data_pagamento = :data_pagamento WHERE id = :id")
                con.execute(query, {"data_pagamento": pagamento['data_pagamento'], "id": pagamento['id']})
            con.commit()
        st.success(f"{len(pagamentos)} lançamento(s) da tabela '{tabela}' foram marcados como 'Pago'!")
        st.cache_data.clear() # Limpa o cache para recarregar os dados
    except Exception as e:
        st.error(f"Erro ao atualizar status: {e}")

# --- ABAS DE CONTROLE ---
tab1, tab2 = st.tabs(["📥 Contas a Receber (Entradas)", "📤 Contas a Pagar (Saídas)"])

with tab1:
    st.subheader("O.S. com Pagamento Pendente")
    df_receber = carregar_dados("entradas", status="'Pendente'")

    if df_receber.empty:
        st.info("🎉 Ótima notícia! Não há nenhuma conta a receber pendente no momento.")
    else:
        total_a_receber = df_receber['valor_atendimento'].sum()
        st.metric("Valor Total a Receber", f"R$ {total_a_receber:,.2f}")

        # Seleção de itens para dar baixa
        options = {f"ID {row.id} | {row.data.strftime('%d/%m/%Y')} | {row.cliente} | R$ {row.valor_atendimento:,.2f}": row.id for index, row in df_receber.iterrows()}
        lancamentos_selecionados = st.multiselect(
            "Selecione as O.S. para dar baixa:",
            options=options.keys(),
            label_visibility="collapsed"
        )
        ids_selecionados = [options[key] for key in lancamentos_selecionados]

        if ids_selecionados:
            st.markdown("---")
            st.subheader("Confirmar Baixa de Entradas")
            pagamentos_a_confirmar = []

            df_selecionados = df_receber[df_receber['id'].isin(ids_selecionados)]

            for _, row in df_selecionados.iterrows():
                cols = st.columns([3, 1])
                with cols[0]:
                    st.markdown(f"**Cliente:** {row.cliente} | **O.S.:** {row.ordem_servico} | **Valor:** R$ {row.valor_atendimento:,.2f}")
                with cols[1]:
                    data_pagamento = st.date_input(
                        "Data do Recebimento",
                        value=date.today(),
                        key=f"data_receber_{row.id}",
                        label_visibility="collapsed"
                    )
                pagamentos_a_confirmar.append({'id': row.id, 'data_pagamento': data_pagamento})

            if st.button("✅ Confirmar Baixa dos Itens Selecionados", type="primary", use_container_width=True):
                marcar_como_pago("entradas", pagamentos_a_confirmar)
                st.rerun()

with tab2:
    st.subheader("Despesas com Pagamento Pendente")
    df_pagar = carregar_dados("saidas", status="'Pendente'")

    if df_pagar.empty:
        st.info("👍 Ótimo! Não há nenhuma despesa pendente de pagamento.")
    else:
        total_a_pagar = df_pagar['valor'].sum()
        st.metric("Valor Total a Pagar", f"R$ {total_a_pagar:,.2f}")

        options_pagar = {f"ID {row.id} | {row.data.strftime('%d/%m/%Y')} | {row.descricao} | R$ {row.valor:,.2f}": row.id for index, row in df_pagar.iterrows()}
        lancamentos_pagar_selecionados = st.multiselect(
            "Selecione as despesas para dar baixa:",
            options=options_pagar.keys(),
            label_visibility="collapsed"
        )
        ids_pagar_selecionados = [options_pagar[key] for key in lancamentos_pagar_selecionados]

        if ids_pagar_selecionados:
            st.markdown("---")
            st.subheader("Confirmar Baixa de Saídas")
            pagamentos_saida_a_confirmar = []
            df_pagar_selecionados = df_pagar[df_pagar['id'].isin(ids_pagar_selecionados)]

            for _, row in df_pagar_selecionados.iterrows():
                cols = st.columns([3, 1])
                with cols[0]:
                    st.markdown(f"**Descrição:** {row.descricao} | **Valor:** R$ {row.valor:,.2f}")
                with cols[1]:
                    data_pagamento_saida = st.date_input("Data do Pagamento", value=date.today(), key=f"data_pagar_{row.id}", label_visibility="collapsed")
                pagamentos_saida_a_confirmar.append({'id': row.id, 'data_pagamento': data_pagamento_saida})

            if st.button("✅ Confirmar Baixa das Despesas Selecionadas", type="primary", use_container_width=True):
                marcar_como_pago("saidas", pagamentos_saida_a_confirmar)
                st.rerun()