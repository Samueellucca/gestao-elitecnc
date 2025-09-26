import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, time, timedelta
from sqlalchemy import create_engine, text
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
import sqlite3
import io
import holidays

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

if st.session_state.get("authentication_status"):
    # --- APLICAÇÃO PRINCIPAL ---
    DB_FILE = "financeiro.db"
    engine = create_engine(f'sqlite:///{DB_FILE}')

    name = st.session_state.get("name", "")
    username = st.session_state.get("username", "")

    # --- FUNÇÕES DE BANCO DE DADOS ---
    @st.cache_data
    def carregar_dados():
        try:
            # Lê a tabela considerando que a tabela tem coluna 'id' (PK) e 'data' armazenada como TEXT/ISO
            entradas_df = pd.read_sql_query("SELECT * FROM entradas", engine, parse_dates=['data'])
            # garante que exista coluna 'id' (compatibilidade com versões antigas que usavam rowid)
            if 'id' not in entradas_df.columns:
                entradas_df.reset_index(inplace=True)
                entradas_df.rename(columns={'index': 'id'}, inplace=True)
        except Exception as e:
            entradas_df = pd.DataFrame(columns=[
                'id','data','ordem_servico','valor_atendimento','horas_tecnicas','horas_tecnicas_50',
                'horas_tecnicas_100','km','refeicao','pecas','hora_inicio','hora_fim',
                'patrimonio','maquina','descricao_servico','cliente','pedagio','usuario_lancamento'
            ])
        try:
            saidas_df = pd.read_sql_query("SELECT * FROM saidas", engine, parse_dates=['data'])
            if 'id' not in saidas_df.columns:
                saidas_df.reset_index(inplace=True)
                saidas_df.rename(columns={'index': 'id'}, inplace=True)
        except Exception as e:
            saidas_df = pd.DataFrame(columns=['id','data','tipo_conta','descricao','valor','usuario_lancamento'])

        # forçar conversão da coluna data para datetime quando possível
        if not entradas_df.empty and 'data' in entradas_df.columns:
            entradas_df['data'] = pd.to_datetime(entradas_df['data'], errors='coerce')
        if not saidas_df.empty and 'data' in saidas_df.columns:
            saidas_df['data'] = pd.to_datetime(saidas_df['data'], errors='coerce')

        return entradas_df, saidas_df

    def carregar_clientes():
        with engine.connect() as con:
            try:
                clientes_df = pd.read_sql_query("SELECT nome FROM clientes ORDER BY nome", con)
                return [""] + clientes_df['nome'].tolist()
            except:
                return [""]

    def deletar_lancamento(tabela, record_id):
        with engine.connect() as con:
            con.execute(text(f"DELETE FROM {tabela} WHERE id = :id"), {"id": record_id})
            con.commit()

    def atualizar_lancamento(tabela, record_id, dados):
        with engine.connect() as con:
            # monta set_clause sem incluir 'id'
            dados_copy = {k: v for k, v in dados.items() if k != 'id'}
            set_clause = ", ".join([f"\"{key}\" = :{key}" for key in dados_copy.keys()])
            dados_copy['id'] = record_id
            con.execute(text(f"UPDATE {tabela} SET {set_clause} WHERE id = :id"), dados_copy)
            con.commit()

    # --- CARREGANDO DADOS E CLIENTES ---
    entradas_df, saidas_df = carregar_dados()
    clientes_cadastrados = carregar_clientes()

    # --- DEBUG: mostra o conteúdo carregado (temporário) ---
    st.sidebar.subheader("DEBUG (apenas leitura)")
    st.sidebar.write("Entradas - dtypes:")
    st.sidebar.write(entradas_df.dtypes if not entradas_df.empty else "Sem entradas carregadas")
    st.sidebar.write("Entradas - primeiras linhas:")
    st.sidebar.write(entradas_df.head() if not entradas_df.empty else "Sem entradas carregadas")
    st.sidebar.write("Saídas - primeiras linhas:")
    st.sidebar.write(saidas_df.head() if not saidas_df.empty else "Sem saídas carregadas")
    st.sidebar.markdown("---")

    st.sidebar.title(f'Bem-vindo(a), *{name}*')
    authenticator.logout('Sair', 'sidebar')

    if 'edit_id' not in st.session_state:
        st.session_state.edit_id = None
    if 'edit_table' not in st.session_state:
        st.session_state.edit_table = None

    # --- CONSTANTES ---
    VALOR_POR_KM = 2.30
    VALOR_HORA_TECNICA = 90.00

    edit_data = None
    if st.session_state.edit_id is not None:
        df_to_edit = entradas_df if st.session_state.edit_table == 'entradas' else saidas_df
        if not df_to_edit.empty and st.session_state.edit_id in df_to_edit['id'].values:
            edit_data = df_to_edit[df_to_edit['id'] == st.session_state.edit_id].iloc[0].to_dict()

    # --- BARRA LATERAL ---
    st.sidebar.header("Lançar / Editar Dados")

    if st.session_state.edit_id:
        st.sidebar.info(f"Você está editando o lançamento ID: {st.session_state.edit_id} ({st.session_state.edit_table or ''})")
        if st.sidebar.button("Cancelar Edição"):
            st.session_state.edit_id = None
            st.session_state.edit_table = None
            st.experimental_rerun()

    is_editing_entrada = st.session_state.edit_id is not None and st.session_state.edit_table == 'entradas'
    with st.sidebar.form("form_entradas", clear_on_submit=False):
        st.subheader("Editando Entrada" if is_editing_entrada else "Nova Entrada (O.S.)")

        # --- LÓGICA DE VALORES PADRÃO ---
        data_default = datetime.now().date()
        hora_inicio_default = time(8, 0)
        hora_fim_default = time(17, 0)

        if is_editing_entrada and edit_data:
            if pd.notnull(edit_data.get('data')):
                data_default = edit_data['data'].date() if isinstance(edit_data['data'], (pd.Timestamp, datetime)) else pd.to_datetime(edit_data['data'], errors='coerce').date()
            if pd.notnull(edit_data.get('hora_inicio')):
                try:
                    hora_inicio_default = datetime.strptime(str(edit_data['hora_inicio']), '%H:%M:%S').time()
                except (ValueError, TypeError):
                    hora_inicio_default = time(8, 0)
            if pd.notnull(edit_data.get('hora_fim')):
                try:
                    hora_fim_default = datetime.strptime(str(edit_data['hora_fim']), '%H:%M:%S').time()
                except (ValueError, TypeError):
                    hora_fim_default = time(17,0)
        
        os_id_default = edit_data.get('ordem_servico', "") if is_editing_entrada and edit_data else ""
        descricao_servico_default = edit_data.get('descricao_servico', "") if is_editing_entrada and edit_data else ""
        pedagio_default = float(edit_data.get('pedagio', 0.0)) if is_editing_entrada and edit_data else 0.0
        refeicao_default = float(edit_data.get('refeicao', 0.0)) if is_editing_entrada and edit_data else 0.0
        pecas_default = float(edit_data.get('pecas', 0.0)) if is_editing_entrada and edit_data else 0.0
        cliente_default = edit_data.get('cliente', "") if is_editing_entrada and edit_data else ""
        patrimonio_default = edit_data.get('patrimonio', "") if is_editing_entrada and edit_data else ""
        maquina_default = edit_data.get('maquina', "") if is_editing_entrada and edit_data else ""

        # --- CAMPOS DO FORMULÁRIO ---
        data_atendimento = st.date_input("Data do Atendimento", value=data_default)
        os_id = st.text_input("Nº da O.S.", value=os_id_default)
        descricao_servico = st.text_area("Descrição do Serviço", value=descricao_servico_default)
        
        cliente_index = clientes_cadastrados.index(cliente_default) if cliente_default in clientes_cadastrados else 0
        cliente = st.selectbox("Cliente", options=clientes_cadastrados, index=cliente_index)

        patrimonio = st.text_input("Patrimônio", value=patrimonio_default)
        maquina = st.text_input("Máquina", value=maquina_default)
        
        st.markdown("---")
        st.write("Cálculo de Horas")
        col_hora1, col_hora2 = st.columns(2)
        with col_hora1:
            hora_inicio = st.time_input("Hora de Início", value=hora_inicio_default, step=60)
        with col_hora2:
            hora_fim = st.time_input("Hora de Fim", value=hora_fim_default, step=60)

        st.markdown("---")
        st.write("Valores e Quantidades:")
        valor_hora_input = st.number_input("Valor da Hora Técnica (R$)", min_value=0.0, format="%.2f", value=VALOR_HORA_TECNICA)
        qtd_km = st.number_input(f"Qtd KM Rodados (R$ {VALOR_POR_KM:.2f}/km)", min_value=0.0, format="%.2f")
        refeicao = st.number_input("Valor da Refeição", min_value=0.0, format="%.2f", value=refeicao_default)
        pecas_entrada = st.number_input("Valor das Peças (Venda)", min_value=0.0, format="%.2f", value=pecas_default)
        pedagio = st.number_input("Valor do Pedágio", min_value=0.0, format="%.2f", value=pedagio_default)

        submit_entrada = st.form_submit_button("Salvar Alterações" if is_editing_entrada else "Lançar Entrada")

        if submit_entrada:
            
            # --- NOVA LÓGICA DE CÁLCULO DE HORAS ---
            
            # 1. Definir os períodos do dia
            inicio_trabalho = datetime.combine(data_atendimento, hora_inicio)
            fim_trabalho = datetime.combine(data_atendimento, hora_fim)
            if fim_trabalho <= inicio_trabalho:
                fim_trabalho += timedelta(days=1)

            periodo_normal_inicio = datetime.combine(inicio_trabalho.date(), time(7, 0))
            periodo_normal_fim = datetime.combine(inicio_trabalho.date(), time(17, 0))
            periodo_almoco_inicio = datetime.combine(inicio_trabalho.date(), time(12, 0))
            periodo_almoco_fim = datetime.combine(inicio_trabalho.date(), time(13, 0))

            # Função auxiliar para calcular sobreposição de tempo em segundos
            def calcular_sobreposicao(inicio1, fim1, inicio2, fim2):
                sobreposicao_inicio = max(inicio1, inicio2)
                sobreposicao_fim = min(fim1, fim2)
                if sobreposicao_fim > sobreposicao_inicio:
                    return (sobreposicao_fim - sobreposicao_inicio).total_seconds()
                return 0

            # 2. Calcular desconto de almoço
            segundos_almoco = calcular_sobreposicao(inicio_trabalho, fim_trabalho, periodo_almoco_inicio, periodo_almoco_fim)
            
            # 3. Verificar se é dia de semana, fim de semana ou feriado
            brasil_holidays = holidays.Brazil(years=inicio_trabalho.year)
            is_dia_util = inicio_trabalho.weekday() < 5 and inicio_trabalho.date() not in brasil_holidays
            
            segundos_normais = 0
            segundos_extra_50 = 0
            segundos_extra_100 = 0
            
            duracao_total_bruta_segundos = (fim_trabalho - inicio_trabalho).total_seconds()
            duracao_total_liquida_segundos = duracao_total_bruta_segundos - segundos_almoco

            if is_dia_util:
                # Calcula horas normais (já descontando o almoço que acontece nesse período)
                segundos_normais_brutos = calcular_sobreposicao(inicio_trabalho, fim_trabalho, periodo_normal_inicio, periodo_normal_fim)
                segundos_normais = segundos_normais_brutos - segundos_almoco
                
                # O que sobrar são horas 50%
                segundos_extra_50 = duracao_total_liquida_segundos - segundos_normais
            else:
                # Em feriados ou fim de semana, todas as horas líquidas são 100%
                segundos_extra_100 = duracao_total_liquida_segundos

            # 4. Converter segundos para horas decimais
            horas_normais = max(segundos_normais, 0) / 3600
            horas_extra_50 = max(segundos_extra_50, 0) / 3600
            horas_extra_100 = max(segundos_extra_100, 0) / 3600

            # --- CÁLCULO FINANCEIRO ---
            valor_horas_normais = valor_hora_input * horas_normais
            valor_horas_50 = (valor_hora_input * 1.5) * horas_extra_50
            valor_horas_100 = (valor_hora_input * 2.0) * horas_extra_100
            
            valor_km_final = qtd_km * VALOR_POR_KM
            valor_atendimento_calculado = valor_horas_normais + valor_horas_50 + valor_horas_100 + valor_km_final + refeicao + pecas_entrada + pedagio

            dados_lancamento = {
                'data': inicio_trabalho.isoformat(),  # salva como string ISO -> facilita leitura no SQLite
                'hora_inicio': hora_inicio.strftime('%H:%M:%S'),
                'hora_fim': hora_fim.strftime('%H:%M:%S'),
                'ordem_servico': os_id,
                'descricao_servico': descricao_servico,
                'cliente': cliente,
                'valor_atendimento': float(valor_atendimento_calculado),
                'horas_tecnicas': float(valor_horas_normais),
                'horas_tecnicas_50': float(valor_horas_50),
                'horas_tecnicas_100': float(valor_horas_100),
                'km': float(valor_km_final),
                'refeicao': float(refeicao),
                'pecas': float(pecas_entrada),
                'pedagio': float(pedagio),
                'usuario_lancamento': username,
                'patrimonio': patrimonio,
                'maquina': maquina
            }

            if is_editing_entrada and st.session_state.edit_id:
                atualizar_lancamento('entradas', st.session_state.edit_id, dados_lancamento)
                st.sidebar.success("Entrada atualizada!")
            else:
                # inserir evitando enviar campo 'id' (AUTOINCREMENT)
                df_insert = pd.DataFrame([dados_lancamento])
                df_insert.to_sql('entradas', engine, if_exists='append', index=False)
                st.sidebar.success(f"Entrada lançada!")

            st.session_state.edit_id, st.session_state.edit_table = None, None
            st.cache_data.clear()
            st.experimental_rerun()

    # O restante do arquivo (formulário de saídas, painel principal, gráficos) permanece semelhante, com correções para usar 'id' ao editar/excluir
    is_editing_saida = st.session_state.edit_id is not None and st.session_state.edit_table == 'saidas'
    with st.sidebar.form("form_saidas", clear_on_submit=False):
        st.subheader("Editando Saída" if is_editing_saida else "Nova Saída")
        
        if is_editing_saida and edit_data and pd.notnull(edit_data.get('data')):
            data_default_s = edit_data['data'].date() if isinstance(edit_data['data'], (pd.Timestamp, datetime)) else pd.to_datetime(edit_data['data'], errors='coerce').date()
            hora_default_s = datetime.strptime(str(edit_data.get('hora_saida','00:00:00')), '%H:%M:%S').time() if edit_data.get('hora_saida') else datetime.now().time()
        else:
            data_default_s = datetime.now().date()
            hora_default_s = datetime.now().time()
            
        tipo_conta_default = edit_data.get('tipo_conta', 'Fixa') if is_editing_saida and edit_data else 'Fixa'
        descricao_default = edit_data.get('descricao', "") if is_editing_saida and edit_data else ""
        valor_default = float(edit_data.get('valor', 0.0)) if is_editing_saida and edit_data else 0.0
        tipo_conta_index = ["Fixa", "Variável"].index(tipo_conta_default) if tipo_conta_default in ["Fixa", "Variável"] else 0

        data_d_s = st.date_input("Data da Despesa", value=data_default_s, key="data_saida")
        data_t_s = st.time_input("Hora da Despesa", value=hora_default_s, key="hora_saida")
        tipo_conta = st.selectbox("Tipo de Conta", ["Fixa", "Variável"], index=tipo_conta_index)
        descricao_saida = st.text_input("Descrição da Despesa", value=descricao_default)
        valor_saida = st.number_input("Valor da Despesa", min_value=0.0, format="%.2f", value=valor_default)

        submit_saida = st.form_submit_button("Salvar Alterações" if is_editing_saida else "Lançar Saída")
        if submit_saida:
            data_completa_s = datetime.combine(data_d_s, data_t_s)
            dados_lancamento_s = {
                'data': data_completa_s.isoformat(),
                'tipo_conta': tipo_conta,
                'descricao': descricao_saida,
                'valor': float(valor_saida),
                'usuario_lancamento': username
            }

            if is_editing_saida and st.session_state.edit_id:
                atualizar_lancamento('saidas', st.session_state.edit_id, dados_lancamento_s)
                st.sidebar.success("Saída atualizada!")
            else:
                pd.DataFrame([dados_lancamento_s]).to_sql('saidas', engine, if_exists='append', index=False)
                st.sidebar.success("Saída lançada!")

            st.session_state.edit_id, st.session_state.edit_table = None, None
            st.cache_data.clear()
            st.experimental_rerun()

    st.sidebar.header("Gerenciar Lançamentos")
    tipo_lancamento = st.sidebar.selectbox("Tipo de lançamento", ["Entrada", "Saída"])
    df_gerenciar = entradas_df if tipo_lancamento == "Entrada" else saidas_df

    if not df_gerenciar.empty:
        if tipo_lancamento == "Entrada":
            df_gerenciar['display'] = df_gerenciar.apply(
                lambda row: f"ID {int(row['id'])}: {(pd.to_datetime(row['data']).strftime('%d/%m/%y %H:%M') if pd.notnull(row['data']) else 'Data N/A')} - O.S. {row.get('ordem_servico', 'N/A')}", 
                axis=1
            )
        else:
            df_gerenciar['display'] = df_gerenciar.apply(
                lambda row: f"ID {int(row['id'])}: {(pd.to_datetime(row['data']).strftime('%d/%m/%y %H:%M') if pd.notnull(row['data']) else 'Data N/A')} - {row.get('descricao', 'N/A')}", 
                axis=1
            )

        lancamento_selecionado = st.sidebar.selectbox(
            "Selecione o lançamento",
            options=df_gerenciar['display'],
            key=f"select_lancamento_{tipo_lancamento}"
        )
        if lancamento_selecionado:
            id_selecionado = int(lancamento_selecionado.split(':')[0].replace('ID', '').strip())

            col1, col2 = st.sidebar.columns(2)
            if col1.button("Carregar para Edição", key=f"edit_{tipo_lancamento}"):
                st.session_state.edit_id = id_selecionado
                st.session_state.edit_table = 'entradas' if tipo_lancamento == "Entrada" else 'saidas'
                st.experimental_rerun()

            if col2.button("Excluir", type="primary", key=f"delete_{tipo_lancamento}"):
                deletar_lancamento('entradas' if tipo_lancamento == "Entrada" else 'saidas', id_selecionado)
                st.sidebar.success("Lançamento excluído!")
                st.cache_data.clear()
                st.experimental_rerun()
    else:
        st.sidebar.info(f"Nenhum(a) {tipo_lancamento.lower()} para gerenciar.")

    st.title("📊 Dashboard Financeiro")
    st.markdown("---")

    start_date, end_date = None, None
    entradas_filtradas, saidas_filtradas = pd.DataFrame(), pd.DataFrame()

    if not entradas_df.empty or not saidas_df.empty:
        all_dates = []
        if not entradas_df.empty and 'data' in entradas_df.columns:
            all_dates.extend(pd.to_datetime(entradas_df['data'], errors='coerce').dt.date.dropna().tolist())
        if not saidas_df.empty and 'data' in saidas_df.columns:
            all_dates.extend(pd.to_datetime(saidas_df['data'], errors='coerce').dt.date.dropna().tolist())
        
        if all_dates:
            min_date, max_date = min(all_dates), max(all_dates)
            date_range = st.date_input("Filtre por período:", [min_date, max_date], min_value=min_date, max_value=max_date, format="DD/MM/YYYY")
            
            if len(date_range) == 2:
                start_date, end_date = date_range
            elif len(date_range) == 1:
                start_date, end_date = date_range[0], date_range[0]

            if start_date and end_date:
                start_date_dt = pd.to_datetime(start_date)
                end_date_dt = pd.to_datetime(end_date).replace(hour=23, minute=59, second=59)
                
                entradas_filtradas = entradas_df[(entradas_df['data'] >= start_date_dt) & (entradas_df['data'] <= end_date_dt)]
                saidas_filtradas = saidas_df[(saidas_df['data'] >= start_date_dt) & (saidas_df['data'] <= end_date_dt)]

                clientes_disponiveis = sorted(entradas_filtradas['cliente'].dropna().unique().tolist())
                cliente_filtro = st.selectbox("Filtrar por cliente:", options=["Todos"] + clientes_disponiveis)
                if cliente_filtro != "Todos":
                    entradas_filtradas = entradas_filtradas[entradas_filtradas['cliente'] == cliente_filtro]
    else:
        st.warning("Nenhum dado lançado ainda.")

    total_entradas = entradas_filtradas['valor_atendimento'].sum() if 'valor_atendimento' in entradas_filtradas.columns else 0
    total_saidas = saidas_filtradas['valor'].sum() if 'valor' in saidas_filtradas.columns else 0
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
            fig = px.pie(saidas_filtradas, names='descricao', values='valor', title="Distribuição de Despesas")
            fig.update_traces(hovertemplate='<b>%{label}</b><br>Valor: R$ %{value:,.2f}<extra></extra>')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Nenhuma saída no período.")

    with col2:
        st.subheader("Composição das Entradas")
        if not entradas_filtradas.empty:
            plot_df_cols = ['horas_tecnicas', 'horas_tecnicas_50', 'horas_tecnicas_100', 'km', 'refeicao', 'pecas', 'pedagio']
            existing_cols = [col for col in plot_df_cols if col in entradas_filtradas.columns]
            
            if existing_cols:
                plot_df = entradas_filtradas[existing_cols].sum().reset_index()
                plot_df.columns = ['Tipo', 'Valor']
                if 'valor_atendimento' in entradas_filtradas:
                    fixo = entradas_filtradas['valor_atendimento'].sum() - plot_df['Valor'].sum()
                    if fixo > 0.01:
                       plot_df.loc[len(plot_df)] = ['Valor Fixo Serviço', fixo]
                
                fig = px.pie(plot_df, names='Tipo', values='Valor', title="Distribuição de Receitas")
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
            fig = px.bar(balanco_df, x='data', y=['Entrada', 'Saída'], title="Entradas vs. Saídas por Dia", barmode='group')
            fig.update_traces(hovertemplate='<b>%{x}</b><br>Valor: R$ %{y:,.2f}<extra></extra>')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sem dados para exibir o balanço diário.")
    else:
        st.info("Sem dados para exibir o balanço diário.")

    st.markdown("---")
    st.subheader("📥 Exportar Relatório do Período")
    if 'start_date' in locals() and start_date and end_date:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            entradas_filtradas.to_excel(writer, index=False, sheet_name='Entradas')
            saidas_filtradas.to_excel(writer, index=False, sheet_name='Saídas')
        st.download_button(
            label="📥 Baixar Relatório (Excel)",
            data=buffer.getvalue(),
            file_name=f"Relatorio_Financeiro_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    st.markdown("---")
    st.subheader("Registros Detalhados (Geral)")
    currency_columns = {
        "valor_atendimento": st.column_config.NumberColumn("Valor Total (R$)", format="R$ %.2f"),
        "horas_tecnicas": st.column_config.NumberColumn("Horas Normais (R$)", format="R$ %.2f"),
        "horas_tecnicas_50": st.column_config.NumberColumn("Horas 50% (R$)", format="R$ %.2f"),
        "horas_tecnicas_100": st.column_config.NumberColumn("Horas 100% (R$)", format="R$ %.2f"),
        "km": st.column_config.NumberColumn("KM (R$)", format="R$ %.2f"),
        "refeicao": st.column_config.NumberColumn("Refeição (R$)", format="R$ %.2f"),
        "pecas": st.column_config.NumberColumn("Peças (R$)", format="R$ %.2f"),
        "pedagio": st.column_config.NumberColumn("Pedágio (R$)", format="R$ %.2f"),
        "valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f"),
        "data": st.column_config.DatetimeColumn("Data", format="DD/MM/YYYY - HH:mm"),
        "descricao_servico": "Descrição do Serviço",
        "ordem_servico": "Nº O.S.",
        "cliente": "Cliente",
        "hora_inicio": "Início",
        "hora_fim": "Fim",
        "patrimonio": "Patrimônio",
        "maquina": "Máquina"
    }
    with st.expander("Ver todas as entradas"):
        st.dataframe(entradas_df, column_config=currency_columns, use_container_width=True, hide_index=True)
    with st.expander("Ver todas as saídas"):
        st.dataframe(saidas_df, column_config=currency_columns, use_container_width=True, hide_index=True)

elif st.session_state.get("authentication_status") is False:
    st.error('Usuário/senha incorreto')
else:
    st.warning('Por favor, insira seu usuário e senha para acessar.')
