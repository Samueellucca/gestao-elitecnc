import streamlit as st
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine, text

# --- VERIFICAÇÃO DE LOGIN ---
if "authentication_status" not in st.session_state or not st.session_state["authentication_status"]:
    st.error("Acesso negado. Por favor, faça login na página inicial.")
    st.stop()

st.sidebar.image("logo.png", width=150)
st.sidebar.button("Sair", on_click=lambda: st.session_state.update({"authentication_status": None}))

# --- CONFIGURAÇÃO DA PÁGINA E CONEXÃO COM DB ---
st.set_page_config(page_title="Controle de Estoque", page_icon="📦", layout="wide")
st.title("📦 Controle de Estoque")

connection_url = st.secrets["database"]["connection_url"]
engine = create_engine(connection_url)

# --- FUNÇÕES DE DADOS ---

@st.cache_data(ttl=300)
def carregar_componentes():
    """Carrega todos os componentes do estoque."""
    try:
        return pd.read_sql("SELECT * FROM estoque_componentes ORDER BY nome", engine)
    except Exception as e:
        st.error(f"Erro ao carregar componentes: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=300)
def carregar_movimentacoes():
    """Carrega o histórico de movimentações."""
    try:
        query = """
        SELECT m.data, c.nome as componente, m.tipo_movimento, m.local, m.quantidade, m.observacao, m.usuario_lancamento
        FROM estoque_movimentacao m
        JOIN estoque_componentes c ON m.componente_id = c.id
        ORDER BY m.data DESC
        """
        return pd.read_sql(query, engine, parse_dates=['data'])
    except Exception as e:
        st.error(f"Erro ao carregar movimentações: {e}")
        return pd.DataFrame()

def executar_movimentacao(componente_id, tipo_movimento, local, quantidade, observacao, usuario):
    """Registra uma movimentação e atualiza o saldo do componente."""
    if not componente_id or not tipo_movimento or not local or quantidade <= 0:
        st.error("Todos os campos são obrigatórios e a quantidade deve ser maior que zero.")
        return

    coluna_qtd = f"qtd_{local.lower().replace(' ', '_').replace('ê', 'e').replace('ó', 'o')}" # qtd_laboratorio ou qtd_assistencia_tecnica

    try:
        with engine.connect() as con:
            # Inicia uma transação
            trans = con.begin()
            try:
                # 1. Verifica o saldo atual
                saldo_atual_result = con.execute(text(f"SELECT {coluna_qtd} FROM estoque_componentes WHERE id = :id"), {"id": componente_id}).scalar_one_or_none()

                if tipo_movimento == 'Saída' and (saldo_atual_result is None or saldo_atual_result < quantidade):
                    st.error(f"Estoque insuficiente em '{local}'. Saldo atual: {saldo_atual_result or 0}.")
                    trans.rollback() # Desfaz a transação
                    return

                # 2. Atualiza o saldo do componente
                operador = "+" if tipo_movimento == 'Entrada' else "-"
                update_query = text(f"UPDATE estoque_componentes SET {coluna_qtd} = {coluna_qtd} {operador} :quantidade WHERE id = :id")
                con.execute(update_query, {"quantidade": quantidade, "id": componente_id})

                # 3. Insere o registro da movimentação
                mov_query = text("""
                    INSERT INTO estoque_movimentacao (componente_id, data, tipo_movimento, local, quantidade, observacao, usuario_lancamento)
                    VALUES (:comp_id, :data, :tipo, :local, :qtd, :obs, :user)
                """)
                con.execute(mov_query, {
                    "comp_id": componente_id, "data": datetime.now(), "tipo": tipo_movimento,
                    "local": local, "qtd": quantidade, "obs": observacao, "user": usuario
                })

                trans.commit() # Confirma a transação
                st.success(f"{tipo_movimento} de {quantidade} unidade(s) registrada com sucesso!")
                st.cache_data.clear()
            except Exception as e:
                trans.rollback() # Desfaz em caso de erro
                st.error(f"Erro na transação: {e}")

    except Exception as e:
        st.error(f"Erro de conexão com o banco de dados: {e}")

def deletar_componente(id_componente):
    """Exclui um componente do estoque. A movimentação é excluída em cascata pelo DB."""
    try:
        with engine.connect() as con:
            con.execute(text("DELETE FROM estoque_componentes WHERE id = :id"), {"id": id_componente})
            con.commit()
        st.success("Componente excluído com sucesso!")
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Erro ao excluir componente: {e}")

def atualizar_componente(id_componente, dados):
    """Atualiza os dados de um componente no estoque."""
    try:
        with engine.connect() as con:
            set_clause = ", ".join([f"{key} = :{key}" for key in dados.keys()])
            dados['id'] = id_componente
            query = text(f"UPDATE estoque_componentes SET {set_clause} WHERE id = :id")
            con.execute(query, dados)
            con.commit()
        st.success("Componente atualizado com sucesso!")
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Erro ao atualizar componente: {e}")


# --- CARREGANDO DADOS ---
df_componentes = carregar_componentes()
df_movimentacoes = carregar_movimentacoes()

# --- ABAS ---
tab_geral, tab_gerenciar, tab_movimentar, tab_historico = st.tabs([
    "📊 Visão Geral",
    "➕ Gerenciar Componentes",
    "🔄 Movimentar Estoque",
    "📜 Histórico de Movimentação"
])

# --- GERENCIAMENTO DE ESTADO DE EDIÇÃO ---
if 'edit_stock_id' not in st.session_state:
    st.session_state.edit_stock_id = None

edit_data = None
if st.session_state.edit_stock_id:
    try:
        edit_df = df_componentes[df_componentes['id'] == st.session_state.edit_stock_id]
        if not edit_df.empty:
            edit_data = edit_df.iloc[0].to_dict()
    except Exception as e:
        st.error(f"Erro ao carregar dados para edição: {e}")
        st.session_state.edit_stock_id = None

# --- ABA 1: VISÃO GERAL E ALERTAS ---
with tab_geral:
    st.subheader("Visão Geral do Estoque")

    if df_componentes.empty:
        st.info("Nenhum componente cadastrado. Adicione componentes na aba 'Gerenciar Componentes'.")
    else:
        # Botão para exportar os dados para CSV (sem a coluna 'id')
        df_export = df_componentes.drop(columns=['id'])
        csv_buffer = df_export.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')
        st.download_button(
            label="📥 Exportar para CSV",
            data=csv_buffer,
            file_name=f"estoque_componentes_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            help="Baixa a lista completa de componentes, incluindo o ID, em um arquivo CSV."
        )
        st.markdown("---")

        # Adiciona a coluna de estoque total para visualização
        df_componentes['estoque_total'] = df_componentes['qtd_laboratorio'] + df_componentes['qtd_assistencia']

        # Exibe o dataframe na tela (sem a coluna de ID para uma visualização mais limpa)
        st.dataframe(
            df_componentes[['nome', 'categoria', 'qtd_laboratorio', 'qtd_assistencia', 'estoque_total', 'estoque_minimo']],
            use_container_width=True,
            hide_index=True,
            column_config={
                "nome": "Componente",
                "categoria": "Categoria",
                "qtd_laboratorio": "Qtd. Laboratório",
                "qtd_assistencia": "Qtd. Assistência Técnica",
                "estoque_total": st.column_config.NumberColumn("Estoque Total", format="%d"),
                "estoque_minimo": st.column_config.NumberColumn("Estoque Mínimo", format="%d"),
            }
        )

        st.markdown("---")
        st.subheader("🚨 Alertas de Estoque Mínimo")
        df_alerta = df_componentes[df_componentes['estoque_total'] <= df_componentes['estoque_minimo']]

        if df_alerta.empty:
            st.success("✅ Tudo certo! Nenhum item está abaixo do estoque mínimo.")
        else:
            st.warning(f"Atenção! {len(df_alerta)} componente(s) estão abaixo do nível mínimo de estoque.")
            st.dataframe(
                df_alerta[['nome', 'estoque_total', 'estoque_minimo']],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "nome": "Componente",
                    "estoque_total": "Estoque Atual",
                    "estoque_minimo": "Estoque Mínimo"
                }
            )

# --- ABA 2: GERENCIAR COMPONENTES ---
with tab_gerenciar:
    st.subheader("Adicionar ou Editar Componente")
    if edit_data:
        st.info(f"📝 Editando componente: **{edit_data.get('nome')}** (ID: {st.session_state.edit_stock_id})")

    # --- Valores padrão para o formulário (novo ou edição) ---
    nome_default = edit_data.get('nome', '') if edit_data else ''
    categoria_default = edit_data.get('categoria', '') if edit_data else ''
    estoque_minimo_default = int(edit_data.get('estoque_minimo', 1)) if edit_data else 1
    qtd_lab_default = int(edit_data.get('qtd_laboratorio', 0)) if edit_data else 0
    qtd_assist_default = int(edit_data.get('qtd_assistencia', 0)) if edit_data else 0

    with st.expander("📤 Importar Componentes via CSV"):
        st.info(
            "**Instruções para Importação/Atualização:**\n"
            "1. Prepare uma planilha CSV com as colunas: `nome`, `categoria`, `estoque_minimo`, `qtd_laboratorio`, `qtd_assistencia`.\n"
            "2. O sistema irá **criar** novos itens ou **atualizar** os existentes com base na coluna `nome`.\n"
            "3. Use o botão 'Exportar para CSV' acima como modelo para o seu arquivo."
        )
        uploaded_file = st.file_uploader("Selecione o arquivo CSV", type="csv")

        if uploaded_file is not None:
            try:
                # Tenta detectar o separador (;) ou (,)
                df_csv = pd.read_csv(uploaded_file, sep=None, engine='python', on_bad_lines='warn')
                if len(df_csv.columns) == 1:
                    # Se a detecção automática falhar e resultar em uma única coluna, tenta os separadores comuns
                    uploaded_file.seek(0) # Volta ao início do arquivo
                    try:
                        df_csv = pd.read_csv(uploaded_file, sep=';')
                    except:
                        uploaded_file.seek(0)
                        df_csv = pd.read_csv(uploaded_file, sep=',')

                required_columns = {'nome'} # Apenas 'nome' é estritamente necessário para novos itens
                
                if not required_columns.issubset(df_csv.columns):
                    st.error(f"O arquivo CSV precisa ter pelo menos a coluna 'nome'. Verifique se o separador é ponto e vírgula (;) ou vírgula (,).")
                else:
                    st.write("Pré-visualização dos dados a serem importados:")
                    st.dataframe(df_csv)

                    if st.button("Confirmar Importação dos Dados", type="primary"):
                        with st.spinner("Importando dados..."):
                            itens_processados = 0

                            # Preenche valores nulos nas colunas numéricas com 0
                            num_cols = ['estoque_minimo', 'qtd_laboratorio', 'qtd_assistencia']
                            for col in num_cols:
                                if col in df_csv.columns:
                                    df_csv[col] = pd.to_numeric(df_csv[col], errors='coerce').fillna(0)

                            with engine.connect() as con:
                                trans = con.begin() # Inicia a transação UMA VEZ, antes do loop
                                for _, row in df_csv.iterrows():
                                    # Prepara os dados da linha
                                    item_data = {
                                        'nome': str(row.get('nome', '')).strip(),
                                        'categoria': row.get('categoria', ''),
                                        'estoque_minimo': int(row.get('estoque_minimo', 0)),
                                        'qtd_laboratorio': int(row.get('qtd_laboratorio', 0)),
                                        'qtd_assistencia': int(row.get('qtd_assistencia', 0)),
                                    }
                                    
                                    if item_data['nome']: # Processa apenas se a linha tiver um nome
                                        # Lógica simplificada: Insere um novo item. Se o nome já existir, atualiza os dados.
                                        query = text("""
                                            INSERT INTO estoque_componentes (nome, categoria, estoque_minimo, qtd_laboratorio, qtd_assistencia)
                                            VALUES (:nome, :categoria, :estoque_minimo, :qtd_laboratorio, :qtd_assistencia)
                                            ON CONFLICT (nome) DO UPDATE SET
                                                categoria = EXCLUDED.categoria,
                                                estoque_minimo = EXCLUDED.estoque_minimo,
                                                qtd_laboratorio = EXCLUDED.qtd_laboratorio,
                                                qtd_assistencia = EXCLUDED.qtd_assistencia;
                                        """)
                                        result = con.execute(query, item_data)
                                        if result.rowcount > 0:
                                            itens_processados += 1
                                trans.commit() # Confirma a transação após o loop
                        st.success(f"Importação concluída! {itens_processados} itens foram processados (inseridos ou atualizados).")
                        st.cache_data.clear()
                        st.rerun()

            except Exception as e:
                st.error(f"Erro ao ler o arquivo CSV: {e}")


    st.markdown("---")

    with st.form("form_componente", clear_on_submit=(st.session_state.edit_stock_id is None)):
        nome = st.text_input("Nome do Componente*", value=nome_default)
        categoria = st.text_input("Categoria (Ex: Diodo, Resistor, Placa)", value=categoria_default)
        estoque_minimo = st.number_input("Estoque Mínimo", min_value=0, step=1, value=estoque_minimo_default)

        if edit_data:
            st.write("Ajustar saldo inicial (apenas em modo de edição):")
            col_qtd1, col_qtd2 = st.columns(2)
            qtd_laboratorio = col_qtd1.number_input("Qtd. Laboratório", min_value=0, step=1, value=qtd_lab_default)
            qtd_assistencia = col_qtd2.number_input("Qtd. Assistência Técnica", min_value=0, step=1, value=qtd_assist_default)

        submit_button_text = "💾 Salvar Alterações" if edit_data else "➕ Adicionar Componente"
        submit_button = st.form_submit_button(submit_button_text, type="primary")

        if submit_button:
            if not nome:
                st.error("O nome do componente é obrigatório.")
            else:
                dados_componente = {
                    "nome": nome,
                    "categoria": categoria,
                    "estoque_minimo": estoque_minimo,
                }
                if edit_data:
                    # Atualização
                    dados_componente["qtd_laboratorio"] = qtd_laboratorio
                    dados_componente["qtd_assistencia"] = qtd_assistencia
                    atualizar_componente(st.session_state.edit_stock_id, dados_componente)
                    st.session_state.edit_stock_id = None
                    st.rerun()
                else:
                    # Inserção
                    # Verifica se o nome do componente já existe (ignorando maiúsculas/minúsculas e espaços)
                    if not df_componentes.empty and nome.strip().lower() in df_componentes['nome'].str.strip().str.lower().values:
                        st.error(f"O componente '{nome}' já está cadastrado. Use a seção 'Gerenciar Componentes Cadastrados' para editá-lo.")
                    else:
                        try:
                            dados_componente["qtd_laboratorio"] = 0
                            dados_componente["qtd_assistencia"] = 0
                            pd.DataFrame([dados_componente]).to_sql('estoque_componentes', engine, if_exists='append', index=False)
                            st.success(f"Componente '{nome}' cadastrado com sucesso!")
                            st.cache_data.clear()
                        except Exception as e:
                            st.error(f"Erro ao cadastrar componente: {e}")

    st.markdown("---")
    st.subheader("⚙️ Gerenciar Componentes Cadastrados")

    if st.session_state.edit_stock_id:
        if st.button("Cancelar Edição"):
            st.session_state.edit_stock_id = None
            st.rerun()

    if not df_componentes.empty:
        df_componentes['display'] = df_componentes.apply(
            lambda row: f"ID {row['id']}: {row['nome']} (Total: {row['qtd_laboratorio'] + row['qtd_assistencia']})",
            axis=1
        )
        componente_selecionado = st.selectbox(
            "Selecione um componente para editar ou excluir:",
            options=[""] + df_componentes['display'].tolist()
        )

        if componente_selecionado:
            id_selecionado = int(componente_selecionado.split(':')[0].replace('ID', '').strip())
            
            btn_col1, btn_col2 = st.columns(2)
            if btn_col1.button("📝 Carregar para Edição", key=f"edit_{id_selecionado}", use_container_width=True):
                st.session_state.edit_stock_id = id_selecionado
                st.rerun()
            
            if btn_col2.button("🗑️ Excluir", type="primary", key=f"delete_{id_selecionado}", use_container_width=True):
                deletar_componente(id_selecionado)
                st.rerun()
    else:
        st.info("Nenhum componente cadastrado.")

# --- ABA 3: MOVIMENTAR ESTOQUE ---
with tab_movimentar:
    st.subheader("Registrar Entrada ou Saída de Componentes")

    if df_componentes.empty:
        st.warning("Cadastre um componente primeiro na aba 'Gerenciar Componentes'.")
    else:
        componentes_dict = dict(zip(df_componentes['nome'], df_componentes['id']))
        lista_componentes = [""] + list(componentes_dict.keys())

        with st.form("form_movimentacao", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                nome_componente = st.selectbox("Selecione o Componente*", options=lista_componentes)
                tipo_movimento = st.radio("Tipo de Movimento*", ["Entrada", "Saída"], horizontal=True)
            with col2:
                local = st.radio("Local do Estoque*", ["Laboratório", "Assistência Técnica"], horizontal=True)
                quantidade = st.number_input("Quantidade*", min_value=1, step=1)

            observacao = st.text_area("Observação (Opcional)", placeholder="Ex: Compra do fornecedor X, Uso na O.S. 1234")

            submit_mov = st.form_submit_button("🚀 Registrar Movimentação", use_container_width=True, type="primary")

            if submit_mov:
                if not nome_componente:
                    st.error("Selecione um componente.")
                else:
                    componente_id = componentes_dict[nome_componente]
                    executar_movimentacao(
                        componente_id=componente_id,
                        tipo_movimento=tipo_movimento,
                        local=local,
                        quantidade=quantidade,
                        observacao=observacao,
                        usuario=st.session_state.get("username", "n/a")
                    )

# --- ABA 4: HISTÓRICO DE MOVIMENTAÇÃO ---
    # --- Seção: Inventário (Contagem Física) ---
    st.markdown("---")
    st.subheader("Inventário (Contagem Física)")

    if df_componentes.empty:
        st.info("Cadastre componentes para realizar o inventário.")
    else:
        componentes_dict_inv = dict(zip(df_componentes['nome'], df_componentes['id']))
        lista_componentes_inv = [""] + list(componentes_dict_inv.keys())

        with st.form("form_inventario_manual", clear_on_submit=False):
            colA, colB = st.columns(2)
            with colA:
                nome_comp_inv = st.selectbox("Componente para ajuste", options=lista_componentes_inv, key="inv_nome")
            with colB:
                local_inv = st.radio("Local do estoque", ["Laborat��rio", "AssistǦncia TǸcnica"], horizontal=True, key="inv_local")

            qtd_atual = 0
            if nome_comp_inv:
                comp_row = df_componentes[df_componentes['nome'] == nome_comp_inv]
                if not comp_row.empty:
                    if local_inv.startswith("Labor"):
                        qtd_atual = int(comp_row.iloc[0].get('qtd_laboratorio', 0) or 0)
                    else:
                        qtd_atual = int(comp_row.iloc[0].get('qtd_assistencia', 0) or 0)

            colC, colD, colE = st.columns([1,1,1])
            with colC:
                st.number_input("Quantidade atual", value=float(qtd_atual), disabled=True, key="inv_atual")
            with colD:
                qtd_contada = st.number_input("Quantidade contada", min_value=0, step=1, value=0, key="inv_contada")
            with colE:
                diff_preview = int(qtd_contada - (st.session_state.get('inv_atual') or 0)) if nome_comp_inv else 0
                st.text_input("Diferença (contada - atual)", value=str(diff_preview), disabled=True, key="inv_diff")

            aplicar_ajuste = st.form_submit_button("Aplicar ajuste de inventário", type="primary")

            if aplicar_ajuste:
                if not nome_comp_inv:
                    st.error("Selecione um componente.")
                else:
                    componente_id = componentes_dict_inv[nome_comp_inv]
                    atual = qtd_atual
                    contado = int(qtd_contada)
                    delta = contado - atual
                    if delta == 0:
                        st.info("Nenhum ajuste necessário: contagem igual ao estoque atual.")
                    else:
                        tipo = "Entrada" if delta > 0 else "Sa��da"
                        qtd_mov = abs(delta)
                        obs = f"Ajuste de inventário (contagem física). De {atual} para {contado}."
                        executar_movimentacao(
                            componente_id=componente_id,
                            tipo_movimento=tipo,
                            local=local_inv,
                            quantidade=qtd_mov,
                            observacao=obs,
                            usuario=st.session_state.get("username", "n/a")
                        )

        with st.expander("Importar contagem via CSV"):
            st.info(
                "Prepare um CSV com as colunas: `nome`, `qtd_laboratorio` e/ou `qtd_assistencia`.\n"
                "Linhas sem alguma coluna serão ignoradas para aquele local. Números negativos serão ajustados para 0."
            )
            inv_file = st.file_uploader("Selecionar arquivo CSV de inventário", type=["csv"], key="inv_csv")
            if inv_file is not None:
                try:
                    import pandas as _pd
                    _df_csv = _pd.read_csv(inv_file, sep=None, engine='python', on_bad_lines='warn')
                    if len(_df_csv.columns) == 1:
                        inv_file.seek(0)
                        try:
                            _df_csv = _pd.read_csv(inv_file, sep=';')
                        except:
                            inv_file.seek(0)
                            _df_csv = _pd.read_csv(inv_file, sep=',')

                    if 'nome' not in _df_csv.columns:
                        st.error("O CSV precisa ter a coluna 'nome'.")
                    else:
                        cols_presentes = [c for c in ['qtd_laboratorio','qtd_assistencia'] if c in _df_csv.columns]
                        if not cols_presentes:
                            st.error("Inclua pelo menos uma coluna: 'qtd_laboratorio' ou 'qtd_assistencia'.")
                        else:
                            _df_csv[cols_presentes] = _df_csv[cols_presentes].fillna(0)
                            for c in cols_presentes:
                                _df_csv[c] = _df_csv[c].clip(lower=0).astype(int)

                            preview = df_componentes[['id','nome','qtd_laboratorio','qtd_assistencia']].merge(
                                _df_csv[['nome'] + cols_presentes], on='nome', how='inner'
                            )
                            if 'qtd_laboratorio' in cols_presentes:
                                preview['delta_lab'] = preview['qtd_laboratorio_y'] - preview['qtd_laboratorio_x']
                            else:
                                preview['delta_lab'] = 0
                            if 'qtd_assistencia' in cols_presentes:
                                preview['delta_ass'] = preview['qtd_assistencia_y'] - preview['qtd_assistencia_x']
                            else:
                                preview['delta_ass'] = 0

                            st.write("Prévia dos ajustes calculados (valores diferentes de zero serão aplicados):")
                            st.dataframe(
                                preview[['nome','qtd_laboratorio_x','qtd_laboratorio_y','delta_lab','qtd_assistencia_x','qtd_assistencia_y','delta_ass']]
                                .rename(columns={
                                    'qtd_laboratorio_x':'atual_lab','qtd_laboratorio_y':'contado_lab',
                                    'qtd_assistencia_x':'atual_ass','qtd_assistencia_y':'contado_ass'
                                }),
                                use_container_width=True,
                                hide_index=True
                            )

                            if st.button("Aplicar ajustes do CSV", type="primary", key="btn_aplicar_csv"):
                                aplicados = 0
                                with st.spinner("Aplicando ajustes de inventário..."):
                                    for _, r in preview.iterrows():
                                        comp_id = int(r['id'])
                                        # Laboratório
                                        dl = int(r.get('delta_lab', 0) or 0)
                                        if dl != 0:
                                            executar_movimentacao(
                                                componente_id=comp_id,
                                                tipo_movimento=("Entrada" if dl > 0 else "Sa��da"),
                                                local="Laborat��rio",
                                                quantidade=abs(dl),
                                                observacao=f"Inventário CSV: ajuste LAB de {int(r['qtd_laboratorio_x'])} para {int(r.get('qtd_laboratorio_y', r['qtd_laboratorio_x']))}",
                                                usuario=st.session_state.get("username", "n/a")
                                            )
                                            aplicados += 1
                                        # Assistência
                                        da = int(r.get('delta_ass', 0) or 0)
                                        if da != 0:
                                            executar_movimentacao(
                                                componente_id=comp_id,
                                                tipo_movimento=("Entrada" if da > 0 else "Sa��da"),
                                                local="AssistǦncia TǸcnica",
                                                quantidade=abs(da),
                                                observacao=f"Inventário CSV: ajuste ASS de {int(r['qtd_assistencia_x'])} para {int(r.get('qtd_assistencia_y', r['qtd_assistencia_x']))}",
                                                usuario=st.session_state.get("username", "n/a")
                                            )
                                            aplicados += 1
                                st.success(f"Ajustes aplicados: {aplicados}")
                except Exception as e:
                    st.error(f"Erro ao processar CSV de inventário: {e}")

with tab_historico:
    st.subheader("Histórico Completo de Movimentações")

    if df_movimentacoes.empty:
        st.info("Nenhuma movimentação de estoque foi registrada ainda.")
    else:
        # Filtros
        col1, col2, col3 = st.columns(3)
        with col1:
            tipos_filtro = st.multiselect(
                "Filtrar por Tipo:",
                options=df_movimentacoes['tipo_movimento'].unique(),
                default=df_movimentacoes['tipo_movimento'].unique()
            )
        with col2:
            locais_filtro = st.multiselect(
                "Filtrar por Local:",
                options=df_movimentacoes['local'].unique(),
                default=df_movimentacoes['local'].unique()
            )
        with col3:
            componentes_filtro = st.multiselect(
                "Filtrar por Componente:",
                options=df_movimentacoes['componente'].unique(),
                default=df_movimentacoes['componente'].unique()
            )

        df_filtrado = df_movimentacoes[
            df_movimentacoes['tipo_movimento'].isin(tipos_filtro) &
            df_movimentacoes['local'].isin(locais_filtro) &
            df_movimentacoes['componente'].isin(componentes_filtro)
        ]

        st.dataframe(
            df_filtrado,
            use_container_width=True,
            hide_index=True,
            column_config={
                "data": st.column_config.DatetimeColumn("Data", format="DD/MM/YYYY HH:mm"),
                "componente": "Componente",
                "tipo_movimento": "Tipo",
                "local": "Local",
                "quantidade": "Qtd.",
                "observacao": "Observação",
                "usuario_lancamento": "Usuário"
            }
        )
