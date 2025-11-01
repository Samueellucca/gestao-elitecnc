import streamlit as st
import pandas as pd
from datetime import date, datetime
from sqlalchemy import create_engine, text

# --- VERIFICAÇÃO DE LOGIN ---
if "authentication_status" not in st.session_state or not st.session_state["authentication_status"]:
    st.error("Acesso negado. Por favor, faça login na página inicial.")
    st.stop()
from dateutil.relativedelta import relativedelta

st.sidebar.image("logo.png", width=150)
st.sidebar.button("Sair", on_click=lambda: st.session_state.update({"authentication_status": None}))

# --- CONFIGURAÇÃO DA PÁGINA E CONEXÃO COM DB ---
st.set_page_config(page_title="Controle Financeiro", page_icon="💰", layout="wide")
st.title("💰 Controle Financeiro")
st.markdown("Visão consolidada para gerenciamento de contas a pagar e a receber. Dê baixa em pagamentos, negocie valores e mantenha seu fluxo de caixa atualizado.")

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

@st.cache_data(ttl=600)
def carregar_clientes_com_pendencias():
    """Carrega apenas clientes que têm pendências financeiras."""
    try:
        query = """
            SELECT DISTINCT cliente FROM entradas 
            WHERE status = 'Pendente' AND cliente IS NOT NULL ORDER BY cliente;
        """
        return pd.read_sql_query(query, engine)['cliente'].tolist()
    except:
        return []

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

def processar_negociacao(tabela, ids_originais, novos_lancamentos):
    """
    Marca os IDs originais como 'Negociado' e insere os novos lançamentos.
    """
    if not ids_originais or not novos_lancamentos:
        st.error("Dados insuficientes para processar a negociação.")
        return

    try:
        with engine.connect() as con:
            trans = con.begin()
            try:
                # 1. Atualiza o status dos lançamentos originais para 'Negociado'
                ids_tuple = tuple(ids_originais)
                query_update = text(f"UPDATE {tabela} SET status = 'Negociado' WHERE id IN :ids")
                con.execute(query_update, {"ids": ids_tuple})

                # 2. Insere os novos lançamentos (parcelas ou valor com desconto)
                df_novos = pd.DataFrame(novos_lancamentos)
                
                # Garante que apenas colunas existentes na tabela sejam inseridas
                colunas_tabela = pd.read_sql(f"SELECT * FROM {tabela} LIMIT 0", con).columns
                df_novos_filtrado = df_novos[[col for col in df_novos.columns if col in colunas_tabela]]

                df_novos_filtrado.to_sql(tabela, con, if_exists='append', index=False)

                trans.commit()
                st.success("Negociação processada com sucesso! Novos lançamentos pendentes foram criados.")
                st.cache_data.clear()
            except Exception as e_inner:
                trans.rollback()
                st.error(f"Erro durante a transação da negociação: {e_inner}")
    except Exception as e_outer:
        st.error(f"Erro de conexão ao processar negociação: {e_outer}")


def get_next_os_number():
    """Busca o próximo número de O.S. disponível."""
    try:
        query = "SELECT MAX(CAST(ordem_servico AS INTEGER)) FROM entradas WHERE ordem_servico ~ '^[0-9]+$';"
        next_os = pd.read_sql(query, engine).iloc[0,0]
        return int(next_os) + 1 if next_os else 1
    except:
        return 1 # Fallback

def renderizar_aba_financeira(tipo_conta, df_dados, clientes_filtro=None):
    """
    Função reutilizável para renderizar a interface de Contas a Pagar ou a Receber.
    """
    if tipo_conta == "receber":
        titulo = "O.S. com Pagamento Pendente"
        col_valor = "valor_atendimento"
        col_desc = "cliente"
        texto_selecao = "Selecione as O.S. para dar baixa:"
        texto_confirmacao = "Confirmar Baixa das Entradas"
        tabela_db = "entradas"
    else:
        titulo = "Despesas com Pagamento Pendente"
        col_valor = "valor"
        col_desc = "descricao"
        texto_selecao = "Selecione as despesas para dar baixa:"
        texto_confirmacao = "Confirmar Baixa das Despesas"
        tabela_db = "saidas"

    st.subheader(titulo)

    # --- Filtros ---
    df_filtrado = df_dados.copy()

    with st.expander("🔍 Filtros e Opções"):
        filtros = st.columns([2, 1])
        if tipo_conta == "receber" and clientes_filtro:
            with filtros[0]:
                cliente_selecionado = st.selectbox("Filtrar por Cliente", options=["Todos"] + clientes_filtro, key=f"filtro_cliente_{tabela_db}")
                if cliente_selecionado != "Todos":
                    df_filtrado = df_filtrado[df_filtrado['cliente'] == cliente_selecionado]

        with filtros[1]:
            if st.checkbox("Filtrar por período?", key=f"chk_periodo_{tabela_db}"):
                min_data = df_filtrado['data'].min().date() if not df_filtrado.empty else date.today()
                max_data = df_filtrado['data'].max().date() if not df_filtrado.empty else date.today()
                date_range = st.date_input("Período", [min_data, max_data], key=f"date_periodo_{tabela_db}")
                if len(date_range) == 2:
                    data_inicio, data_fim = date_range
                    df_filtrado = df_filtrado[(df_filtrado['data'].dt.date >= data_inicio) & (df_filtrado['data'].dt.date <= data_fim)]

    if df_filtrado.empty:
        st.info(f"🎉 Ótima notícia! Não há nenhuma conta a {tipo_conta} pendente com os filtros aplicados.")
        return

    total_pendente = df_filtrado[col_valor].sum()
    st.metric(f"Valor Total a {tipo_conta.capitalize()}", f"R$ {total_pendente:,.2f}")

    # Usar o editor de dados para seleção
    df_filtrado['Selecionar'] = False
    colunas_visiveis = ['Selecionar', 'data', col_desc, col_valor]
    if tipo_conta == "receber":
        colunas_visiveis.insert(3, 'ordem_servico')

    st.write(texto_selecao)
    df_editado = st.data_editor(
        df_filtrado[colunas_visiveis],
        hide_index=True,
        column_config={
            "data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
            col_valor: st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f"),
        },
        key=f"editor_{tabela_db}"
    )

    df_selecionados = df_editado[df_editado['Selecionar']]

    if not df_selecionados.empty:
        with st.container(border=True):
            total_selecionado = df_filtrado.loc[df_selecionados.index][col_valor].sum()
            st.subheader(f"Ações para {len(df_selecionados)} Item(s) Selecionado(s)")
            st.metric("Valor Total Selecionado", f"R$ {total_selecionado:,.2f}")

            tipo_pagamento = st.radio("Escolha uma ação:", ["✅ Baixa Direta", "💸 À Vista com Desconto", "💳 Parcelado"], horizontal=True, key=f"tipo_pag_{tabela_db}")

            if tipo_pagamento == "✅ Baixa Direta":
                data_pagamento_geral = st.date_input(
                    "Data de Pagamento/Recebimento",
                    value=date.today(),
                    key=f"data_geral_{tabela_db}"
                )
                if st.button(f"Confirmar Baixa de {len(df_selecionados)} Itens", type="primary", use_container_width=True):
                    ids_selecionados = df_filtrado.loc[df_selecionados.index]['id'].tolist()
                    pagamentos_a_confirmar = [{'id': id_val, 'data_pagamento': data_pagamento_geral} for id_val in ids_selecionados]
                    marcar_como_pago(tabela_db, pagamentos_a_confirmar)
                    st.rerun()

            elif tipo_pagamento == "💸 À Vista com Desconto":
                col_desc1, col_desc2 = st.columns([1, 2])
                with col_desc1:
                    desconto_percent = st.number_input("Desconto (%)", min_value=0.0, max_value=100.0, value=5.0, step=1.0)
                with col_desc2:
                    valor_com_desconto = total_selecionado * (1 - desconto_percent / 100)
                    st.metric("Valor Final com Desconto", f"R$ {valor_com_desconto:,.2f}")

                if st.button("Gerar Fatura Única com Desconto", type="primary", use_container_width=True):
                    ids_originais = df_filtrado.loc[df_selecionados.index]['id'].tolist()
                    cliente_nome = df_filtrado.loc[df_selecionados.index].iloc[0]['cliente']
                    next_os = get_next_os_number()

                    novo_lancamento = {
                        'data': datetime.now(),
                        'ordem_servico': str(next_os),
                        'cliente': cliente_nome,
                        'descricao_servico': f"Fatura com desconto de {desconto_percent}% sobre {len(ids_originais)} O.S.",
                        'valor_atendimento': valor_com_desconto,
                        'status': 'Pendente',
                        'usuario_lancamento': st.session_state.get("username", "n/a")
                    }
                    processar_negociacao(tabela_db, ids_originais, [novo_lancamento])
                    st.rerun()

            elif tipo_pagamento == "💳 Parcelado":
                col_parc1, col_parc2 = st.columns([1, 2])
                with col_parc1:
                    num_parcelas = st.number_input("Nº de Parcelas", min_value=2, max_value=24, value=3, step=1)
                with col_parc2:
                    valor_parcela = total_selecionado / num_parcelas
                    st.metric(f"Valor de cada uma das {num_parcelas} parcelas", f"R$ {valor_parcela:,.2f}")

                if st.button(f"Gerar {num_parcelas} Parcelas", type="primary", use_container_width=True):
                    ids_originais = df_filtrado.loc[df_selecionados.index]['id'].tolist()
                    cliente_nome = df_filtrado.loc[df_selecionados.index].iloc[0]['cliente']
                    next_os_base = get_next_os_number()
                    
                    novos_lancamentos = []
                    for i in range(num_parcelas):
                        data_vencimento = datetime.now() + relativedelta(months=i)
                        lancamento_parcela = {
                            'data': data_vencimento,
                            'ordem_servico': f"{next_os_base}-{i+1}",
                            'cliente': cliente_nome,
                            'descricao_servico': f"Parcela {i+1}/{num_parcelas} da negociação de {len(ids_originais)} O.S.",
                            'valor_atendimento': valor_parcela,
                            'status': 'Pendente',
                            'usuario_lancamento': st.session_state.get("username", "n/a")
                        }
                        novos_lancamentos.append(lancamento_parcela)
                    
                    processar_negociacao(tabela_db, ids_originais, novos_lancamentos)
                    st.rerun()

# --- ABAS DE CONTROLE ---
tab1, tab2 = st.tabs(["📥 Contas a Receber (Entradas)", "📤 Contas a Pagar (Saídas)"])

with tab1:
    df_receber = carregar_dados("entradas", status="'Pendente'")
    clientes_com_pendencias = carregar_clientes_com_pendencias()
    renderizar_aba_financeira("receber", df_receber, clientes_com_pendencias)

with tab2:
    df_pagar = carregar_dados("saidas", status="'Pendente'")
    renderizar_aba_financeira("pagar", df_pagar) # A negociação só se aplica a 'receber' por enquanto