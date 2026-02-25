import streamlit as st
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine, text
from fpdf import FPDF
import io

# --- VERIFICAÇÃO DE LOGIN ---
if "authentication_status" not in st.session_state or not st.session_state["authentication_status"]:
    st.error("Acesso negado. Por favor, faça login na página inicial.")
    st.stop()

st.sidebar.image("logo.png", width=150)
st.sidebar.button("Sair", on_click=lambda: st.session_state.update({"authentication_status": None}))

# --- CONFIGURAÇÃO DA PÁGINA E CONEXÃO COM DB ---
st.set_page_config(page_title="Lançamento de Laboratório", page_icon="🔬", layout="wide")
st.title("🔬 Lançamento de Laboratório")
st.write("Use esta tela para registrar serviços realizados exclusivamente no laboratório.")

connection_url = st.secrets["database"]["connection_url"]
engine = create_engine(connection_url)

# --- FUNÇÕES AUXILIARES ---

@st.cache_data(ttl=600)
def carregar_clientes():
    """Carrega a lista de nomes de clientes do banco de dados."""
    try:
        clientes_df = pd.read_sql_query("SELECT nome FROM clientes ORDER BY nome", engine)
        return [""] + clientes_df['nome'].tolist()
    except Exception as e:
        st.error(f"Erro ao carregar clientes: {e}")
        return [""]

@st.cache_data(ttl=300)
def carregar_lancamentos_recentes():
    """Carrega os 50 lançamentos de entrada mais recentes para gerenciamento."""
    query = "SELECT id, data, ordem_servico, cliente, valor_atendimento, status, nome_tecnicos FROM entradas ORDER BY data DESC LIMIT 50"
    df = pd.read_sql_query(query, engine, parse_dates=['data'])
    return df


def safe_number(value, default=0.0):
    """Converte valor para float de forma segura."""
    try:
        return float(value) if value else default
    except (ValueError, TypeError):
        return default

def deletar_lancamento(id_lancamento):
    """Exclui um lançamento da tabela de entradas."""
    try:
        with engine.connect() as con:
            con.execute(text("DELETE FROM entradas WHERE id = :id"), {"id": id_lancamento})
            con.commit()
        st.success("Lançamento excluído com sucesso!")
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Erro ao excluir lançamento: {e}")

def atualizar_lancamento(id_lancamento, dados):
    """Atualiza um lançamento na tabela de entradas."""
    try:
        with engine.connect() as con:
            set_clause = ", ".join([f"{key} = :{key}" for key in dados.keys()])
            dados['id'] = id_lancamento
            query = text(f"UPDATE entradas SET {set_clause} WHERE id = :id")
            con.execute(query, dados)
            con.commit()
        st.success("Lançamento atualizado com sucesso!")
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Erro ao atualizar lançamento: {e}")

def gerar_etiqueta_pdf(id_lancamento):
    """Gera uma etiqueta PDF 100x60mm para o lançamento."""
    try:
        # Busca os dados completos do lançamento
        dados = pd.read_sql_query(f"SELECT * FROM entradas WHERE id = {id_lancamento}", engine).iloc[0]
        
        # Configuração do PDF (Paisagem, mm, 100x60 - Tamanho comum de etiqueta térmica)
        pdf = FPDF('L', 'mm', (60, 100))
        pdf.set_margins(3, 3, 3)
        pdf.add_page()

        # Tenta usar fonte DejaVu se disponível, senão Arial
        try:
            pdf.add_font('DejaVu', '', 'DejaVuSans.ttf')
            pdf.add_font('DejaVu', 'B', 'DejaVuSans-Bold.ttf')
            pdf.set_font('DejaVu', 'B', 10)
        except:
            pdf.set_font('Arial', 'B', 10)

        # Cabeçalho
        pdf.cell(0, 5, "ELITE CNC - LABORATÓRIO", 0, 1, 'C')
        pdf.line(2, 9, 98, 9)
        pdf.ln(4)

        # Número da O.S. em destaque
        pdf.set_font(size=16)
        pdf.cell(0, 8, f"O.S.: {dados['ordem_servico']}", 0, 1, 'C')
        pdf.ln(2)

        # Detalhes
        pdf.set_font(size=9)
        pdf.cell(0, 5, f"Cliente: {str(dados['cliente'])[:28]}", 0, 1, 'L')
        pdf.cell(0, 5, f"Data: {pd.to_datetime(dados['data']).strftime('%d/%m/%Y')}", 0, 1, 'L')
        pdf.cell(0, 5, f"Equip: {str(dados['maquina'])[:28]}", 0, 1, 'L')
        pdf.cell(0, 5, f"Patrimônio: {str(dados['patrimonio'])[:20]}", 0, 1, 'L')

        return bytes(pdf.output())
    except Exception as e:
        st.error(f"Erro ao gerar etiqueta: {e}")
        return None

# --- CARREGANDO DADOS ---
clientes_cadastrados = carregar_clientes()

# --- GERENCIAMENTO DE ESTADO DE EDIÇÃO ---
if 'edit_lab_id' not in st.session_state:
    st.session_state.edit_lab_id = None

edit_data = None
if st.session_state.edit_lab_id:
    try:
        edit_df = pd.read_sql_query(f"SELECT * FROM entradas WHERE id = {st.session_state.edit_lab_id}", engine)
        if not edit_df.empty:
            edit_data = edit_df.iloc[0].to_dict()
            st.info(f"📝 Editando lançamento ID: {st.session_state.edit_lab_id}. Clique em 'Cancelar Edição' para voltar.")
    except Exception as e:
        st.error(f"Erro ao carregar dados para edição: {e}")
        st.session_state.edit_lab_id = None

# --- FORMULÁRIO DE LANÇAMENTO ---
col1, col2 = st.columns([2, 1], gap="large")

with col1:
    # Define os valores padrão com base no modo (novo ou edição)
    data_default = edit_data['data'].date() if edit_data and pd.notnull(edit_data.get('data')) else datetime.now().date()
    os_id_default = edit_data.get('ordem_servico', '') if edit_data else ''
    cliente_default = edit_data.get('cliente', '') if edit_data else ''
    equipamento_default = edit_data.get('maquina', '') if edit_data else ''
    tecnico_default = edit_data.get('nome_tecnicos', st.session_state.get("username", "")) if edit_data else st.session_state.get("username", "")
    
    # Extrai o modelo da descrição, se possível
    descricao_completa_default = edit_data.get('descricao_servico', '') if edit_data else ''
    modelo_default = ''
    descricao_servico_default = descricao_completa_default
    if "Modelo:" in descricao_completa_default:
        parts = descricao_completa_default.split("--------------------", 1)
        if len(parts) == 2:
            modelo_default = parts[0].replace("Modelo:", "").strip()
            descricao_servico_default = parts[1].strip()

    numero_serie_default = edit_data.get('patrimonio', '') if edit_data else ''
    valor_lab_default = float(edit_data.get('valor_laboratorio', 0.0)) if edit_data else 0.0
    pecas_default = float(edit_data.get('pecas', 0.0)) if edit_data else 0.0

    with st.form("form_laboratorio", clear_on_submit=(st.session_state.edit_lab_id is None)):
        st.subheader("📝 Detalhes do Serviço" if not edit_data else f"📝 Editando O.S. {os_id_default}")
        
        with st.container(border=True):
            # --- CAMPOS DO FORMULÁRIO ---
            st.markdown("##### 🛠️ Dados do Equipamento")
            c1, c2 = st.columns(2)
            with c1:
                data_atendimento = st.date_input("Data do Atendimento", value=data_default)
                cliente_index = clientes_cadastrados.index(cliente_default) if cliente_default in clientes_cadastrados else 0
                cliente = st.selectbox("Cliente", options=clientes_cadastrados, index=cliente_index)
                equipamento = st.text_input("Equipamento", value=equipamento_default)
                numero_serie = st.text_input("Número de Série (Patrimônio)", value=numero_serie_default)
            
            with c2:
                os_id = st.text_input("Nº da O.S.", value=os_id_default)
                tecnico_responsavel = st.text_input("Técnico Responsável", value=tecnico_default)
                modelo = st.text_input("Modelo", value=modelo_default)
                # Espaçador visual para alinhar
                st.write("")
            
            st.markdown("---")
            st.markdown("##### 📝 Descrição e Valores")
            descricao_servico = st.text_area("Descrição do Serviço Realizado", value=descricao_servico_default, height=100)
            
            
            c_val1, c_val2 = st.columns(2)
            with c_val1:
                valor_laboratorio = st.number_input("Mão de Obra (Laboratório)", min_value=0.0, format="%.2f", value=valor_lab_default)
            with c_val2:
                pecas_utilizadas = st.number_input("Peças Utilizadas", min_value=0.0, format="%.2f", value=pecas_default)

            submit_button_text = "💾 Salvar Alterações" if st.session_state.edit_lab_id else "✅ Lançar Serviço"
            submit_button = st.form_submit_button(submit_button_text, use_container_width=True, type="primary")

        if submit_button:
            if not cliente or not os_id:
                st.error("Os campos 'Cliente' e 'Nº da O.S.' são obrigatórios.")
            else:
                # Combina as descrições em um único campo para o banco de dados
                descricao_completa = (
                    f"Modelo: {modelo}\n"
                    f"--------------------\n"
                    f"{descricao_servico}"
                )

                valor_total = safe_number(valor_laboratorio) + safe_number(pecas_utilizadas)

                dados_lancamento = {
                    'data': pd.to_datetime(data_atendimento),
                    'ordem_servico': os_id,
                    'cliente': cliente,
                    'maquina': equipamento,
                    'patrimonio': numero_serie,
                    'descricao_servico': descricao_completa,
                    'pecas': safe_number(pecas_utilizadas),
                    'valor_laboratorio': safe_number(valor_laboratorio),
                    'valor_atendimento': valor_total,
                    'status': 'Pendente', # O lançamento já entra como pendente de pagamento
                    'usuario_lancamento': st.session_state.get("username", "n/a"),
                    'nome_tecnicos': tecnico_responsavel,
                    'qtd_tecnicos': 1, # Define como 1 para contar nos relatórios de produtividade
                    # Zerando outros campos numéricos para consistência
                    'horas_tecnicas': 0, 'horas_tecnicas_50': 0, 'horas_tecnicas_100': 0,
                    'km': 0, 'refeicao': 0, 'pedagio': 0, 'valor_deslocamento': 0
                }

                if st.session_state.edit_lab_id:
                    # Modo de atualização
                    atualizar_lancamento(st.session_state.edit_lab_id, dados_lancamento)
                    st.session_state.edit_lab_id = None # Limpa o estado de edição
                    st.rerun()
                else:
                    # Modo de inserção
                    try:
                        pd.DataFrame([dados_lancamento]).to_sql('entradas', engine, if_exists='append', index=False)
                        st.success(f"Serviço de laboratório para O.S. '{os_id}' lançado com sucesso!")
                    except Exception as e:
                        st.error(f"Ocorreu um erro ao salvar no banco de dados: {e}")

with col2:
    with st.container(border=True):
        st.image("logo.png", use_container_width=True)
        st.info(
            "**Fluxo de Trabalho:**\n\n"
            "1. Preencha os dados do serviço.\n"
            "2. Valor Total = **Mão de Obra** + **Peças**.\n"
            "3. Gera uma **entrada pendente**.\n"
            "4. Baixe no **Controle Financeiro**."
        )

    st.write("")

    with st.container(border=True):
        st.subheader("⚙️ Histórico Recente")

        if st.session_state.edit_lab_id:
            st.warning(f"Editando ID: {st.session_state.edit_lab_id}")
            if st.button("❌ Cancelar Edição", use_container_width=True):
                st.session_state.edit_lab_id = None
                st.rerun()

        df_gerenciar = carregar_lancamentos_recentes()

        if not df_gerenciar.empty:
            # Ordena para garantir que o mais recente apareça primeiro na lista
            df_gerenciar['display'] = df_gerenciar.apply(
                lambda row: f"{'✅' if row.get('status') == 'Pago' else '⏳'} {row['data'].strftime('%d/%m')} - {str(row.get('cliente') or 'N/A').split()[0]} - O.S. {row.get('ordem_servico', 'N/A')} (ID: {row['id']})",
                axis=1
            )
            lancamento_selecionado = st.selectbox(
                "Selecione para editar ou excluir:",
                options=[""] + df_gerenciar['display'].tolist()
            )

            if lancamento_selecionado:
                # Extrai o ID do final da string "(ID: 123)"
                id_selecionado = int(lancamento_selecionado.split("(ID: ")[1].replace(")", "").strip())
                
                btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 1.5])
                if btn_col1.button("📝 Editar", key=f"edit_{id_selecionado}", use_container_width=True):
                    st.session_state.edit_lab_id = id_selecionado
                    st.rerun()
                
                if btn_col2.button("🗑️ Excluir", type="primary", key=f"delete_{id_selecionado}", use_container_width=True):
                    deletar_lancamento(id_selecionado)
                    st.rerun()
                
                # Botão de Etiqueta
                pdf_bytes = gerar_etiqueta_pdf(id_selecionado)
                if pdf_bytes:
                    btn_col3.download_button("🖨️ Etiqueta", data=pdf_bytes, file_name=f"Etiqueta_OS_{id_selecionado}.pdf", mime="application/pdf", use_container_width=True)