import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
import pandas as pd
from sqlalchemy import create_engine
from fpdf import FPDF
from datetime import datetime
import smtplib
import re
from urllib.parse import quote
from email.message import EmailMessage

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gerar PDF", page_icon="📄", layout="wide")

# --- VERIFICAÇÃO DE LOGIN ---
if "authentication_status" not in st.session_state:
    st.error("Por favor, faça login na página inicial.")
    st.stop()
elif st.session_state["authentication_status"] is False:
    st.error("Usuário ou senha inválidos. Volte à página inicial e tente novamente.")
    st.stop()
elif st.session_state["authentication_status"] is None:
    st.warning("Você precisa estar logado para acessar esta página.")
    st.stop()

# Se chegou aqui, está logado:
authenticator = None  # só para manter compatibilidade se precisar do logout
import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from menu import exibir_menu
exibir_menu()

st.title("📄 Gerar Relatório em PDF")
st.write("Selecione uma Ordem de Serviço abaixo para gerar um relatório em PDF para impressão.")

# Conexão com o banco de dados da nuvem a partir dos "Secrets"
connection_url = st.secrets["database"]["connection_url"]
engine = create_engine(connection_url)

# --- CLASSE PARA GERAR O PDF ---
class PDF(FPDF):
    def header(self):
        empresa_razao_social = "Elite CNC Service"
        empresa_cnpj = "CNPJ: 61.159.425/0001-32"
        empresa_endereco = "Rua da Paz, 230 - Santa Rita - Monte Alto SP"
        empresa_contato = "Tel: (11) 97761-7009 | Email: elitecncservice@gmail.com"    
        empresa_site = "www.elitecncservice.com.br"
        
        try:
            self.image('logo.png', 10, 1, 50)
        except FileNotFoundError:
            self.set_xy(10, 8)
            self.set_font('Arial', 'B', 12) 
            self.cell(50, 10, 'Logo N/A', 0, 1, 'L')

        self.set_font('DejaVu', '', 9)
        self.set_y(8) 
        self.set_x(-105) 
        self.cell(100, 5, empresa_razao_social, 0, 1, 'R')
        self.set_x(-105)
        self.cell(100, 5, empresa_cnpj, 0, 1, 'R')
        self.set_x(-105)
        self.cell(100, 5, empresa_endereco, 0, 1, 'R')
        self.set_x(-105)
        self.cell(100, 5, empresa_contato, 0, 1, 'R')
        self.set_x(-105)
        self.cell(100, 5, empresa_site, 0, 1, 'R')
        
        self.set_y(35)
        self.set_line_width(0.5)
        self.line(10, self.get_y(), 200, self.get_y()) 
        
        self.ln(3) 
        self.set_font('DejaVu', 'B', 16)
        self.cell(0, 10, 'RELATÓRIO DE SERVIÇOS', 0, 1, 'C')
        self.ln(8)

    def footer(self):
        self.set_y(-15)
        self.set_font('DejaVu', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

# --- FUNÇÃO PARA ENVIAR EMAIL COM ANEXO ---
def enviar_pdf_por_email(destinatario, assunto, corpo, dados_pdf, nome_arquivo_pdf):
    try:
        remetente = st.secrets["email_credentials"]["username"]
        senha = st.secrets["email_credentials"]["password"]
        msg = EmailMessage()
        msg['Subject'] = assunto
        msg['From'] = remetente
        msg['To'] = destinatario
        msg.set_content(corpo)
        
        corpo_html = corpo.replace('\n', '<br>')
        html_content = f"""\
        <html>
            <body style="font-family: Arial, sans-serif; color: #333333; line-height: 1.6;">
                <p>{corpo_html}</p>
                <br>
                <table border="0" cellpadding="0" cellspacing="0" style="font-family: Arial, sans-serif; color: #333333; line-height: 1.4;">
                    <tr>
                        <td style="padding-right: 15px; border-right: 2px solid #cccccc;">
                            <a href='https://postimg.cc/fVNyZqpf' target='_blank'>
                                <img src='https://i.postimg.cc/fVNyZqpf/Whats-App-Image-2025-01-06-at-16-03-50.jpg' border='0' alt='Elite CNC Service' style='max-width: 140px; height: auto;'>
                            </a>
                        </td>
                        <td style="padding-left: 15px;">
                            <strong style="font-size: 16px;">Filipe Guimarães</strong><br>
                            <span style="font-size: 14px; color: #666666;">Sócio Proprietário</span><br>
                            <span style="font-size: 13px;">
                            📞 WhatsApp: (11) 97761-7009<br>
                            ✉️ elitecncservice@gmail.com<br>
                            🌐 <a href="http://www.elitecncservice.com.br" style="color: #0056b3; text-decoration: none;">www.elitecncservice.com.br</a>
                            </span>
                        </td>
                    </tr>
                </table>
            </body>
        </html>
        """
        msg.add_alternative(html_content, subtype='html')
        
        msg.add_attachment(dados_pdf, maintype='application', subtype='pdf', filename=nome_arquivo_pdf)
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(remetente, senha)
            smtp.send_message(msg)
        st.success(f"Email com o relatório enviado com sucesso para {destinatario}!")
        return True
    except Exception as e:
        st.error(f"Falha ao enviar o email. Erro: {e}")
        st.error("Verifique as credenciais em secrets.toml e sua Senha de App.")
        return False

# --- FUNÇÃO PARA CARREGAR DADOS ---
@st.cache_data
def carregar_dados_completos():
    try:
        entradas_df = pd.read_sql("SELECT * FROM entradas", engine, parse_dates=['data'])
        clientes_df = pd.read_sql("SELECT nome, telefone, email, endereco, cnpj FROM clientes", engine)
        
        if not entradas_df.empty:
            merged_df = pd.merge(entradas_df, clientes_df, left_on='cliente', right_on='nome', how='left')
            return merged_df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Ocorreu um erro crítico ao buscar os dados: {e}")
        return pd.DataFrame()

# --- INTERFACE DO STREAMLIT ---
df_os = carregar_dados_completos()

if not df_os.empty and 'ordem_servico' in df_os.columns and not df_os['ordem_servico'].isnull().all():
    df_os_validas = df_os.dropna(subset=['ordem_servico']).copy()

    df_os_validas['display'] = df_os_validas.apply(
        lambda row: f"O.S. {row['ordem_servico']} - {row['cliente']} ({(row['data'].strftime('%d/%m/%Y') if pd.notnull(row['data']) else 'Data N/A')})",
        axis=1
    )
    
    os_selecionada_display = st.selectbox(
        "Selecione a Ordem de Serviço:",
        options=[""] + df_os_validas['display'].tolist()
    )

    if os_selecionada_display:
        os_details = df_os_validas[df_os_validas['display'] == os_selecionada_display].iloc[0]
        telefone_cliente = os_details.get('telefone_y', os_details.get('telefone', 'N/A'))
        email_cliente = os_details.get('email_y', os_details.get('email', None))

        st.markdown("---")
        
        pdf = PDF()
        try:
            pdf.add_font('DejaVu', '', 'DejaVuSans.ttf')
            pdf.add_font('DejaVu', 'B', 'DejaVuSans-Bold.ttf')
            pdf.add_font('DejaVu', 'I', 'DejaVuSans-Oblique.ttf')
        except FileNotFoundError:
            st.error("Arquivos de fonte (DejaVu) não encontrados.")
        
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        y_inicial_colunas = pdf.get_y()
        pdf.set_font('DejaVu', 'B', 12)
        pdf.cell(95, 8, 'DADOS DO CLIENTE', 'B', 1, 'L')
        pdf.ln(2)
        pdf.set_font('DejaVu', '', 10)
        pdf.multi_cell(95, 6, f"Nome: {os_details.get('cliente', 'N/A')}\n"
                             f"CNPJ: {os_details.get('cnpj', 'N/A')}\n"
                             f"Telefone: {telefone_cliente}\n"
                             f"Endereço: {os_details.get('endereco', 'N/A')}")
        # BLOCO NOVO E CORRIGIDO
        y_final_coluna_esquerda = pdf.get_y()
        pdf.set_y(y_inicial_colunas)
        pdf.set_x(105)
        pdf.set_font('DejaVu', 'B', 12)
        pdf.cell(95, 8, 'DADOS DO SERVIÇO', 'B', 1, 'L')
        pdf.ln(2)
        pdf.set_x(105)
        pdf.set_font('DejaVu', '', 10)

        # Monta a lista de detalhes do serviço dinamicamente
        detalhes_servico = []
        detalhes_servico.append(f"Nº da O.S.: {os_details.get('ordem_servico', 'N/A')}")
        data_servico_str = os_details['data'].strftime('%d/%m/%Y') if pd.notnull(os_details.get('data')) else 'Data N/A'
        detalhes_servico.append(f"Data: {data_servico_str}")
        
        # Adiciona máquina e patrimônio apenas se existirem
        if os_details.get('maquina') and pd.notnull(os_details.get('maquina')):
            detalhes_servico.append(f"Máquina: {os_details.get('maquina')}")
        if os_details.get('patrimonio') and pd.notnull(os_details.get('patrimonio')):
            detalhes_servico.append(f"Patrimônio: {os_details.get('patrimonio')}")

        nome_tecnicos = os_details.get('nome_tecnicos')
        if nome_tecnicos and pd.notnull(nome_tecnicos) and str(nome_tecnicos).strip() != "":
            detalhes_servico.append(f"Técnico(s): {nome_tecnicos}")
        else:
            detalhes_servico.append(f"Técnicos: {os_details.get('qtd_tecnicos', 1)}")
            
        detalhes_servico.append(f"Início: {os_details.get('hora_inicio', 'N/A')}")
        detalhes_servico.append(f"Fim: {os_details.get('hora_fim', 'N/A')}")
        
        # Junta as linhas e escreve no PDF
        texto_final_servico = "\n".join(detalhes_servico)
        pdf.multi_cell(95, 6, texto_final_servico)
        # ----------------------

        y_final_coluna_direita = pdf.get_y()
        pdf.set_y(max(y_final_coluna_esquerda, y_final_coluna_direita) + 5)
        pdf.set_font('DejaVu', 'B', 12)
        pdf.cell(0, 8, 'DESCRIÇÃO DOS SERVIÇOS REALIZADOS', 'B', 1, 'L')
        pdf.ln(2)
        pdf.set_font('DejaVu', '', 10)
        pdf.multi_cell(0, 6, os_details.get('descricao_servico', 'Nenhuma descrição fornecida.'))
        pdf.ln(10)
        pdf.set_font('DejaVu', 'B', 12)
        pdf.cell(0, 8, 'VALORES', 'B', 1, 'L')
        pdf.ln(2)
        pdf.set_font('DejaVu', 'B', 10)
        pdf.cell(150, 7, 'Descrição', 1, 0, 'C')
        pdf.cell(40, 7, 'Valor', 1, 1, 'C')
        pdf.set_font('DejaVu', '', 10)
        valores = {
            "Horas Técnicas Normais": os_details.get('horas_tecnicas', 0),
            "Horas Técnicas 50%": os_details.get('horas_tecnicas_50', 0),
            "Horas Técnicas 100%": os_details.get('horas_tecnicas_100', 0),
            "Valor de Deslocamento": os_details.get('valor_deslocamento_total', 0),
            "Deslocamento (KM)": os_details.get('km', 0),
            "Refeição": os_details.get('refeicao', 0),
            "Peças": os_details.get('pecas', 0),
            "Pedágio": os_details.get('pedagio', 0),
            "Valor Laboratório": os_details.get('valor_laboratorio', 0)
        }
        for descricao, valor in valores.items():
            if isinstance(valor, (int, float)) and valor > 0:
                pdf.cell(150, 7, f"   {descricao}", 'LR', 0)
                pdf.cell(40, 7, f"R$ {valor:.2f}".replace('.', ','), 'LR', 1, 'R')
        pdf.set_font('DejaVu', 'B', 11)
        pdf.cell(150, 8, 'VALOR TOTAL', 1, 0, 'R')
        pdf.cell(40, 8, f"R$ {os_details.get('valor_atendimento', 0):.2f}".replace('.', ','), 1, 1, 'R')
        
        pdf_bytes = bytes(pdf.output())
        nome_arquivo = f"Relatorio_OS_{os_details.get('ordem_servico', 'N_A')}.pdf"
        
        st.subheader("Ações do Relatório")
        st.download_button(
            label="📥 Baixar PDF",
            data=pdf_bytes,
            file_name=nome_arquivo,
            mime="application/pdf",
            use_container_width=True
        )

        # Mensagem padrão para envio
        mensagem_envio = f"Prezado(a) {os_details.get('cliente')},\n\nSegue em anexo o relatório de serviço referente à O.S. nº {os_details.get('ordem_servico')}.\n\nQualquer dúvida, estamos à disposição.\n\nAtenciosamente,"

        col_acao1, col_acao2 = st.columns(2)

        # --- Enviar via WhatsApp ---
        with col_acao1:
            if telefone_cliente and pd.notnull(telefone_cliente):
                numero_limpo = re.sub(r'\D', '', str(telefone_cliente))
                if not numero_limpo.startswith('55'):
                    numero_limpo = '55' + numero_limpo
                
                # Mensagem para WhatsApp não inclui o anexo, apenas notifica.
                mensagem_whatsapp = f"Olá {os_details.get('cliente')}, tudo bem?\n\nEstou enviando o relatório de serviço da O.S. nº {os_details.get('ordem_servico')} para o seu e-mail.\n\nPor favor, verifique sua caixa de entrada.\n\nQualquer dúvida, estou à disposição."
                mensagem_url = quote(mensagem_whatsapp)
                link_whatsapp = f"https://wa.me/{numero_limpo}?text={mensagem_url}"
                # Usar st.markdown para um link mais robusto
                st.markdown(
                    f'<a href="{link_whatsapp}" target="_blank" style="display: inline-block; text-align: center; width: 100%; padding: 0.25rem 0.75rem; background-color: #fafafa; color: #262730; border: 1px solid rgba(49, 51, 63, 0.2); border-radius: 0.5rem; text-decoration: none;">📲 Enviar via WhatsApp</a>',
                    unsafe_allow_html=True
                )

            else:
                st.button("📲 Enviar via WhatsApp", use_container_width=True, disabled=True)
                st.caption("Cliente sem telefone.")
            
        # --- Enviar por Email ---
        with col_acao2:
            if email_cliente and pd.notnull(email_cliente):
                if st.button("✉️ Enviar por Email", use_container_width=True, type="primary"):
                    with st.spinner(f"Enviando para {email_cliente}..."):
                        enviar_pdf_por_email(
                            destinatario=email_cliente,
                            assunto=f"Relatório de Serviço - O.S. {os_details.get('ordem_servico')}",
                            corpo=mensagem_envio,
                            dados_pdf=pdf_bytes,
                            nome_arquivo_pdf=nome_arquivo
                        )
            else:
                st.button("✉️ Enviar por Email", use_container_width=True, disabled=True)
                st.caption("Cliente sem email cadastrado.")

else:
    st.info("Nenhuma Ordem de Serviço válida foi encontrada para gerar relatórios.")