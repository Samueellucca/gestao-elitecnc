import streamlit as st
import pandas as pd
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

@st.cache_data
def carregar_pendencias(tabela):
    """Carrega entradas ou saídas com status 'Pendente'."""
    try:
        query = f"SELECT * FROM {tabela} WHERE status = 'Pendente' ORDER BY data ASC"
        df = pd.read_sql_query(query, engine, parse_dates=['data'])
        return df
    except Exception as e:
        st.error(f"Erro ao carregar dados da tabela {tabela}: {e}")
        return pd.DataFrame()

def marcar_como_pago(tabela, ids_para_pagar):
    """Atualiza o status de uma lista de IDs para 'Pago'."""
    if not ids_para_pagar:
        return
    try:
        with engine.connect() as con:
            # Usamos a sintaxe 'IN' para atualizar múltiplos registros de uma vez
            query = text(f"UPDATE {tabela} SET status = 'Pago' WHERE id IN :ids")
            con.execute(query, {"ids": tuple(ids_para_pagar)})
            con.commit()
        st.success(f"{len(ids_para_pagar)} lançamento(s) da tabela '{tabela}' foram marcados como 'Pago'!")
        st.cache_data.clear() # Limpa o cache para recarregar os dados
    except Exception as e:
        st.error(f"Erro ao atualizar status: {e}")

# --- ABAS DE CONTROLE ---
tab1, tab2 = st.tabs(["📥 Contas a Receber (Entradas)", "📤 Contas a Pagar (Saídas)"])

with tab1:
    st.subheader("O.S. com Pagamento Pendente")
    df_receber = carregar_pendencias("entradas")

    if df_receber.empty:
        st.info("🎉 Ótima notícia! Não há nenhuma conta a receber pendente no momento.")
    else:
        total_a_receber = df_receber['valor_atendimento'].sum()
        st.metric("Valor Total a Receber", f"R$ {total_a_receber:,.2f}")

        # Adiciona uma coluna 'Pagar' para seleção
        df_receber['Pagar'] = False
        colunas_para_exibir = [
            'Pagar', 'data', 'ordem_servico', 'cliente', 'descricao_servico', 'valor_atendimento'
        ]
        
        # Usa o data_editor para permitir a seleção
        df_editado_receber = st.data_editor(
            df_receber[colunas_para_exibir],
            column_config={
                "Pagar": st.column_config.CheckboxColumn(required=True),
                "data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                "valor_atendimento": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f")
            },
            hide_index=True,
            use_container_width=True,
            key="editor_receber"
        )

        # Filtra os IDs selecionados
        ids_selecionados_receber = df_receber.loc[df_editado_receber['Pagar']].id.tolist()

        if st.button("✅ Dar Baixa nas Entradas Selecionadas", disabled=not ids_selecionados_receber, type="primary"):
            marcar_como_pago("entradas", ids_selecionados_receber)
            st.rerun()

with tab2:
    st.subheader("Despesas com Pagamento Pendente")
    df_pagar = carregar_pendencias("saidas")

    if df_pagar.empty:
        st.info("👍 Tudo certo! Não há nenhuma despesa pendente de pagamento.")
    else:
        total_a_pagar = df_pagar['valor'].sum()
        st.metric("Valor Total a Pagar", f"R$ {total_a_pagar:,.2f}")

        df_pagar['Pagar'] = False
        colunas_pagar_exibir = ['Pagar', 'data', 'descricao', 'valor']

        df_editado_pagar = st.data_editor(
            df_pagar[colunas_pagar_exibir],
            column_config={
                "Pagar": st.column_config.CheckboxColumn(required=True),
                "data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                "valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f")
            },
            hide_index=True,
            use_container_width=True,
            key="editor_pagar"
        )

        ids_selecionados_pagar = df_pagar.loc[df_editado_pagar['Pagar']].id.tolist()

        if st.button("✅ Dar Baixa nas Saídas Selecionadas", disabled=not ids_selecionados_pagar, type="primary"):
            marcar_como_pago("saidas", ids_selecionados_pagar)
            st.rerun()