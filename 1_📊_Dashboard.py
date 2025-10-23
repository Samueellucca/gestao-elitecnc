import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, time, timedelta
from sqlalchemy import create_engine, text
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
import io
import holidays

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Dashboard Financeiro", page_icon="💰", layout="wide")

def safe_number(value, default=0.0):
    """Converte valor para float seguro.
    Se vier None, vazio, NaN ou inválido → retorna default."""
    try:
        if value is None or str(value).strip() == "":
            return default
        val = float(value)
        if pd.isna(val):
            return default
        return val
    except Exception:
        return default

def safe_int(value, default=1):
    """Converte valor para int seguro. Retorna default se a conversão falhar."""
    return int(safe_number(value, default))

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
# A lógica de login é chamada aqui, mas a interface do usuário é controlada abaixo
authenticator.login() 

if st.session_state["authentication_status"]:
    # --- APLICAÇÃO PRINCIPAL (QUANDO LOGADO) ---
    # O código principal do seu dashboard vai aqui dentro.
    # Para manter a organização, vamos importar os módulos pesados apenas após o login.
    from datetime import datetime, time, timedelta

    from sqlalchemy import create_engine, text
    import io
    import holidays

    # --- APLICAÇÃO PRINCIPAL ---
    # Conexão com o banco de dados da nuvem a partir dos "Secrets"
    connection_url = st.secrets["database"]["connection_url"]
    engine = create_engine(connection_url)

    name = st.session_state["name"]
    username = st.session_state["username"]
    
    # --- FUNÇÕES DE BANCO DE DADOS ---
    @st.cache_data
    def carregar_dados():
        try:
            entradas_df = pd.read_sql_query("SELECT * FROM entradas", engine, parse_dates=['data'])
        except Exception:
            entradas_df = pd.DataFrame()
        try:
            saidas_df = pd.read_sql_query("SELECT * FROM saidas", engine, parse_dates=['data'])
        except Exception:
            saidas_df = pd.DataFrame()
        return entradas_df, saidas_df

    def carregar_clientes():
        with engine.connect() as con:
            try:
                clientes_df = pd.read_sql_query("SELECT nome FROM clientes ORDER BY nome", con)
                return [""] + clientes_df['nome'].tolist()
            except:
                return [""]

    def deletar_lancamento(tabela, id):
        with engine.connect() as con:
            con.execute(text(f"DELETE FROM {tabela} WHERE id = :id"), {"id": id})
            con.commit()

    def atualizar_lancamento(tabela, id, dados):
        with engine.connect() as con:
            # --- FILTRAR APENAS COLUNAS EXISTENTES NO BANCO ---
            colunas_existentes = pd.read_sql(f"SELECT * FROM {tabela} LIMIT 1", engine).columns
            dados = {k: v for k, v in dados.items() if k in colunas_existentes}

            set_clause = ", ".join([f"\"{key}\" = :{key}" for key in dados.keys()])
            dados['id'] = id
            con.execute(text(f"UPDATE {tabela} SET {set_clause} WHERE id = :id"), dados)
            con.commit()

    # --- CARREGANDO DADOS E CLIENTES ---
    entradas_df, saidas_df = carregar_dados()
    clientes_cadastrados = carregar_clientes()

    # --- BARRA LATERAL ---
    st.sidebar.image("logo.png", width=150)
    st.sidebar.title(f'Bem-vindo(a), *{name}*')
    authenticator.logout('Sair', 'sidebar')

    st.title("📊 Dashboard Financeiro")

    if 'edit_id' not in st.session_state:
        st.session_state.edit_id = None
    if 'edit_table' not in st.session_state:
        st.session_state.edit_table = None

    # --- ABAS PRINCIPAIS ---
    tab1, tab2 = st.tabs(["📊 Dashboard", "✍️ Lançamentos & Edição"])

elif st.session_state["authentication_status"] is False:
    # --- TELA DE LOGIN (SENHA INCORRETA) ---
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.image("logo.png", use_container_width=True)
    st.error('Usuário/senha incorreto')

elif st.session_state["authentication_status"] is None:
    # --- TELA DE LOGIN (INICIAL) ---
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.image("logo.png", use_container_width=True)
    st.warning('Por favor, insira seu usuário e senha para acessar.')



# --- CONSTANTES ---
VALOR_POR_KM = 2.30
VALOR_HORA_TECNICA = 90.00

# --- ABA DE LANÇAMENTOS ---
if "authentication_status" in st.session_state and st.session_state["authentication_status"]:
    with tab2:
        st.header("✍️ Lançamentos e Edição")

        edit_data = None
        if st.session_state.edit_id is not None:
            df_to_edit = entradas_df if st.session_state.edit_table == 'entradas' else saidas_df
            if not df_to_edit.empty and st.session_state.edit_id in df_to_edit['id'].values:
                edit_data = df_to_edit[df_to_edit['id'] == st.session_state.edit_id].iloc[0].to_dict()

        if st.session_state.edit_id:
            st.info(f"Você está editando o lançamento ID: {st.session_state.edit_id} ({st.session_state.edit_table[:-1]})")
            if st.button("Cancelar Edição"):
                st.session_state.edit_id = None
                st.session_state.edit_table = None
                st.rerun()

        col_form1, col_form2 = st.columns(2, gap="large")

        # --- FORMULÁRIO DE ENTRADAS ---
        with col_form1:
            is_editing_entrada = st.session_state.edit_id is not None and st.session_state.edit_table == 'entradas'
            with st.form("form_entradas", clear_on_submit=True):
                st.subheader("➕ Nova Entrada (O.S.)" if not is_editing_entrada else "📝 Editando Entrada")

                # --- LÓGICA DE VALORES PADRÃO ---
                data_default = datetime.now().date()
                hora_inicio_default = time(8, 0) # type: ignore
                hora_fim_default = time(17, 0)

                if is_editing_entrada and edit_data:
                    if pd.notnull(edit_data.get('data')):
                        data_default = edit_data['data'].date()
                    if pd.notnull(edit_data.get('hora_inicio')):
                        try:
                            hora_inicio_default = datetime.strptime(edit_data['hora_inicio'], '%H:%M:%S').time()
                        except (ValueError, TypeError):
                            hora_inicio_default = time(8, 0)
                    if pd.notnull(edit_data.get('hora_fim')):
                        try:
                            hora_fim_default = datetime.strptime(edit_data['hora_fim'], '%H:%M:%S').time()
                        except (ValueError, TypeError):
                            hora_fim_default = time(17,0)
                
                os_id_default = edit_data.get('ordem_servico', "") if is_editing_entrada and edit_data else ""
                descricao_servico_default = edit_data.get('descricao_servico', "") if is_editing_entrada and edit_data else ""
                patrimonio_default = edit_data.get('patrimonio', "") if is_editing_entrada and edit_data else ""
                maquina_default = edit_data.get('maquina', "") if is_editing_entrada and edit_data else ""
                pedagio_default = safe_number(edit_data.get('pedagio')) if is_editing_entrada and edit_data else 0.0
                refeicao_default = safe_number(edit_data.get('refeicao')) if is_editing_entrada and edit_data else 0.0
                pecas_default = safe_number(edit_data.get('pecas')) if is_editing_entrada and edit_data else 0.0
                cliente_default = edit_data.get('cliente', "") if is_editing_entrada and edit_data else ""
                qtd_tecnicos_default = safe_int(edit_data.get('qtd_tecnicos')) if is_editing_entrada and edit_data else 1
                
                km_valor_default = safe_number(edit_data.get('km')) if is_editing_entrada and edit_data else 0.0
                qtd_km_default = km_valor_default / VALOR_POR_KM if VALOR_POR_KM > 0 else 0.0

                valor_deslocamento_default = safe_number(edit_data.get('valor_deslocamento')) if is_editing_entrada and edit_data else 0.0
                valor_laboratorio_default = safe_number(edit_data.get('valor_laboratorio')) if is_editing_entrada and edit_data else 0.0

                status_default = edit_data.get('status', "Pendente") if is_editing_entrada and edit_data else "Pendente"
                # --- CAMPOS DO FORMULÁRIO ---
                data_atendimento = st.date_input("Data do Atendimento", value=data_default)
                os_id = st.text_input("Nº da O.S.", value=os_id_default)
                descricao_servico = st.text_area("Descrição do Serviço", value=descricao_servico_default)
                patrimonio = st.text_input("Patrimônio", value=patrimonio_default)
                maquina = st.text_input("Máquina", value=maquina_default)
                
                cliente_index = clientes_cadastrados.index(cliente_default) if cliente_default in clientes_cadastrados else 0
                cliente = st.selectbox("Cliente", options=clientes_cadastrados, index=cliente_index)

                status_options = ["Pendente", "Pago", "Cancelado"]
                status = st.selectbox("Status do Lançamento", options=status_options, index=status_options.index(status_default))

                st.markdown("---")
                st.write("Cálculo de Horas")
                qtd_tecnicos = st.number_input("Quantidade de Técnicos", min_value=1, step=1, value=qtd_tecnicos_default)
                qtd_tecnicos = int(qtd_tecnicos)
                
                col_hora1, col_hora2 = st.columns(2)
                with col_hora1:
                    hora_inicio = st.time_input("Hora de Início", value=hora_inicio_default, step=timedelta(minutes=15))
                with col_hora2:
                    hora_fim = st.time_input("Hora de Fim", value=hora_fim_default, step=timedelta(minutes=15))

                st.write("Intervalo (Almoço/Janta) - Opcional")
                col_almoco1, col_almoco2 = st.columns(2)
                with col_almoco1:
                    # Usamos None como padrão para indicar que não há intervalo
                    hora_almoco_inicio = st.time_input("Início do Intervalo", value=None, step=timedelta(minutes=15))
                with col_almoco2:
                    hora_almoco_fim = st.time_input("Fim do Intervalo", value=None, step=timedelta(minutes=15))

                st.markdown("---")
                st.write("Valores e Quantidades:")
                valor_hora_input = st.number_input("Valor da Hora Técnica (R$)", min_value=0.0, format="%.2f", value=VALOR_HORA_TECNICA)
                valor_deslocamento = st.number_input("Valor Deslocamento do Técnico (R$)", min_value=0.0, step=1.0, value=valor_deslocamento_default)
                valor_laboratorio = st.number_input("Valor Laboratório (R$)", min_value=0.0, step=1.0, value=valor_laboratorio_default)
                qtd_km = st.number_input(f"Qtd KM Rodados (R$ {VALOR_POR_KM:.2f}/km)", min_value=0.0, format="%.2f", value=qtd_km_default)
                refeicao = st.number_input("Valor da Refeição",min_value=0.0, step=1.0, value=refeicao_default)
                pecas_entrada = st.number_input("Valor das Peças (Venda)", min_value=0.0, step=1.0, value=pecas_default)
                pedagio = st.number_input("Valor do Pedágio", min_value=0.0, step=1.0, value=pedagio_default)

                submit_entrada = st.form_submit_button("💾 Salvar Alterações" if is_editing_entrada else "✅ Lançar Entrada", use_container_width=True)

            if submit_entrada:
                inicio_trabalho = datetime.combine(data_atendimento, hora_inicio)
                fim_trabalho = datetime.combine(data_atendimento, hora_fim)
                if fim_trabalho <= inicio_trabalho:
                    fim_trabalho += timedelta(days=1)

                # REMOVIDO: Cálculo automático de almoço
                # periodo_almoco_inicio = datetime.combine(inicio_trabalho.date(), time(12, 0))
                # periodo_almoco_fim = datetime.combine(inicio_trabalho.date(), time(13, 0))

                periodo_normal_inicio = datetime.combine(inicio_trabalho.date(), time(7, 0))
                periodo_normal_fim = datetime.combine(inicio_trabalho.date(), time(17, 0))

                def calcular_sobreposicao(inicio1, fim1, inicio2, fim2):
                    sobreposicao_inicio = max(inicio1, inicio2)
                    sobreposicao_fim = min(fim1, fim2)
                    if sobreposicao_fim > sobreposicao_inicio:
                        return (sobreposicao_fim - sobreposicao_inicio).total_seconds()
                    return 0

                brasil_holidays = holidays.Brazil(years=inicio_trabalho.year)
                is_dia_util = inicio_trabalho.weekday() < 5 and inicio_trabalho.date() not in brasil_holidays
                duracao_total_bruta_segundos = (fim_trabalho - inicio_trabalho).total_seconds()

                # NOVO: Cálculo do intervalo manual
                segundos_intervalo = 0
                if hora_almoco_inicio and hora_almoco_fim and hora_almoco_fim > hora_almoco_inicio:
                    inicio_intervalo_dt = datetime.combine(data_atendimento, hora_almoco_inicio)
                    fim_intervalo_dt = datetime.combine(data_atendimento, hora_almoco_fim)
                    segundos_intervalo = (fim_intervalo_dt - inicio_intervalo_dt).total_seconds()

                duracao_total_liquida_segundos = duracao_total_bruta_segundos - segundos_intervalo

                segundos_normais = segundos_extra_50 = segundos_extra_100 = 0
                if is_dia_util:
                    # Calcula a sobreposição com o período normal
                    segundos_normais = calcular_sobreposicao(inicio_trabalho, fim_trabalho, periodo_normal_inicio, periodo_normal_fim)
                    # Desconta o intervalo do período normal primeiro
                    segundos_normais -= segundos_intervalo
                    segundos_normais = max(0, segundos_normais) # Garante que não seja negativo

                    segundos_extra_50 = duracao_total_liquida_segundos - segundos_normais
                else:
                    segundos_extra_100 = duracao_total_liquida_segundos

                horas_normais, horas_extra_50, horas_extra_100 = segundos_normais / 3600, segundos_extra_50 / 3600, segundos_extra_100 / 3600
                valor_horas_normais = (valor_hora_input * horas_normais) * qtd_tecnicos
                valor_horas_50 = ((valor_hora_input * 1.5) * horas_extra_50) * qtd_tecnicos
                valor_horas_100 = ((valor_hora_input * 2.0) * horas_extra_100) * qtd_tecnicos
                valor_km_final = qtd_km * VALOR_POR_KM
                valor_atendimento_calculado = (valor_horas_normais + valor_horas_50 + valor_horas_100 + valor_km_final + refeicao + pecas_entrada + pedagio + (valor_deslocamento * qtd_tecnicos) + valor_laboratorio)

                dados_lancamento = {
                    'data': pd.to_datetime(inicio_trabalho), 'hora_inicio': hora_inicio.strftime('%H:%M:%S'), 'hora_fim': hora_fim.strftime('%H:%M:%S'),
                    'ordem_servico': os_id or "", 'descricao_servico': descricao_servico or "", 'patrimonio': patrimonio or "", 'maquina': maquina or "", 'cliente': cliente or "",
                    'valor_atendimento': safe_number(valor_atendimento_calculado), 'horas_tecnicas': safe_number(valor_horas_normais), 'horas_tecnicas_50': safe_number(valor_horas_50),
                    'horas_tecnicas_100': safe_number(valor_horas_100), 'km': safe_number(valor_km_final), 'refeicao': safe_number(refeicao), 'pecas': safe_number(pecas_entrada),
                    'pedagio': safe_number(pedagio), 'usuario_lancamento': username, 'qtd_tecnicos': safe_int(qtd_tecnicos, default=1), 'valor_deslocamento': safe_number(valor_deslocamento),
                    'valor_laboratorio': safe_number(valor_laboratorio), 'status': status, 'valor_deslocamento_total': safe_number(valor_deslocamento) * safe_int(qtd_tecnicos, default=1),
                    'valor_hora_tecnica_total': safe_number(valor_hora_input * qtd_tecnicos), 'horas_normais': safe_number(horas_normais), 'horas_extra_50': safe_number(horas_extra_50),
                    'horas_extra_100': safe_number(horas_extra_100)
                }

                if is_editing_entrada:
                    atualizar_lancamento('entradas', st.session_state.edit_id, dados_lancamento)
                    st.success("Entrada atualizada!")
                else:
                    colunas_existentes = pd.read_sql("SELECT * FROM entradas LIMIT 1", engine).columns
                    dados_lancamento_filtrado = {k: v for k, v in dados_lancamento.items() if k in colunas_existentes}
                    pd.DataFrame([dados_lancamento_filtrado]).to_sql('entradas', engine, if_exists='append', index=False)
                    st.success("Entrada lançada!")

                st.session_state.edit_id, st.session_state.edit_table = None, None
                st.cache_data.clear()
                st.rerun()

        # --- FORMULÁRIO DE SAÍDAS E GERENCIAMENTO ---
        with col_form2:
            is_editing_saida = st.session_state.edit_id is not None and st.session_state.edit_table == 'saidas'
            with st.form("form_saidas", clear_on_submit=True):
                st.subheader("➖ Nova Saída" if not is_editing_saida else "📝 Editando Saída")
                
                if is_editing_saida and edit_data and pd.notnull(edit_data.get('data')):
                    data_default_s, hora_default_s = edit_data['data'].date(), edit_data['data'].time()
                else:
                    data_default_s, hora_default_s = datetime.now().date(), datetime.now().time()
                    
                tipo_conta_default = edit_data.get('tipo_conta', 'Fixa') if is_editing_saida and edit_data else 'Fixa'
                descricao_default = edit_data.get('descricao', "") if is_editing_saida and edit_data else ""
                valor_default = edit_data.get('valor', 0.0) if is_editing_saida and edit_data else 0.0
                tipo_conta_index = ["Fixa", "Variável"].index(tipo_conta_default)

                data_d_s = st.date_input("Data da Despesa", value=data_default_s, key="data_saida")
                data_t_s = st.time_input("Hora da Despesa", value=hora_default_s, key="hora_saida")
                tipo_conta = st.selectbox("Tipo de Conta", ["Fixa", "Variável"], index=tipo_conta_index)
                descricao_saida = st.text_input("Descrição da Despesa", value=descricao_default)
                valor_saida = st.number_input("Valor da Despesa", min_value=0.0, format="%.2f", value=valor_default)

                submit_saida = st.form_submit_button("💾 Salvar Alterações" if is_editing_saida else "✅ Lançar Saída", use_container_width=True)
                if submit_saida:
                    data_completa_s = datetime.combine(data_d_s, data_t_s)
                    dados_lancamento_s = {'data': data_completa_s, 'tipo_conta': tipo_conta, 'descricao': descricao_saida, 'valor': valor_saida, 'usuario_lancamento': username}

                    if is_editing_saida:
                        atualizar_lancamento('saidas', st.session_state.edit_id, dados_lancamento_s)
                        st.success("Saída atualizada!")
                    else:
                        pd.DataFrame([dados_lancamento_s]).to_sql('saidas', engine, if_exists='append', index=False)
                        st.success("Saída lançada!")

                    st.session_state.edit_id, st.session_state.edit_table = None, None
                    st.cache_data.clear()
                    st.rerun()

            st.markdown("---")
            # --- GERENCIAR LANÇAMENTOS ---
            st.subheader("⚙️ Gerenciar Lançamentos")
            tipo_lancamento = st.selectbox("Tipo de lançamento", ["Entrada", "Saída"])
            df_gerenciar = entradas_df if tipo_lancamento == "Entrada" else saidas_df

            if not df_gerenciar.empty:
                df_gerenciar_sorted = df_gerenciar.sort_values(by='data', ascending=False)
                if tipo_lancamento == "Entrada":
                    df_gerenciar_sorted['display'] = df_gerenciar_sorted.apply(lambda row: f"ID {row['id']}: {(row['data'].strftime('%d/%m/%y %H:%M') if pd.notnull(row['data']) else 'Data N/A')} - O.S. {row.get('ordem_servico', 'N/A')}", axis=1)
                else:
                    df_gerenciar_sorted['display'] = df_gerenciar_sorted.apply(lambda row: f"ID {row['id']}: {(row['data'].strftime('%d/%m/%y %H:%M') if pd.notnull(row['data']) else 'Data N/A')} - {row.get('descricao', 'N/A')}", axis=1)

                lancamento_selecionado = st.selectbox("Selecione o lançamento para editar ou excluir", options=df_gerenciar_sorted['display'], key=f"select_lancamento_{tipo_lancamento}")
                if lancamento_selecionado:
                    id_selecionado = int(lancamento_selecionado.split(':')[0].replace('ID', '').strip())

                    col1, col2 = st.columns(2)
                    if col1.button("📝 Carregar para Edição", key=f"edit_{tipo_lancamento}", use_container_width=True):
                        st.session_state.edit_id = id_selecionado
                        st.session_state.edit_table = 'entradas' if tipo_lancamento == "Entrada" else 'saidas'
                        st.rerun()

                    if col2.button("🗑️ Excluir", type="primary", key=f"delete_{tipo_lancamento}", use_container_width=True):
                        deletar_lancamento('entradas' if tipo_lancamento == "Entrada" else 'saidas', id_selecionado)
                        st.success("Lançamento excluído!")
                        st.cache_data.clear()
                        st.rerun()
            else:
                st.info(f"Nenhum(a) {tipo_lancamento.lower()} para gerenciar.")

# --- ABA DO DASHBOARD ---
if "authentication_status" in st.session_state and st.session_state["authentication_status"]:
    with tab1:
        start_date, end_date = None, None
        entradas_filtradas, saidas_filtradas = pd.DataFrame(), pd.DataFrame()

        if not entradas_df.empty or not saidas_df.empty:
            all_dates = []
            if not entradas_df.empty and 'data' in entradas_df.columns:
                all_dates.extend(pd.to_datetime(entradas_df['data']).dt.date.dropna())
            if not saidas_df.empty and 'data' in saidas_df.columns:
                all_dates.extend(pd.to_datetime(saidas_df['data']).dt.date.dropna())
            
            if all_dates:
                min_date, max_date = min(all_dates), max(all_dates)
                
                st.subheader("Filtros do Dashboard")
                st.info(
                    "Os dados exibidos no dashboard são filtrados pelo período, status e cliente selecionados. "
                    "Certifique-se de que o status 'Pendente' esteja selecionado no filtro de status para visualizar lançamentos de laboratório não pagos.",
                    icon="ℹ️"
                )
                col_filter1, col_filter2, col_filter3 = st.columns(3)
                with col_filter1:
                    date_range = st.date_input("Filtre por período:", [min_date, max_date], min_value=min_date, max_value=max_date, format="DD/MM/YYYY")
                
                if len(date_range) == 2:
                    start_date, end_date = date_range[0], date_range[1]

                if start_date and end_date:
                    # Verifica se a coluna 'status' existe antes de usá-la
                    if 'status' in entradas_df.columns:
                        status_disponiveis = sorted(entradas_df['status'].dropna().unique().tolist())
                        with col_filter2:
                            status_filtro = st.multiselect("Filtrar por status:", options=status_disponiveis, default=status_disponiveis)
                    else:
                        status_filtro = [] # Define como lista vazia se a coluna não existir

                    clientes_disponiveis = sorted(entradas_df['cliente'].dropna().unique().tolist())
                    with col_filter3:
                        cliente_filtro = st.selectbox("Filtrar por cliente:", options=["Todos"] + clientes_disponiveis)

                    start_date_dt = pd.to_datetime(start_date)
                    end_date_dt = pd.to_datetime(end_date).replace(hour=23, minute=59, second=59)
                    
                    entradas_filtradas = entradas_df[(entradas_df['data'] >= start_date_dt) & (entradas_df['data'] <= end_date_dt)]
                    saidas_filtradas = saidas_df[(saidas_df['data'] >= start_date_dt) & (saidas_df['data'] <= end_date_dt)]

                    if cliente_filtro != "Todos":
                        entradas_filtradas = entradas_filtradas[entradas_filtradas['cliente'] == cliente_filtro]
                    if status_filtro and 'status' in entradas_filtradas.columns:
                        entradas_filtradas = entradas_filtradas[entradas_filtradas['status'].isin(status_filtro)]
        else:
            st.warning("Nenhum dado lançado ainda.")

        st.markdown("---")
        st.subheader("Resumo Financeiro do Período")
        total_entradas = entradas_filtradas['valor_atendimento'].sum() if 'valor_atendimento' in entradas_filtradas.columns else 0
        total_saidas = saidas_filtradas['valor'].sum() if 'valor' in saidas_filtradas.columns else 0
        lucro_real = total_entradas - total_saidas

        col1, col2, col3 = st.columns(3)
        col1.metric("🟢 Total de Entradas", f"R$ {total_entradas:,.2f}")
        col2.metric("🔴 Total de Saídas", f"R$ {total_saidas:,.2f}")
        col3.metric("💰 Lucro Real", f"R$ {lucro_real:,.2f}")
        st.markdown("---")

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Composição das Saídas")
            if not saidas_filtradas.empty:
                fig = px.pie(saidas_filtradas, names='descricao', values='valor', title="Distribuição de Despesas")
                fig.update_traces(hovertemplate='<b>%{label}</b><br>Valor: R$ %{value:,.2f}<extra></extra>')
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Nenhuma saída no período.")

        with col2:
            st.subheader("Composição das Entradas")
            if not entradas_filtradas.empty:
                plot_df_cols = ['horas_tecnicas', 'horas_tecnicas_50', 'horas_tecnicas_100', 'km', 'refeicao', 'pecas', 'pedagio', 'valor_laboratorio', 'valor_deslocamento_total']
                existing_cols = [col for col in plot_df_cols if col in entradas_filtradas.columns]
                
                if existing_cols:
                    plot_df = entradas_filtradas[existing_cols].sum().reset_index()
                    plot_df.columns = ['Tipo', 'Valor']
                    plot_df = plot_df[plot_df['Valor'] > 0] # Remove valores zerados
                    
                    fig = px.pie(plot_df, names='Tipo', values='Valor', title="Distribuição de Receitas por Categoria")
                    fig.update_traces(hovertemplate='<b>%{label}</b><br>Valor: R$ %{value:,.2f}<extra></extra>')
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Nenhuma coluna de receita para exibir.")
            else:
                st.info("Nenhuma entrada no período.")

        st.subheader("Balanço Diário")
        if not entradas_filtradas.empty or not saidas_filtradas.empty:
            entradas_diarias = entradas_filtradas.groupby(entradas_filtradas['data'].dt.date)['valor_atendimento'].sum().reset_index(name='Entrada') if not entradas_filtradas.empty and 'valor_atendimento' in entradas_filtradas else pd.DataFrame(columns=['data', 'Entrada'])
            saidas_diarias = saidas_filtradas.groupby(saidas_filtradas['data'].dt.date)['valor'].sum().reset_index(name='Saída') if not saidas_filtradas.empty else pd.DataFrame(columns=['data', 'Saída'])
            
            if not entradas_diarias.empty or not saidas_diarias.empty:
                balanco_df = pd.merge(entradas_diarias, saidas_diarias, on='data', how='outer').fillna(0)
                balanco_df['Lucro'] = balanco_df['Entrada'] - balanco_df['Saída']
                fig = px.bar(balanco_df, x='data', y=['Entrada', 'Saída'], title="Entradas vs. Saídas por Dia", barmode='group', color_discrete_map={'Entrada': 'green', 'Saída': 'red'})
                fig.update_traces(hovertemplate='<b>%{x}</b><br>Valor: R$ %{y:,.2f}<extra></extra>')
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Sem dados para exibir o balanço diário.")
        else:
            st.info("Sem dados para exibir o balanço diário.")

        st.markdown("---")
        st.subheader("📥 Exportar e Visualizar Dados")
        if start_date and end_date:
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                entradas_filtradas.to_excel(writer, index=False, sheet_name='Entradas')
                saidas_filtradas.to_excel(writer, index=False, sheet_name='Saídas')
            st.download_button(
                label="📥 Baixar Relatório do Período (Excel)",
                data=buffer.getvalue(),
                file_name=f"Relatorio_Financeiro_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        currency_columns = {
            "valor_atendimento": st.column_config.NumberColumn("Valor Total (R$)", format="R$ %.2f"),
            "horas_tecnicas": st.column_config.NumberColumn("Horas Normais (R$)", format="R$ %.2f"),
            "horas_tecnicas_50": st.column_config.NumberColumn("Horas 50% (R$)", format="R$ %.2f"),
            "horas_tecnicas_100": st.column_config.NumberColumn("Horas 100% (R$)", format="R$ %.2f"),
            "km": st.column_config.NumberColumn("KM (R$)", format="R$ %.2f"),
            "refeicao": st.column_config.NumberColumn("Refeição (R$)", format="R$ %.2f"),
            "pecas": st.column_config.NumberColumn("Peças (R$)", format="R$ %.2f"),
            "pedagio": st.column_config.NumberColumn("Pedágio (R$)", format="R$ %.2f"),
            "valor_laboratorio": st.column_config.NumberColumn("Laboratório (R$)", format="R$ %.2f"),
            "valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f"),
            "data": st.column_config.DatetimeColumn("Data", format="DD/MM/YYYY - HH:mm"), "status": "Status",
            "descricao_servico": "Descrição do Serviço", "ordem_servico": "Nº O.S.", "cliente": "Cliente",
            "patrimonio": "Patrimônio", "maquina": "Máquina", "hora_inicio": "Início", "hora_fim": "Fim"
        }
        with st.expander("Ver todos os registros de Entrada"):
            st.dataframe(entradas_df.sort_values(by='data', ascending=False), column_config=currency_columns, use_container_width=True, hide_index=True)
        with st.expander("Ver todos os registros de Saída"):
            st.dataframe(saidas_df.sort_values(by='data', ascending=False), column_config=currency_columns, use_container_width=True, hide_index=True)
