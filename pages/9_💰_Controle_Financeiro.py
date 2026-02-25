import streamlit as st
import pandas as pd
import io
import re
from urllib.parse import quote
import plotly.express as px
from datetime import date, datetime, timedelta
from sqlalchemy import create_engine, text
from dateutil.relativedelta import relativedelta

# --- VERIFICAÇÃO DE LOGIN ---
if "authentication_status" not in st.session_state or not st.session_state["authentication_status"]:
    st.error("Acesso negado. Por favor, faça login na página inicial.")
    st.stop()

st.sidebar.image("logo.png", width=150)
st.sidebar.button("Sair", on_click=lambda: st.session_state.update({"authentication_status": None}))

# --- CONFIGURAÇÃO DA PÁGINA E CONEXÃO COM DB ---
st.set_page_config(page_title="Controle Financeiro", page_icon="💰", layout="wide")
st.title("💰 Controle Financeiro")
st.markdown("Gerencie suas contas a pagar e receber, realize baixas e negociações de forma centralizada.")

connection_url = st.secrets["database"]["connection_url"]
engine = create_engine(connection_url)

# --- FILTROS DE VISUALIZAÇÃO ---
# (Movido para dentro das abas ou topo para ficar mais limpo, veja abaixo)

# --- CORREÇÃO AUTOMÁTICA DE SCHEMA ---
try:
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE entradas ADD COLUMN IF NOT EXISTS data_pagamento TIMESTAMP"))
        conn.execute(text("ALTER TABLE saidas ADD COLUMN IF NOT EXISTS data_pagamento TIMESTAMP"))
        conn.commit()
except Exception as e:
    print(f"Erro ao tentar corrigir schema: {e}")

# --- FUNÇÕES DE DADOS ---

@st.cache_data(ttl=300)
def carregar_dados(tabela, status_list):
    """Carrega dados de uma tabela com um status específico."""
    if not status_list:
        return pd.DataFrame()
    try:
        status_str = ",".join([f"'{s}'" for s in status_list])
        query = f"SELECT * FROM {tabela} WHERE status IN ({status_str}) ORDER BY data ASC"
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

@st.cache_data(ttl=600)
def carregar_telefones_clientes():
    """Carrega nome e telefone dos clientes para contato."""
    try:
        df = pd.read_sql("SELECT nome, telefone FROM clientes", engine)
        return df
    except:
        return pd.DataFrame(columns=['nome', 'telefone'])

def marcar_como_pago(tabela, pagamentos):
    """Atualiza o status e a data de pagamento de uma lista de IDs."""
    if not pagamentos:
        return False
    try:
        with engine.connect() as con:
            trans = con.begin()
            try:
                for pagamento in pagamentos:
                    query = text(f"UPDATE {tabela} SET status = 'Pago', data_pagamento = :data_pagamento WHERE id = :id")
                    con.execute(query, {"data_pagamento": pagamento['data_pagamento'], "id": int(pagamento['id'])})
                trans.commit()
                st.toast(f"{len(pagamentos)} lançamento(s) baixado(s) com sucesso!", icon="✅")
                st.cache_data.clear() # Limpa o cache para recarregar os dados
                return True
            except Exception as e:
                trans.rollback()
                raise e
    except Exception as e:
        st.error(f"Erro ao atualizar status: {e}")
        return False

def processar_negociacao(tabela, ids_originais, novos_lancamentos):
    """
    Marca os IDs originais como 'Negociado' e insere os novos lançamentos.
    """
    if not ids_originais or not novos_lancamentos:
        st.error("Dados insuficientes para processar a negociação.")
        return False

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
                st.toast("Negociação realizada com sucesso!", icon="🤝")
                st.cache_data.clear()
                return True
            except Exception as e_inner:
                trans.rollback()
                st.error(f"Erro durante a transação da negociação: {e_inner}")
                return False
    except Exception as e_outer:
        st.error(f"Erro de conexão ao processar negociação: {e_outer}")
        return False


def get_next_os_number():
    """Busca o próximo número de O.S. disponível."""
    try:
        query = "SELECT MAX(CAST(ordem_servico AS INTEGER)) FROM entradas WHERE ordem_servico ~ '^[0-9]+$';"
        next_os = pd.read_sql(query, engine).iloc[0,0]
        return int(next_os) + 1 if next_os else 1
    except:
        return 1 # Fallback

# --- LAYOUT DE TOPO (Métricas e Filtro Global) ---
with st.container(border=True):
    st.subheader("📊 Visão Geral")
    col_m1, col_m2, col_m3, col_f_global = st.columns([1, 1, 1, 1.5])
    
    with col_f_global:
        status_opcoes = ["Pendente", "Pago", "Negociado", "Cancelado"]
        status_selecionados = st.multiselect("Status dos Lançamentos:", options=status_opcoes, default=["Pendente"])
    
    # Carrega dados e calcula métricas APÓS definir o filtro
    df_receber = carregar_dados("entradas", tuple(status_selecionados))
    df_pagar = carregar_dados("saidas", tuple(status_selecionados))
    
    total_receber = df_receber['valor_atendimento'].sum() if not df_receber.empty else 0.0
    total_pagar = df_pagar['valor'].sum() if not df_pagar.empty else 0.0
    saldo_previsto = total_receber - total_pagar

    col_m1.metric("📥 A Receber", f"R$ {total_receber:,.2f}", delta="Entradas", delta_color="normal")
    col_m2.metric("📤 A Pagar", f"R$ {total_pagar:,.2f}", delta="Saídas", delta_color="inverse")
    col_m3.metric("💰 Saldo Previsto", f"R$ {saldo_previsto:,.2f}", delta="Líquido", delta_color="normal" if saldo_previsto >= 0 else "inverse")

# --- ABAS ---
tab_receber, tab_pagar = st.tabs(["📥 Contas a Receber (Entradas)", "📤 Contas a Pagar (Saídas)"])

def get_status_visual(row):
    s = row.get('status', 'Pendente')
    if s == 'Pago': return "✅ Pago"
    if s == 'Negociado': return "🤝 Negociado"
    if s == 'Cancelado': return "🚫 Cancelado"
    if pd.notnull(row['data']) and row['data'].date() < date.today():
        return "🔴 Atrasado"
    return "🟢 No Prazo"

# ==============================================================================
# ABA: CONTAS A RECEBER
# ==============================================================================
with tab_receber:
    st.subheader("Gerenciar Recebimentos")
    
    # --- Filtros ---
    with st.container(border=True):
        c_f1, c_f2 = st.columns([1, 1])
        clientes_pendentes = carregar_clientes_com_pendencias()
        filtro_cliente = c_f1.selectbox("🔍 Filtrar por Cliente", ["Todos"] + clientes_pendentes)

        min_date = df_receber['data'].min().date() if not df_receber.empty else date.today()
        max_date = df_receber['data'].max().date() if not df_receber.empty else date.today()
        filtro_data = c_f2.date_input("Período de Vencimento", [min_date, max_date])

    # --- Aplicação dos Filtros ---
    df_r_view = df_receber.copy()
    if filtro_cliente != "Todos" and 'cliente' in df_r_view.columns:
        df_r_view = df_r_view[df_r_view['cliente'] == filtro_cliente]
    
    if len(filtro_data) == 2 and 'data' in df_r_view.columns:
        df_r_view = df_r_view[(df_r_view['data'].dt.date >= filtro_data[0]) & (df_r_view['data'].dt.date <= filtro_data[1])]

    # --- Cruzamento com Telefones ---
    df_telefones = carregar_telefones_clientes()
    if not df_telefones.empty and not df_r_view.empty and 'cliente' in df_r_view.columns:
        df_r_view = pd.merge(df_r_view, df_telefones, left_on='cliente', right_on='nome', how='left')

    if df_r_view.empty:
        st.info("Nenhuma conta a receber encontrada com os filtros atuais.")
    else:
        # Coluna visual de status
        df_r_view['status_venc'] = df_r_view.apply(get_status_visual, axis=1)
        df_r_view['selecionar'] = False

        # --- Destaque de Vencidos ---
        vencidos_r = df_r_view[(df_r_view['data'].dt.date < date.today()) & (df_r_view['status'] == 'Pendente')]
        if not vencidos_r.empty:
            st.error(f"🚨 Atenção: Existem {len(vencidos_r)} conta(s) vencida(s) nesta lista, totalizando R$ {vencidos_r['valor_atendimento'].sum():,.2f}!", icon="⚠️")

        col_chart, col_table = st.columns([1, 3])
        
        with col_chart:
            with st.container(border=True):
                st.markdown("##### Distribuição")
                fig_receber = px.pie(
                    df_r_view,
                    values='valor_atendimento',
                    names='cliente',
                    hole=0.5,
                    height=300
                )
                fig_receber.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0))
                st.plotly_chart(fig_receber, use_container_width=True)
                
                # Botão de Exportação (Movido para cá para economizar espaço)
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    df_r_view.drop(columns=['selecionar'], errors='ignore').to_excel(writer, index=False, sheet_name='Receber')
                st.download_button(
                    label="📥 Baixar Excel",
                    data=buffer.getvalue(),
                    file_name=f"Contas_Receber_{date.today()}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
            )

        with col_table:
            st.write("Selecione os itens na tabela abaixo para realizar ações:")
            edited_r = st.data_editor(
                df_r_view[['selecionar', 'status_venc', 'data', 'ordem_servico', 'cliente', 'valor_atendimento', 'id', 'telefone']],
                column_config={
                "selecionar": st.column_config.CheckboxColumn("✅", width="small"),
                "status_venc": st.column_config.TextColumn("Status", width="medium"),
                "data": st.column_config.DateColumn("Vencimento", format="DD/MM/YYYY"),
                "ordem_servico": st.column_config.TextColumn("O.S."),
                "cliente": "Cliente",
                "valor_atendimento": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f"),
                "id": None,
                "telefone": None, # Oculta o telefone na visualização da tabela
                },
                hide_index=True,
                use_container_width=True,
                key="editor_receber",
                height=400
            )
            # Totalizador discreto abaixo da tabela
            st.caption(f"🧾 Total Listado na Tabela: **R$ {df_r_view['valor_atendimento'].sum():,.2f}**")

        selecionados = edited_r[edited_r['selecionar']]
        
        # --- Área de Ações ---
        if not selecionados.empty:
            st.markdown("---")
            with st.container(border=True):
                st.subheader("⚡ Painel de Ações")
                total_sel = selecionados['valor_atendimento'].sum()
                qtd_sel = len(selecionados)
                
                col_resumo, col_acao = st.columns([1, 2])
                
                with col_resumo:
                    st.info(f"**{qtd_sel}** itens selecionados\n\nTotal: **R$ {total_sel:,.2f}**")
                
                with col_acao:
                    acao = st.radio("Escolha a ação:", ["Baixar (Recebimento)", "Negociar (Desconto/Parcelamento)", "📞 Enviar Cobrança (WhatsApp)", "Restaurar Status (Pendente)"], horizontal=True)
                
                if acao == "Baixar (Recebimento)":
                    c_b1, c_b2 = st.columns(2)
                    dt_baixa = c_b1.date_input("Data do Recebimento", date.today())
                    val_recebido = c_b2.number_input("Valor Recebido (R$)", value=float(total_sel), min_value=0.0, step=10.0, format="%.2f")
                    
                    desconto = total_sel - val_recebido
                    if abs(desconto) > 0.01:
                        if desconto > 0:
                            st.info(f"📉 Desconto de **R$ {desconto:,.2f}** será aplicado proporcionalmente aos itens selecionados.")
                        else:
                            st.warning(f"📈 Acréscimo de **R$ {abs(desconto):,.2f}** será aplicado proporcionalmente.")

                    if st.button(f"✅ Confirmar Baixa", type="primary", use_container_width=True):
                        # Se houver diferença de valor (desconto ou acréscimo), atualiza os registros antes de baixar
                        if abs(desconto) > 0.01 and total_sel > 0:
                            ratio = val_recebido / total_sel
                            try:
                                with engine.connect() as con:
                                    for _, row in selecionados.iterrows():
                                        novo_valor = float(row['valor_atendimento'] * ratio)
                                        con.execute(
                                            text("UPDATE entradas SET valor_atendimento = :val WHERE id = :id"),
                                            {"val": novo_valor, "id": int(row['id'])}
                                        )
                                    con.commit()
                            except Exception as e:
                                st.error(f"Erro ao atualizar valores com desconto: {e}")
                                st.stop()

                        dt_baixa_full = datetime.combine(dt_baixa, datetime.min.time())
                        itens = [{'id': int(row['id']), 'data_pagamento': dt_baixa_full} for _, row in selecionados.iterrows()]
                        if marcar_como_pago("entradas", itens):
                            st.rerun()
                
                elif acao == "Negociar (Desconto/Parcelamento)":
                    tipo_neg = st.selectbox("Tipo de Negociação", ["Aplicar Desconto (À Vista)", "Parcelar Valor"])
                    
                    if tipo_neg == "Aplicar Desconto (À Vista)":
                        perc = st.number_input("Desconto (%)", 0.0, 100.0, 5.0)
                        novo_valor = total_sel * (1 - perc/100)
                        st.info(f"Valor original: R$ {total_sel:,.2f} ➝ **Novo Valor: R$ {novo_valor:,.2f}**")
                        st.warning("⚠️ Atenção: Isso arquivará os lançamentos selecionados como 'Negociado' e criará uma NOVA O.S. com o valor ajustado.")
                        
                        if st.button("🤝 Confirmar Negociação com Desconto", use_container_width=True):
                            ids = selecionados['id'].tolist()
                            cli = selecionados.iloc[0]['cliente']
                            novo_lanc = {
                                'data': datetime.now(),
                                'ordem_servico': str(get_next_os_number()),
                                'cliente': cli,
                                'descricao_servico': f"Negociação ({qtd_sel} itens) - Desconto {perc}%",
                                'valor_atendimento': novo_valor,
                                'status': 'Pendente',
                                'usuario_lancamento': st.session_state.get("username", "n/a")
                            }
                            if processar_negociacao("entradas", ids, [novo_lanc]):
                                st.rerun()
                            
                    elif tipo_neg == "Parcelar Valor":
                        n_parc = st.number_input("Nº Parcelas", 2, 24, 2)
                        v_parc = total_sel / n_parc
                        st.info(f"Total: R$ {total_sel:,.2f} ➝ **{n_parc}x de R$ {v_parc:,.2f}**")
                        st.warning("⚠️ Atenção: Isso arquivará os lançamentos selecionados e criará NOVAS O.S. para cada parcela.")
                        
                        if st.button("💳 Confirmar Parcelamento", use_container_width=True):
                            ids = selecionados['id'].tolist()
                            cli = selecionados.iloc[0]['cliente']
                            base_os = get_next_os_number()
                            novos = []
                            for i in range(n_parc):
                                novos.append({
                                    'data': datetime.now() + relativedelta(months=i),
                                    'ordem_servico': f"{base_os}-{i+1}",
                                    'cliente': cli,
                                    'descricao_servico': f"Parcela {i+1}/{n_parc} - Ref. Negociação",
                                    'valor_atendimento': v_parc,
                                    'status': 'Pendente',
                                    'usuario_lancamento': st.session_state.get("username", "n/a")
                                })
                            if processar_negociacao("entradas", ids, novos):
                                st.rerun()

                elif acao == "📞 Enviar Cobrança (WhatsApp)":
                    st.markdown("##### Links de Cobrança Gerados:")
                    
                    # Agrupa por cliente para mandar uma mensagem única com todos os itens dele
                    grupos_clientes = selecionados.groupby('cliente')
                    
                    for cliente_nome, grupo in grupos_clientes:
                        telefone = grupo.iloc[0]['telefone']
                        total_cliente = grupo['valor_atendimento'].sum()
                        lista_os = ", ".join(grupo['ordem_servico'].astype(str).tolist())
                        qtd_itens = len(grupo)
                        
                        if pd.isna(telefone) or not telefone:
                            st.warning(f"⚠️ {cliente_nome}: Cliente sem telefone cadastrado.")
                        else:
                            # Limpa e formata o telefone
                            numero_limpo = re.sub(r'\D', '', str(telefone))
                            if not numero_limpo.startswith('55'):
                                numero_limpo = '55' + numero_limpo
                            
                            # Cria a mensagem
                            msg_texto = f"Olá {cliente_nome}, tudo bem? \nConsta em nosso sistema pendência(s) referente(s) à(s) O.S. {lista_os}, totalizando R$ {total_cliente:,.2f}. \nPoderia nos dar uma previsão de pagamento?"
                            msg_encoded = quote(msg_texto)
                            link_zap = f"https://wa.me/{numero_limpo}?text={msg_encoded}"
                            
                            st.markdown(
                                f"""<a href="{link_zap}" target="_blank" style="text-decoration: none;">
                                <button style="background-color:#25D366; color:white; border:none; padding:8px 16px; border-radius:5px; cursor:pointer; font-weight:bold;">
                                📲 Enviar para {cliente_nome} (R$ {total_cliente:,.2f})
                                </button></a>""", unsafe_allow_html=True
                            )

                elif acao == "Restaurar Status (Pendente)":
                    st.warning("⚠️ Esta ação reverterá o status dos itens selecionados para 'Pendente'. Utilize caso tenha excluído uma negociação e queira recuperar os lançamentos originais.")
                    if st.button("🔄 Confirmar Restauração", use_container_width=True):
                        ids = tuple(selecionados['id'].tolist())
                        if ids:
                            try:
                                with engine.connect() as con:
                                    query_restaurar = text("UPDATE entradas SET status = 'Pendente' WHERE id IN :ids")
                                    con.execute(query_restaurar, {"ids": ids})
                                    con.commit()
                                st.success("Itens restaurados para 'Pendente' com sucesso!")
                                st.cache_data.clear()
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao restaurar itens: {e}")

# ==============================================================================
# ABA: CONTAS A PAGAR
# ==============================================================================
with tab_pagar:
    st.subheader("Gerenciar Pagamentos (Despesas)")
    
    if df_pagar.empty:
        st.info("Nenhuma conta a pagar pendente.")
    else:
        df_p_view = df_pagar.copy()
        df_p_view['status_venc'] = df_p_view.apply(get_status_visual, axis=1)
        df_p_view['selecionar'] = False

        # --- Destaque de Vencidos ---
        vencidos_p = df_p_view[(df_p_view['data'].dt.date < date.today()) & (df_p_view['status'] == 'Pendente')]
        if not vencidos_p.empty:
            st.error(f"🚨 Atenção: Existem {len(vencidos_p)} conta(s) vencida(s) nesta lista, totalizando R$ {vencidos_p['valor'].sum():,.2f}!", icon="⚠️")

        col_top_p1, col_top_p2 = st.columns([4, 1])
        with col_top_p2:
            # --- Botão de Exportação ---
            buffer_p = io.BytesIO()
            with pd.ExcelWriter(buffer_p, engine='openpyxl') as writer:
                df_p_view.drop(columns=['selecionar'], errors='ignore').to_excel(writer, index=False, sheet_name='Pagar')
            st.download_button(
                label="📥 Baixar Excel",
                data=buffer_p.getvalue(),
                file_name=f"Contas_Pagar_{date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

        edited_p = st.data_editor(
            df_p_view[['selecionar', 'status_venc', 'data', 'descricao', 'valor', 'id']],
            column_config={
                "selecionar": st.column_config.CheckboxColumn("✅", width="small"),
                "status_venc": st.column_config.TextColumn("Status", width="medium"),
                "data": st.column_config.DateColumn("Vencimento", format="DD/MM/YYYY"),
                "descricao": "Descrição",
                "valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f"),
                "id": None,
            },
            hide_index=True,
            use_container_width=True,
            key="editor_pagar"
        )

        # --- Totalizador ---
        st.caption(f"🧾 Total Listado: **R$ {df_p_view['valor'].sum():,.2f}**")

        selecionados_p = edited_p[edited_p['selecionar']]

        if not selecionados_p.empty:
            st.markdown("---")
            with st.container(border=True):
                st.subheader("⚡ Painel de Pagamento")
                total_p = selecionados_p['valor'].sum()
                
                c_pag1, c_pag2, c_pag3 = st.columns([1, 1, 1])
                c_pag1.metric("Total Selecionado", f"R$ {total_p:,.2f}")
                
                dt_pag = c_pag2.date_input("Data do Pagamento", date.today(), key="dt_pag_saida")
                
                c_pag3.write("") # Espaçamento
                c_pag3.write("")
                if c_pag3.button(f"✅ Confirmar Baixa", type="primary", use_container_width=True):
                    dt_pag_full = datetime.combine(dt_pag, datetime.min.time())
                    itens = [{'id': int(row['id']), 'data_pagamento': dt_pag_full} for _, row in selecionados_p.iterrows()]
                    if marcar_como_pago("saidas", itens):
                        st.rerun()