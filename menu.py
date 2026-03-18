import streamlit as st

def exibir_menu(authenticator=None):
    # Usamos colunas para criar uma barra de navegação superior
    # O parâmetro 'vertical_alignment' centraliza perfeitamente a logo e os botões
    c1, c2, c3, c4, c5, c6, c7, c8 = st.columns([1.5, 0.9, 1, 1.3, 1.3, 0.9, 1, 0.9], vertical_alignment="center")

    with c1:
        st.image("logo.png", width=120)
    
    with c2:
        st.page_link("1_📊_Dashboard.py", label="Dashboard", icon="📊")
        
    with c3:
        st.page_link("pages/2_⭐_Clientes.py", label="Clientes", icon="⭐")
        
    # Submenu: Relatórios (Usando Popover que funciona como Dropdown)
    with c4:
        with st.popover("📁 Relatórios", use_container_width=True):
            st.page_link("pages/4_📄_Gerar_Relatório_PDF.py", label="Gerar PDF", icon="📄")
            st.page_link("pages/8_📦_Compilar_Relatórios.py", label="Compilar", icon="📦")
            st.page_link("pages/5_💲_Fechamento.py", label="Fechamento", icon="💲")

    # Submenu: Financeiro (Usando Popover)
    with c5:
        with st.popover("💼 Financeiro", use_container_width=True):
            st.page_link("pages/9_💰_Controle_Financeiro.py", label="Controle", icon="💰")
            st.page_link("pages/6_🌊_Fluxo_de_Caixa.py", label="Fluxo", icon="🌊")
            st.page_link("pages/6_💸_Enviar_Boleto.py", label="Boleto", icon="💸")
            st.page_link("pages/7_🧾_Enviar_Nota_Fiscal.py", label="Nota", icon="🧾")

    with c6:
        st.page_link("pages/10_🔬_Laboratório.py", label="Laboratório", icon="🔬")
        
    with c7:
        st.page_link("pages/11_📦_Estoque.py", label="Estoque", icon="📦")
        
    with c8:
        if authenticator:
            authenticator.logout('Sair', 'main')
        else:
            st.button("Sair", on_click=lambda: st.session_state.update({"authentication_status": None}), use_container_width=True)

    # Injetamos o CSS no final para garantir que as colunas acima sejam o "primeiro elemento" da tela
    st.markdown("""
        <style>
            /* Esconde a barra lateral nativa inteira e a barra superior do Streamlit */
            [data-testid="collapsedControl"] {display: none;}
            section[data-testid="stSidebar"] {display: none;}
            header[data-testid="stHeader"] {display: none;}
            .block-container {padding-top: 1rem;} 
            
            /* Estiliza o contêiner do menu superior */
            div.block-container > div > div:first-child {
                background-color: var(--secondary-background-color);
                padding: 10px 15px;
                border-radius: 10px;
                box-shadow: 0px 4px 10px rgba(0,0,0,0.1);
                margin-bottom: 20px;
            }
        
        /* Ajusta os links de página para terem a mesma altura e alinhamento visual dos botões com borda */
        div[data-testid="stPageLink-NavLink"] {
            display: flex;
            align-items: center;
            height: 38px;
        }
        
        /* Zera o espaçamento nativo entre as colunas do cabeçalho */
        div.block-container > div > div:first-child div[data-testid="stHorizontalBlock"] {
            gap: 0px !important;
        }
        
        /* Remove as margens internas laterais para os botões ficarem bem próximos */
        div.block-container > div > div:first-child div[data-testid="column"] {
            padding-left: 2px !important;
            padding-right: 2px !important;
        }
        </style>
    """, unsafe_allow_html=True)