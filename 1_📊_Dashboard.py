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
from fpdf import FPDF

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

def gerar_pdf_financeiro(entradas, saidas, inicio, fim):
    """Gera um PDF com o resumo financeiro e listagem de lançamentos."""
    class PDF(FPDF):
        def header(self):
            # Tenta inserir o logo no canto superior esquerdo (x=10, y=8, largura=33)
            try:
                self.image('logo.png', 10, 8, 33)
            except:
                pass # Se não encontrar a imagem, segue sem logo

            try:
                self.add_font('DejaVu', '', 'DejaVuSans.ttf')
                self.add_font('DejaVu', 'B', 'DejaVuSans-Bold.ttf')
                self.set_font('DejaVu', 'B', 14)
            except:
                self.set_font('Arial', 'B', 14)
            self.cell(0, 10, "Relatório Financeiro - Elite CNC", 0, 1, 'C')
            self.set_font_size(10)
            self.cell(0, 10, f"Período: {inicio.strftime('%d/%m/%Y')} a {fim.strftime('%d/%m/%Y')}", 0, 1, 'C')
            self.ln(10) # Aumenta o espaçamento para não sobrepor o logo
            
        def footer(self):
            self.set_y(-30) # Aumenta o espaço reservado para o rodapé
            try:
                self.set_font('DejaVu', '', 8)
            except:
                self.set_font('Arial', 'I', 8)
            
            self.cell(0, 5, "Rua da Paz, 230 - Santa Rita - Monte Alto SP", 0, 1, 'C')
            self.cell(0, 5, "Tel: (11) 97761-7009 | Email: elitecncservice@gmail.com", 0, 1, 'C')
            
            self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=35) # Garante que a tabela pare antes de chegar no rodapé
    pdf.add_page()
    
    # Configuração de fonte para o corpo
    try:
        pdf.add_font('DejaVu', '', 'DejaVuSans.ttf')
        pdf.add_font('DejaVu', 'B', 'DejaVuSans-Bold.ttf')
        font_family = 'DejaVu'
    except:
        font_family = 'Arial'

    # Resumo
    total_ent = entradas['valor_atendimento'].sum() if not entradas.empty else 0
    total_sai = saidas['valor'].sum() if not saidas.empty else 0
    lucro = total_ent - total_sai
    
    pdf.set_font(font_family, 'B', 12)
    pdf.cell(0, 8, "Resumo do Período", 0, 1)
    pdf.set_font(font_family, '', 10)
    pdf.cell(50, 6, f"Total Entradas: R$ {total_ent:,.2f}", 0, 1)
    pdf.cell(50, 6, f"Total Saídas: R$ {total_sai:,.2f}", 0, 1)
    pdf.cell(50, 6, f"Lucro Líquido: R$ {lucro:,.2f}", 0, 1)
    pdf.ln(5)
    
    # Tabela Entradas
    pdf.set_font(font_family, 'B', 12)
    pdf.cell(0, 8, "Entradas (Receitas)", 0, 1)
    pdf.set_font(font_family, 'B', 8)
    pdf.set_fill_color(220, 230, 241)
    pdf.cell(20, 6, "Data", 1, 0, 'C', True); pdf.cell(60, 6, "Cliente", 1, 0, 'C', True); pdf.cell(25, 6, "O.S.", 1, 0, 'C', True); pdf.cell(30, 6, "Valor", 1, 0, 'C', True); pdf.cell(25, 6, "Status", 1, 1, 'C', True)
    
    pdf.set_font(font_family, '', 8)
    if not entradas.empty:
        for _, row in entradas.iterrows():
            pdf.cell(20, 6, row['data'].strftime('%d/%m/%Y') if pd.notnull(row['data']) else "", 1)
            pdf.cell(60, 6, str(row.get('cliente', ''))[:30], 1)
            pdf.cell(25, 6, str(row.get('ordem_servico', ''))[:12], 1)
            pdf.cell(30, 6, f"R$ {row.get('valor_atendimento', 0):,.2f}", 1, 0, 'R')
            pdf.cell(25, 6, str(row.get('status', ''))[:12], 1, 1, 'C')
    else:
        pdf.cell(160, 6, "Nenhum registro.", 1, 1, 'C')
    pdf.ln(5)
    
    # Tabela Saídas
    pdf.set_font(font_family, 'B', 12)
    pdf.cell(0, 8, "Saídas (Despesas)", 0, 1)
    pdf.set_font(font_family, 'B', 8)
    pdf.set_fill_color(241, 220, 220)
    pdf.cell(20, 6, "Data", 1, 0, 'C', True); pdf.cell(85, 6, "Descrição", 1, 0, 'C', True); pdf.cell(30, 6, "Valor", 1, 0, 'C', True); pdf.cell(25, 6, "Tipo", 1, 1, 'C', True)
    
    pdf.set_font(font_family, '', 8)
    if not saidas.empty:
        for _, row in saidas.iterrows():
            pdf.cell(20, 6, row['data'].strftime('%d/%m/%Y') if pd.notnull(row['data']) else "", 1)
            pdf.cell(85, 6, str(row.get('descricao', ''))[:45], 1)
            pdf.cell(30, 6, f"R$ {row.get('valor', 0):,.2f}", 1, 0, 'R')
            pdf.cell(25, 6, str(row.get('tipo_conta', ''))[:12], 1, 1, 'C')
    else:
        pdf.cell(160, 6, "Nenhum registro.", 1, 1, 'C')
        
    return bytes(pdf.output())

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
VALOR_POR_KM = 2.45
VALOR_HORA_TECNICA = 100.00

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

        # Layout: Coluna maior para Entradas (mais campos), Coluna menor para Saídas
        col_form1, col_form2 = st.columns([1.8, 1], gap="medium")

        # --- FORMULÁRIO DE ENTRADAS ---
        with col_form1:
            is_editing_entrada = st.session_state.edit_id is not None and st.session_state.edit_table == 'entradas'
            
            # Container visual para o formulário de Entradas
            with st.container(border=True):
                st.markdown("### 🛠️ Nova Ordem de Serviço (Entrada)" if not is_editing_entrada else "### 📝 Editando Ordem de Serviço")
                
                with st.expander("📤 Importar Entradas via CSV"):
                    st.info("Colunas sugeridas: data, cliente, valor_atendimento, ordem_servico, descricao_servico, status.")
                    uploaded_file_ent = st.file_uploader("Selecionar CSV de Entradas", type="csv", key="csv_entradas")
                    if uploaded_file_ent:
                        try:
                            try:
                                df_ent_csv = pd.read_csv(uploaded_file_ent, sep=None, engine='python')
                            except UnicodeDecodeError:
                                uploaded_file_ent.seek(0)
                                df_ent_csv = pd.read_csv(uploaded_file_ent, sep=None, engine='python', encoding='latin-1')

                            df_ent_csv.columns = df_ent_csv.columns.str.lower()

                            if 'data' in df_ent_csv.columns:
                                df_ent_csv['data'] = pd.to_datetime(df_ent_csv['data'], dayfirst=True, errors='coerce')
                                df_ent_csv.dropna(subset=['data'], inplace=True)
                                st.dataframe(df_ent_csv.head(), use_container_width=True)
                                if st.button("Confirmar Importação (Entradas)", type="primary"):
                                    df_ent_csv['usuario_lancamento'] = username
                                    cols_validas = pd.read_sql("SELECT * FROM entradas LIMIT 0", engine).columns
                                    df_final = df_ent_csv[[c for c in df_ent_csv.columns if c in cols_validas]]
                                    df_final.to_sql('entradas', engine, if_exists='append', index=False)
                                    st.success(f"{len(df_final)} entradas importadas com sucesso!")
                                    st.cache_data.clear()
                                    st.rerun()
                            else:
                                st.error("O arquivo CSV precisa ter uma coluna chamada 'data'.")
                        except Exception as e:
                            st.error(f"Erro ao ler CSV: {e}")

                with st.form("form_entradas", clear_on_submit=True):
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
                    nome_tecnicos_default = edit_data.get('nome_tecnicos', "") if is_editing_entrada and edit_data else ""
                    
                    km_valor_default = safe_number(edit_data.get('km')) if is_editing_entrada and edit_data else 0.0
                    qtd_km_default = km_valor_default / VALOR_POR_KM if VALOR_POR_KM > 0 else 0.0

                    valor_deslocamento_default = safe_number(edit_data.get('valor_deslocamento')) if is_editing_entrada and edit_data else 0.0
                    valor_laboratorio_default = safe_number(edit_data.get('valor_laboratorio')) if is_editing_entrada and edit_data else 0.0

                    status_default = edit_data.get('status', "Pendente") if is_editing_entrada and edit_data else "Pendente"
                    
                    # --- CAMPOS DO FORMULÁRIO (LAYOUT MELHORADO) ---
                    st.markdown("##### 📋 Dados Gerais")
                    c_gen1, c_gen2, c_gen3 = st.columns([1.5, 1, 1])
                    with c_gen1:
                        cliente_index = clientes_cadastrados.index(cliente_default) if cliente_default in clientes_cadastrados else 0
                        cliente = st.selectbox("Cliente", options=clientes_cadastrados, index=cliente_index)
                    with c_gen2:
                        os_id = st.text_input("Nº da O.S.", value=os_id_default)
                    with c_gen3:
                        status_options = ["Pendente", "Pago", "Cancelado"]
                        status = st.selectbox("Status", options=status_options, index=status_options.index(status_default))

                    c_det1, c_det2, c_det3 = st.columns(3)
                    with c_det1:
                        data_atendimento = st.date_input("Data", value=data_default)
                    with c_det2:
                        maquina = st.text_input("Máquina", value=maquina_default)
                    with c_det3:
                        patrimonio = st.text_input("Patrimônio", value=patrimonio_default)

                    descricao_servico = st.text_area("Descrição do Serviço", value=descricao_servico_default, height=68)

                    st.markdown("---")
                    st.markdown("##### ⏱️ Horas e Técnicos")
                    c_tec1, c_tec2 = st.columns([1, 2])
                    with c_tec1:
                        qtd_tecnicos = st.number_input("Qtd. Técnicos", min_value=1, step=1, value=qtd_tecnicos_default)
                        qtd_tecnicos = int(qtd_tecnicos)
                    with c_tec2:
                        nome_tecnicos = st.text_input("Nome do(s) Técnico(s)", value=nome_tecnicos_default, placeholder="Ex: João, Maria")
                    
                    c_hora1, c_hora2, c_hora3, c_hora4 = st.columns(4)
                    with c_hora1:
                        hora_inicio = st.time_input("Início", value=hora_inicio_default, step=timedelta(minutes=15))
                    with c_hora2:
                        hora_fim = st.time_input("Fim", value=hora_fim_default, step=timedelta(minutes=15))
                    with c_hora3:
                        hora_almoco_inicio = st.time_input("Início Intervalo", value=None, step=timedelta(minutes=15))
                    with c_hora4:
                        hora_almoco_fim = st.time_input("Fim Intervalo", value=None, step=timedelta(minutes=15))

                    st.markdown("---")
                    st.markdown("##### 💰 Detalhamento Financeiro")
                    
                    c_fin1, c_fin2, c_fin3 = st.columns(3)
                    with c_fin1:
                        valor_hora_input = st.number_input("Valor Hora Técnica (R$)", min_value=0.0, format="%.2f", value=VALOR_HORA_TECNICA)
                        valor_deslocamento = st.number_input("Deslocamento Técnico (R$)", min_value=0.0, step=1.0, value=valor_deslocamento_default)
                        valor_laboratorio = st.number_input("Valor Laboratório (R$)", min_value=0.0, step=1.0, value=valor_laboratorio_default)
                    with c_fin2:
                        qtd_km = st.number_input(f"KM Rodados (R$ {VALOR_POR_KM:.2f}/km)", min_value=0.0, format="%.2f", value=qtd_km_default)
                        refeicao = st.number_input("Refeição (R$)",min_value=0.0, step=1.0, value=refeicao_default)
                    with c_fin3:
                        pecas_entrada = st.number_input("Peças (R$)", min_value=0.0, step=1.0, value=pecas_default)
                        pedagio = st.number_input("Pedágio (R$)", min_value=0.0, step=1.0, value=pedagio_default)

                    st.write("") # Espaçamento
                    submit_entrada = st.form_submit_button("💾 Salvar Alterações" if is_editing_entrada else "✅ Lançar Entrada", use_container_width=True, type="primary")

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
                    'horas_extra_100': safe_number(horas_extra_100),
                    'nome_tecnicos': nome_tecnicos or ""
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
            
            # Container visual para o formulário de Saídas
            with st.container(border=True):
                st.markdown("### 💸 Nova Despesa (Saída)" if not is_editing_saida else "### 📝 Editando Despesa")
                
                with st.expander("📤 Importar Saídas via CSV"):
                    st.info("Colunas sugeridas: data, descricao, valor, tipo_conta.")
                    uploaded_file_sai = st.file_uploader("Selecionar CSV de Saídas", type="csv", key="csv_saidas")
                    if uploaded_file_sai:
                        try:
                            try:
                                df_sai_csv = pd.read_csv(uploaded_file_sai, sep=None, engine='python')
                            except UnicodeDecodeError:
                                uploaded_file_sai.seek(0)
                                df_sai_csv = pd.read_csv(uploaded_file_sai, sep=None, engine='python', encoding='latin-1')

                            df_sai_csv.columns = df_sai_csv.columns.str.lower()

                            if 'data' in df_sai_csv.columns:
                                df_sai_csv['data'] = pd.to_datetime(df_sai_csv['data'], dayfirst=True, errors='coerce')
                                df_sai_csv.dropna(subset=['data'], inplace=True)
                                st.dataframe(df_sai_csv.head(), use_container_width=True)
                                if st.button("Confirmar Importação (Saídas)", type="primary"):
                                    df_sai_csv['usuario_lancamento'] = username
                                    cols_validas = pd.read_sql("SELECT * FROM saidas LIMIT 0", engine).columns
                                    df_final = df_sai_csv[[c for c in df_sai_csv.columns if c in cols_validas]]
                                    df_final.to_sql('saidas', engine, if_exists='append', index=False)
                                    st.success(f"{len(df_final)} saídas importadas com sucesso!")
                                    st.cache_data.clear()
                                    st.rerun()
                            else:
                                st.error("O arquivo CSV precisa ter uma coluna chamada 'data'.")
                        except Exception as e:
                            st.error(f"Erro ao ler CSV: {e}")

                with st.form("form_saidas", clear_on_submit=True):
                    if is_editing_saida and edit_data and pd.notnull(edit_data.get('data')):
                        data_default_s, hora_default_s = edit_data['data'].date(), edit_data['data'].time()
                    else:
                        data_default_s, hora_default_s = datetime.now().date(), datetime.now().time()
                        
                    tipo_conta_default = edit_data.get('tipo_conta', 'Fixa') if is_editing_saida and edit_data else 'Fixa'
                    descricao_default = edit_data.get('descricao', "") if is_editing_saida and edit_data else ""
                    valor_default = edit_data.get('valor', 0.0) if is_editing_saida and edit_data else 0.0
                    tipo_conta_index = ["Fixa", "Variável"].index(tipo_conta_default)

                    data_d_s = st.date_input("Data", value=data_default_s, key="data_saida")
                    data_t_s = st.time_input("Hora", value=hora_default_s, key="hora_saida")
                    tipo_conta = st.selectbox("Tipo de Conta", ["Fixa", "Variável"], index=tipo_conta_index)
                    descricao_saida = st.text_input("Descrição", value=descricao_default)
                    valor_saida = st.number_input("Valor (R$)", min_value=0.0, format="%.2f", value=valor_default)
                    
                    st.write("")
                    submit_saida = st.form_submit_button("💾 Salvar Alterações" if is_editing_saida else "✅ Lançar Saída", use_container_width=True, type="primary")
            
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

        # --- GERENCIAR LANÇAMENTOS (MOVIDO PARA BAIXO PARA MELHOR LAYOUT) ---
        st.markdown("---")
        with st.container(border=True):
            st.subheader("⚙️ Gerenciar Lançamentos Recentes")
            
            tipo_lancamento = st.radio("Selecione o tipo para gerenciar:", ["Entrada", "Saída"], horizontal=True)
            df_gerenciar = entradas_df if tipo_lancamento == "Entrada" else saidas_df

            if not df_gerenciar.empty:
                df_gerenciar_sorted = df_gerenciar.sort_values(by='data', ascending=False)
                if tipo_lancamento == "Entrada":
                    df_gerenciar_sorted['display'] = df_gerenciar_sorted.apply(lambda row: f"ID {row['id']}: {(row['data'].strftime('%d/%m/%y %H:%M') if pd.notnull(row['data']) else 'Data N/A')} - O.S. {row.get('ordem_servico', 'N/A')} - {row.get('cliente', 'N/A')}", axis=1)
                else:
                    df_gerenciar_sorted['display'] = df_gerenciar_sorted.apply(lambda row: f"ID {row['id']}: {(row['data'].strftime('%d/%m/%y %H:%M') if pd.notnull(row['data']) else 'Data N/A')} - {row.get('descricao', 'N/A')} - R$ {row.get('valor', 0):.2f}", axis=1)

                lancamento_selecionado = st.selectbox("Selecione o lançamento para editar ou excluir", options=df_gerenciar_sorted['display'], key=f"select_lancamento_{tipo_lancamento}")
                if lancamento_selecionado:
                    id_selecionado = int(lancamento_selecionado.split(':')[0].replace('ID', '').strip())

                    col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 4])
                    if col_btn1.button("📝 Editar", key=f"edit_{tipo_lancamento}", use_container_width=True):
                        st.session_state.edit_id = id_selecionado
                        st.session_state.edit_table = 'entradas' if tipo_lancamento == "Entrada" else 'saidas'
                        st.rerun()

                    if col_btn2.button("🗑️ Excluir", type="primary", key=f"delete_{tipo_lancamento}", use_container_width=True):
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
                min_date_db, max_date_db = min(all_dates), max(all_dates)
                
                today = datetime.now().date()
                default_start = today - timedelta(days=30)
                default_end = today

                picker_min = min(min_date_db, default_start)
                picker_max = max(max_date_db, default_end)
                
                # --- ÁREA DE FILTROS (EXPANDER) ---
                with st.expander("🔍 Filtros e Seleção de Período", expanded=True):
                    st.info(
                        "Selecione o período e os filtros abaixo para atualizar os gráficos. "
                        "Para ver lançamentos não pagos, inclua o status 'Pendente'.",
                        icon="ℹ️"
                    )
                    
                    # Linha 1: Data e Status (Filtros Primários)
                    c_top1, c_top2 = st.columns([1, 1])
                    
                    with c_top1:
                        date_range = st.date_input("📅 Período de Análise:", [default_start, default_end], min_value=picker_min, max_value=picker_max, format="DD/MM/YYYY")
                    
                    if len(date_range) == 2:
                        start_date, end_date = date_range[0], date_range[1]

                    if start_date and end_date:
                        # Verifica se a coluna 'status' existe antes de usá-la
                        if 'status' in entradas_df.columns:
                            status_disponiveis = sorted(entradas_df['status'].dropna().unique().tolist())
                            # Remove 'Negociado' do padrão para evitar duplicidade de soma
                            defaults = [s for s in status_disponiveis if s != 'Negociado']
                            with c_top2:
                                status_filtro = st.multiselect("🏷️ Status:", options=status_disponiveis, default=defaults, placeholder="Selecione os status...")
                        else:
                            status_filtro = []

                        # Linha 2: Cliente e Técnico (Filtros Secundários)
                        c_bot1, c_bot2 = st.columns([1, 1])

                        clientes_disponiveis = sorted(entradas_df['cliente'].dropna().unique().tolist())
                        with c_bot1:
                            cliente_filtro = st.selectbox("👤 Cliente:", options=["Todos"] + clientes_disponiveis)

                        tecnicos_disponiveis = []
                        if 'nome_tecnicos' in entradas_df.columns:
                            series_tecnicos = entradas_df['nome_tecnicos'].dropna().str.split(',').explode()
                            tecnicos_disponiveis = sorted(series_tecnicos.str.strip().replace('', pd.NA).dropna().unique())
                        
                        with c_bot2:
                            tecnico_filtro = st.multiselect("🔧 Técnico:", options=tecnicos_disponiveis, default=[], placeholder="Todos os técnicos")

                        # --- APLICAÇÃO DOS FILTROS ---
                        start_date_dt = pd.to_datetime(start_date)
                        end_date_dt = pd.to_datetime(end_date).replace(hour=23, minute=59, second=59)
                        
                        entradas_filtradas = entradas_df[(entradas_df['data'] >= start_date_dt) & (entradas_df['data'] <= end_date_dt)]
                        saidas_filtradas = saidas_df[(saidas_df['data'] >= start_date_dt) & (saidas_df['data'] <= end_date_dt)]

                        if cliente_filtro != "Todos":
                            entradas_filtradas = entradas_filtradas[entradas_filtradas['cliente'] == cliente_filtro]
                        if status_filtro and 'status' in entradas_filtradas.columns:
                            entradas_filtradas = entradas_filtradas[entradas_filtradas['status'].isin(status_filtro)]
                        
                        if tecnico_filtro:
                            regex_filtro = '|'.join(tecnico_filtro)
                            entradas_filtradas = entradas_filtradas[entradas_filtradas['nome_tecnicos'].str.contains(regex_filtro, na=False, regex=True)]
        else:
            st.warning("Nenhum dado lançado ainda.")

        # --- CONTAINER DE MÉTRICAS ---
        with st.container(border=True):
            st.subheader("💵 Resumo Financeiro do Período")
            total_entradas = entradas_filtradas['valor_atendimento'].sum() if 'valor_atendimento' in entradas_filtradas.columns else 0
            total_saidas = saidas_filtradas['valor'].sum() if 'valor' in saidas_filtradas.columns else 0
            lucro_real = total_entradas - total_saidas

            col1, col2, col3 = st.columns(3)
            col1.metric("🟢 Total de Entradas", f"R$ {total_entradas:,.2f}")
            col2.metric("🔴 Total de Saídas", f"R$ {total_saidas:,.2f}")
            col3.metric("💰 Lucro Real", f"R$ {lucro_real:,.2f}")

        # --- CONTAINER DE GRÁFICOS ---
        with st.container(border=True):
            st.subheader("📊 Análise Gráfica")
            col_charts1, col_charts2 = st.columns(2)
            
            with col_charts1:
                st.markdown("##### 🔴 Composição das Saídas")
                if not saidas_filtradas.empty:
                    fig = px.pie(saidas_filtradas, names='descricao', values='valor', title="Distribuição de Despesas")
                    fig.update_traces(hovertemplate='<b>%{label}</b><br>Valor: R$ %{value:,.2f}<extra></extra>')
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Nenhuma saída no período.")

            with col_charts2:
                st.markdown("##### 🟢 Composição das Entradas")
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

            st.markdown("---")
            st.markdown("##### 📅 Balanço Diário")
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

        # --- CONTAINER DE EXPORTAÇÃO E TABELAS ---
        with st.container(border=True):
            st.subheader("📥 Exportar e Visualizar Dados")
            if start_date and end_date:
                col_exp1, col_exp2 = st.columns(2)
                
                with col_exp1:
                    buffer = io.BytesIO()
                    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                        entradas_filtradas.to_excel(writer, index=False, sheet_name='Entradas')
                        saidas_filtradas.to_excel(writer, index=False, sheet_name='Saídas')
                    st.download_button(
                        label="📥 Baixar Relatório (Excel)",
                        data=buffer.getvalue(),
                        file_name=f"Relatorio_Financeiro_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
                
                with col_exp2:
                    pdf_bytes = gerar_pdf_financeiro(entradas_filtradas, saidas_filtradas, start_date, end_date)
                    st.download_button(
                        label="📄 Baixar Relatório (PDF)",
                        data=pdf_bytes,
                        file_name=f"Relatorio_Financeiro_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.pdf",
                        mime="application/pdf",
                        use_container_width=True
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
                "patrimonio": "Patrimônio", "maquina": "Máquina", "hora_inicio": "Início", "hora_fim": "Fim",
                "nome_tecnicos": "Técnico(s)"
            }
            with st.expander("Ver todos os registros de Entrada"):
                st.dataframe(entradas_df.sort_values(by='data', ascending=False), column_config=currency_columns, use_container_width=True, hide_index=True)
            with st.expander("Ver todos os registros de Saída"):
                st.dataframe(saidas_df.sort_values(by='data', ascending=False), column_config=currency_columns, use_container_width=True, hide_index=True)
