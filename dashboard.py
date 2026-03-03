import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from supabase import create_client, Client
import google.generativeai as genai
import os
from datetime import datetime
from dotenv import load_dotenv

# --- CONFIGURAÇÃO INICIAL ---
load_dotenv()

# --- CONFIGURAÇÃO IA ---
api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-1.5-flash')

# --- SUPABASE CONNECTION ---
@st.cache_resource
def init_supabase():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if url and key:
        return create_client(url, key)
    return None

supabase = init_supabase()

# --- SESSION STATE ---
if 'historico_chat' not in st.session_state:
    st.session_state.historico_chat = []
if 'log_mudancas' not in st.session_state:
    st.session_state.log_mudancas = []
if 'volume_mensal' not in st.session_state:
    st.session_state.volume_mensal = 100
if 'aplicar_preco_rapido' not in st.session_state:
    st.session_state.aplicar_preco_rapido = None
if 'meta_mensal' not in st.session_state:
    st.session_state.meta_mensal = 50000.0
if 'filtro_status' not in st.session_state:
    st.session_state.filtro_status = "Todos"

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Rumo BI | Gestão de Elite", layout="wide", page_icon="📈")

# --- CSS AVANÇADO ---
st.markdown("""
<style>
    /* Cores Base */
    :root {
        --primary: #0F172A;
        --secondary: #1E293B;
        --accent: #0EA5E9;
        --success: #10B981;
        --warning: #F59E0B;
        --danger: #EF4444;
        --text: #F1F5F9;
        --text-dim: #94A3B8;
    }
    
    .stApp { 
        background: linear-gradient(135deg, #0F172A 0%, #1A1F35 100%) !important;
    }
    
    /* Métricas Premium */
    [data-testid="stMetric"] {
        background: linear-gradient(135deg, #1E293B 0%, #2D3A52 100%) !important;
        border: 1px solid rgba(14, 165, 233, 0.2) !important;
        border-radius: 16px !important;
        padding: 20px !important;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3) !important;
        transition: all 0.3s ease !important;
    }
    
    [data-testid="stMetric"]:hover {
        border-color: rgba(14, 165, 233, 0.8) !important;
        box-shadow: 0 8px 30px rgba(14, 165, 233, 0.2) !important;
        transform: translateY(-4px) !important;
    }
    
    [data-testid="stMetricValue"] { 
        color: #0EA5E9 !important;
        font-size: 28px !important;
        font-weight: 700 !important;
    }
    
    [data-testid="stMetricLabel"] { 
        color: #94A3B8 !important;
        font-size: 14px !important;
        font-weight: 600 !important;
    }
    
    /* Headers */
    h1, h2, h3 { 
        color: #F1F5F9 !important;
        font-weight: 700 !important;
        letter-spacing: -0.5px !important;
    }
    
    h1 { font-size: 2.5em !important; }
    h2 { font-size: 1.8em !important; margin-top: 30px !important; }
    h3 { font-size: 1.3em !important; }
    
    /* Cards de Alerta */
    .stAlert {
        border-radius: 12px !important;
        border-left: 4px solid !important;
        padding: 15px !important;
    }
    
    .stSuccess { border-left-color: #10B981 !important; }
    .stError { border-left-color: #EF4444 !important; }
    .stWarning { border-left-color: #F59E0B !important; }
    
    /* Sidebar */
    [data-testid="stSidebar"] { 
        background: linear-gradient(180deg, #1E293B 0%, #233A5F 100%) !important;
        border-right: 1px solid rgba(14, 165, 233, 0.1) !important;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px !important;
        border-bottom: 2px solid #334155 !important;
    }
    
    .stTabs [aria-selected="true"] {
        border-bottom: 3px solid #0EA5E9 !important;
        color: #0EA5E9 !important;
    }
    
    /* Botões */
    .stButton > button {
        background: linear-gradient(135deg, #0EA5E9 0%, #0284C7 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 10px !important;
        padding: 12px 24px !important;
        font-weight: 600 !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 4px 15px rgba(14, 165, 233, 0.3) !important;
    }
    
    .stButton > button:hover {
        box-shadow: 0 8px 25px rgba(14, 165, 233, 0.5) !important;
        transform: translateY(-2px) !important;
    }
    
    /* Dividers */
    .element-container:has(> .stMarkdown hr) {
        margin: 30px 0 !important;
    }
    
    hr {
        border: 1px solid rgba(14, 165, 233, 0.2) !important;
    }
</style>
""", unsafe_allow_html=True)

# --- HELPERS ---
def formatar_brl(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def get_nome_col(df):
    for col in ['nome', 'produto', 'name', 'product']:
        if col in df.columns:
            return col
    return df.columns[0] if len(df.columns) > 0 else 'nome'

# --- EXPORTAÇÃO ---
def gerar_csv_produtos(df, nome_col):
    """Gera CSV com análise completa de produtos"""
    df_export = df[[nome_col, 'preco_venda', 'custo_unitario', 'margem_pct', 'status', 'lucro_total_mensal']].copy()
    df_export.columns = ['Produto', 'Preço Venda', 'Custo Unitário', 'Margem %', 'Status', 'Lucro Mensal']
    df_export['Preço Venda'] = df_export['Preço Venda'].apply(formatar_brl)
    df_export['Custo Unitário'] = df_export['Custo Unitário'].apply(formatar_brl)
    df_export['Lucro Mensal'] = df_export['Lucro Mensal'].apply(formatar_brl)
    return df_export.to_csv(index=False, encoding='utf-8-sig').encode('utf-8')

# --- BANCO DE DADOS ---
@st.cache_data(ttl=5)
def buscar_dados_supabase():
    if not supabase:
        st.error("❌ Erro: Supabase não configurado. Verifique .env")
        return pd.DataFrame()
    try:
        response = supabase.table('produtos').select('*').execute()
        df = pd.DataFrame(response.data)
        # Normalização de Elite: nomes de colunas sempre em minúsculo
        df.columns = [str(col).lower().strip() for col in df.columns]
        return df
    except Exception as e:
        st.error(f"❌ Erro Supabase: {e}")
        return pd.DataFrame()

def registrar_auditoria(produto_id, novo_preco, novo_custo, produto_nome, preco_antigo, custo_antigo):
    """Registra a mudança em tabela de auditoria no Supabase"""
    if not supabase or produto_id is None:
        return False
    try:
        supabase.table('audit_log').insert({
            'produto_id': produto_id,
            'produto_nome': produto_nome,
            'preco_antigo': float(preco_antigo),
            'preco_novo': float(novo_preco),
            'custo_antigo': float(custo_antigo),
            'custo_novo': float(novo_custo),
            'timestamp': datetime.now().isoformat(),
            'data_mudanca': datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        }).execute()
        return True
    except Exception as e:
        # Se tabela não existir, apenas silencia o erro
        return False

def salvar_alteracao_supabase(produto_id, novo_preco, novo_custo, produto_nome, preco_antigo, custo_antigo):
    if not supabase or produto_id is None:
        return False
    try:
        # Salva no banco
        supabase.table('produtos').update({
            'preco_venda': float(novo_preco),
            'custo_unitario': float(novo_custo)
        }).eq('id', produto_id).execute()
        
        # Registra auditoria em paralelo (não impede o salvamento)
        registrar_auditoria(produto_id, novo_preco, novo_custo, produto_nome, preco_antigo, custo_antigo)
        return True
    except Exception as e:
        st.error(f"❌ Erro ao salvar: {e}")
        return False

# --- ENGINE ---
def processar_vendas(df, volume):
    if df.empty: return df
    df = df.copy()
    
    # Preenchimento de colunas operacionais que vimos no seu SQL
    for col in ['taxa_cartao_pct', 'custo_logistico', 'imposto_pct']:
        if col not in df.columns: df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    df['preco_venda'] = pd.to_numeric(df['preco_venda'], errors='coerce')
    df['custo_unitario'] = pd.to_numeric(df['custo_unitario'], errors='coerce')

    # Cálculos Reais de PME
    df['imposto_valor'] = df['preco_venda'] * df['imposto_pct']
    df['cartao_valor'] = df['preco_venda'] * df['taxa_cartao_pct']
    df['lucro_unitario'] = df['preco_venda'] - df['custo_unitario'] - df['imposto_valor'] - df['cartao_valor'] - df['custo_logistico']
    df['margem_pct'] = (df['lucro_unitario'] / df['preco_venda'] * 100).fillna(0)
    df['lucro_total_mensal'] = df['lucro_unitario'] * volume
    
    # Preço Ideal para 30% de Margem
    taxa_fixa = df['imposto_pct'] + df['taxa_cartao_pct']
    df['preco_ideal'] = (df['custo_unitario'] / (1 - 0.30 - taxa_fixa)).fillna(0)
    df['oportunidade'] = df['preco_ideal'] - df['preco_venda']
    
    df['status'] = df['margem_pct'].apply(lambda x: "🟢 SAUDÁVEL" if x >= 20 else ("🟡 ALERTA" if x >= 10 else "🔴 CRÍTICO"))
    return df

# --- UI INTERFACE ---
st.title("📊 Painel Financeiro de Produtos")
st.markdown("<h3 style='text-align: center; color: #4ade80;'>💰 Controle Inteligente de Margem e Lucratividade</h3>", unsafe_allow_html=True)

df = buscar_dados_supabase()

if not df.empty:
    with st.sidebar:
        st.markdown("<h2 style='text-align: center;'>🎮 Terminal</h2>", unsafe_allow_html=True)
        nome_col = get_nome_col(df)
        
        # --- META MENSAL ---
        with st.expander("🎯 Meta Mensal", expanded=True):
            meta_input = st.number_input(
                "Defina sua meta de lucro (R$)",
                min_value=1000.0,
                max_value=1000000.0,
                value=st.session_state.meta_mensal,
                step=1000.0,
                key="input_meta"
            )
            st.session_state.meta_mensal = meta_input
        
        st.markdown("---")
        
        # --- FILTROS AVANÇADOS ---
        with st.expander("🔍 Filtros Avançados", expanded=False):
            # Filtro por Status
            filtro_status = st.selectbox(
                "📊 Status do Produto",
                ["Todos", "🔴 Críticos", "🟡 Alertas", "🟢 Saudáveis"],
                key="select_status"
            )
            
            # Filtro por Faixa de Margem
            filtro_margem = st.slider(
                "📉 Faixa de Margem (%)",
                min_value=-100.0,
                max_value=100.0,
                value=(-100.0, 100.0),
                step=5.0
            )
        
        st.markdown("---")
        
        # Filtro por Categoria se existir
        if 'categoria' in df.columns:
            cat = st.selectbox("📂 Categoria", ["Todas"] + sorted(df['categoria'].unique().tolist()))
            if cat != "Todas": df = df[df['categoria'] == cat]

        selected_produto = st.selectbox("🛍️ Selecione um Produto", df[nome_col].unique())
        
        # Se veio de aplicar recomendação, muda para esse produto
        if st.session_state.aplicar_preco_rapido:
            produto_rapido = st.session_state.aplicar_preco_rapido
            selected_produto = produto_rapido['produto_nome']
        
        volume = st.slider("📦 Quantidade Mensal", 1, 10000, st.session_state['volume_mensal'])
        st.session_state['volume_mensal'] = volume
        
        st.markdown("---")
        
        # --- SIMULADOR RÁPIDO ---
        with st.expander("⚡ Simulador Rápido", expanded=False):
            st.caption("Simule aumentos em massa")
            aumento_simulacao = st.slider(
                "Aumentar preços em:",
                min_value=0,
                max_value=50,
                value=10,
                step=5,
                format="%d%%",
                key="slider_simulacao"
            )
            
            if st.button("🔮 Simular Impacto", use_container_width=True):
                df_temp = df.copy()
                df_temp['preco_simulado'] = df_temp['preco_venda'] * (1 + aumento_simulacao/100)
                df_temp['lucro_simulado'] = (df_temp['preco_simulado'] - df_temp['custo_unitario'] - 
                                             (df_temp['preco_simulado'] * df_temp['imposto_pct']) - 
                                             (df_temp['preco_simulado'] * df_temp['taxa_cartao_pct']) - 
                                             df_temp['custo_logistico'])
                df_temp['margem_simulada'] = (df_temp['lucro_simulado'] / df_temp['preco_simulado'] * 100)
                
                lucro_atual = (df_temp['lucro_unitario'] * volume).sum()
                lucro_simulado = (df_temp['lucro_simulado'] * volume).sum()
                diferenca = lucro_simulado - lucro_atual
                
                st.markdown(f"""
                <div style="background: rgba(14, 165, 233, 0.15); border: 1px solid rgba(14, 165, 233, 0.4); 
                            border-radius: 8px; padding: 12px; margin-top: 10px;">
                    <span style="color: #94A3B8; font-size: 12px;">💰 Impacto Estimado:</span><br>
                    <span style="color: #10B981; font-size: 20px; font-weight: 700;">{formatar_brl(diferenca)}/mês</span><br>
                    <span style="color: #94A3B8; font-size: 11px;">Lucro passaria de {formatar_brl(lucro_atual)} para {formatar_brl(lucro_simulado)}</span>
                </div>
                """, unsafe_allow_html=True)
        
        st.markdown("---")
        p_row = df[df[nome_col] == selected_produto].iloc[0]
        
        # Se veio de aplicar recomendação, já usa o novo preço
        preco_inicial = st.session_state.aplicar_preco_rapido['preco_novo'] if st.session_state.aplicar_preco_rapido else float(p_row['preco_venda'])
        
        novo_preco = st.slider("💵 Preço de Venda (R$)", float(p_row['preco_venda']*0.5), float(p_row['preco_venda']*2.0), preco_inicial, key="slider_preco")
        novo_custo = st.slider("📦 Custo Unitário (R$)", float(p_row['custo_unitario']*0.5), float(p_row['custo_unitario']*2.0), float(p_row['custo_unitario']), key="slider_custo")

        houve_alteracao = (novo_preco != float(p_row['preco_venda'])) or (novo_custo != float(p_row['custo_unitario']))

        if houve_alteracao:
            # Aviso especial se é uma alteração rápida
            if st.session_state.aplicar_preco_rapido:
                st.markdown(
                    f"""
                    <div style="
                        background: rgba(16, 185, 129, 0.25);
                        border: 1px solid rgba(16, 185, 129, 0.6);
                        border-radius: 10px;
                        padding: 12px;
                        margin-bottom: 10px;
                        color: #10B981;
                        font-size: 13px;
                        font-weight: 600;
                        text-align: center;
                    ">
                        🚀 Preço Recomendado Aplicado
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            
            st.markdown(
                f"""
                <div style="
                    background: rgba(16, 185, 129, 0.18);
                    border: 1px solid rgba(16, 185, 129, 0.35);
                    border-radius: 10px;
                    padding: 10px 12px;
                    margin-bottom: 8px;
                    color: #E2E8F0;
                    font-size: 14px;
                    line-height: 1.45;
                ">
                    <b>✏️ Alteração detectada</b><br>
                    <span>Preço: {formatar_brl(float(p_row['preco_venda']))} → {formatar_brl(novo_preco)}</span><br>
                    <span>Custo: {formatar_brl(float(p_row['custo_unitario']))} → {formatar_brl(novo_custo)}</span>
                </div>
                """,
                unsafe_allow_html=True
            )
            confirmar_salvar = st.checkbox(
                "Confirmo que desejo salvar esta alteração",
                key=f"confirmar_save_{p_row['id']}"
            )
            if st.button("💾 Salvar Alteração", use_container_width=True, disabled=not confirmar_salvar):
                if salvar_alteracao_supabase(p_row['id'], novo_preco, novo_custo, selected_produto, 
                                            float(p_row['preco_venda']), float(p_row['custo_unitario'])):
                    registro = (
                        f"{datetime.now().strftime('%d/%m %H:%M')} | {selected_produto} | "
                        f"Preço: {formatar_brl(float(p_row['preco_venda']))} → {formatar_brl(novo_preco)} | "
                        f"Custo: {formatar_brl(float(p_row['custo_unitario']))} → {formatar_brl(novo_custo)}"
                    )
                    st.session_state.log_mudancas.append(registro)
                    st.session_state.aplicar_preco_rapido = None  # Limpa a aplicação rápida
                    st.success("✅ Alteração salva com sucesso! (Registrada em auditoria)")
                    st.cache_data.clear()
                    st.rerun()
        else:
            st.caption("Nenhuma alteração pendente para salvar.")

        st.markdown("---")
        with st.expander("🕒 Histórico de Alterações", expanded=False):
            if st.session_state.log_mudancas:
                for item in reversed(st.session_state.log_mudancas[-10:]):
                    st.caption(f"• {item}")
            else:
                st.caption("Nenhuma alteração salva ainda.")
        
        with st.expander("📊 Auditoria Completa (Supabase)", expanded=False):
            st.caption("Histórico persistente de todas as mudanças")
            try:
                audit_response = supabase.table('audit_log').select('*').order('timestamp', desc=True).limit(20).execute()
                if audit_response.data:
                    audit_df = pd.DataFrame(audit_response.data)
                    for idx, row in audit_df.iterrows():
                        data =row.get('data_mudanca', 'N/A')
                        produto = row.get('produto_nome', '?')
                        preco_antes = formatar_brl(float(row.get('preco_antigo', 0)))
                        preco_depois = formatar_brl(float(row.get('preco_novo', 0)))
                        st.caption(f"• {data} | {produto}\n  Preço: {preco_antes} → {preco_depois}")
                else:
                    st.caption("Nenhum registro de auditoria ainda")
            except:
                st.caption("⚠️ Tabela de auditoria não encontrada (criada na primeira mudança)")

    # Processamento e KPIs
    df = processar_vendas(df, volume)
    
    # Aplicar filtros avançados
    if filtro_status == "🔴 Críticos":
        df = df[df['margem_pct'] < 10]
    elif filtro_status == "🟡 Alertas":
        df = df[(df['margem_pct'] >= 10) & (df['margem_pct'] < 20)]
    elif filtro_status == "🟢 Saudáveis":
        df = df[df['margem_pct'] >= 20]
    
    # Filtro por margem
    df = df[(df['margem_pct'] >= filtro_margem[0]) & (df['margem_pct'] <= filtro_margem[1])]
    
    if df.empty:
        st.warning("⚠️ Nenhum produto corresponde aos filtros selecionados.")
        st.stop()
    
    # Calcular Score de Saúde (0-100)
    df['score_saude'] = (
        (df['margem_pct'].clip(0, 50) / 50 * 40) +  # 40 pontos: margem
        (df['oportunidade'].clip(-50, 0) / 50 * 30 + 30) +  # 30 pontos: potencial (inverso)
        ((df['preco_venda'] > 10).astype(int) * 15) +  # 15 pontos: ticket médio
        ((df['lucro_unitario'] > 0).astype(int) * 15)  # 15 pontos: lucratividade
    ).clip(0, 100).round(0)
    
    p_data = df[df[nome_col] == selected_produto].iloc[0]

    # ========== META MENSAL PROGRESS ==========
    lucro_total_atual = df['lucro_total_mensal'].sum()
    progresso_meta = min((lucro_total_atual / st.session_state.meta_mensal) * 100, 100)
    falta_meta = max(st.session_state.meta_mensal - lucro_total_atual, 0)
    
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, rgba(14, 165, 233, 0.15) 0%, rgba(16, 185, 129, 0.15) 100%); 
                border: 1px solid rgba(14, 165, 233, 0.3); border-radius: 12px; padding: 20px; margin-bottom: 20px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
            <div>
                <h3 style="margin: 0; color: #F1F5F9; font-size: 1.2em;">🎯 Progresso da Meta Mensal</h3>
                <p style="margin: 5px 0 0 0; color: #94A3B8; font-size: 14px;">Meta: {formatar_brl(st.session_state.meta_mensal)} | Atual: {formatar_brl(lucro_total_atual)}</p>
            </div>
            <div style="text-align: right;">
                <span style="color: {'#10B981' if progresso_meta >= 100 else '#F59E0B'}; font-size: 32px; font-weight: 700;">{progresso_meta:.0f}%</span>
            </div>
        </div>
        <div style="background: rgba(0, 0, 0, 0.2); border-radius: 10px; height: 20px; overflow: hidden;">
            <div style="background: linear-gradient(90deg, #0EA5E9 0%, #10B981 100%); height: 100%; width: {progresso_meta}%; transition: width 0.3s ease;"></div>
        </div>
        <p style="margin: 10px 0 0 0; color: #94A3B8; font-size: 13px; text-align: center;">
            {('🎉 Meta atingida!' if progresso_meta >= 100 else f'Faltam {formatar_brl(falta_meta)} para atingir a meta')}
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # ========== SEÇÃO KPIs PREMIUM ==========
    st.markdown("### 📊 Métricas Principais")
    c1, c2, c3, c4, c5 = st.columns(5)
    
    with c1:
        margem_valor = p_data['margem_pct']
        delta_margem = margem_valor - 20
        st.metric(
            "💵 Margem Real",
            f"{margem_valor:.1f}%",
            delta=f"{delta_margem:+.1f}%",
            delta_color="normal" if delta_margem >= 0 else "inverse",
            help="Objetivo: ≥20% | 🟢 Saudável"
        )
    
    with c2:
        st.metric(
            "🎯 Lucro Unitário",
            formatar_brl(p_data['lucro_unitario']),
            help="Lucro líquido por unidade"
        )
    
    with c3:
        st.metric(
            "📈 Projeção Mensal",
            formatar_brl(p_data['lucro_total_mensal']),
            help=f"Em {volume} unidades"
        )
    
    with c4:
        status_icon = p_data['status'].split()[0]
        st.metric(
            "🏥 Status",
            p_data['status'].split()[1],
            help="Saúde financeira do produto"
        )
    
    with c5:
        score_cor = (
            "#10B981" if p_data['score_saude'] >= 70 else 
            ("#F59E0B" if p_data['score_saude'] >= 40 else "#EF4444")
        )
        st.markdown(f"""
        <div style="text-align: center; padding: 10px;">
            <span style="color: #94A3B8; font-size: 14px; font-weight: 600;">⭐ Score</span><br>
            <span style="color: {score_cor}; font-size: 28px; font-weight: 700;">{p_data['score_saude']:.0f}</span>
            <span style="color: #94A3B8; font-size: 16px;">/100</span>
        </div>
        """, unsafe_allow_html=True)

    # ========== EXECUTIVE SUMMARY ==========
    st.markdown("---")
    st.markdown("### 📈 Executive Summary")
    
    # Calcular insights agregados
    total_oportunidade = df[df['oportunidade'] > 0]['oportunidade'].sum()
    produtos_criticos_count = len(df[df['margem_pct'] < 10])
    economia_potencial = total_oportunidade * volume / 2
    top3_profit = df.nlargest(3, 'lucro_total_mensal')['lucro_total_mensal'].sum()
    concentracao = (top3_profit / df['lucro_total_mensal'].sum() * 100) if df['lucro_total_mensal'].sum() > 0 else 0
    
    exc1, exc2, exc3, exc4 = st.columns(4)
    with exc1:
        st.metric("💰 Oportunidade Total", formatar_brl(total_oportunidade * volume), help="Aumento potencial de margem/mês")
    with exc2:
        st.metric("🎯 Saúde Portfolio", f"{(100 - concentracao):.0f}%", help="Diversificação. >70% = Saudável")
    with exc3:
        preço_mediano = df['preco_venda'].median()
        margem_mediana = df['margem_pct'].median()
        st.metric("📍 Mediana", f"{margem_mediana:.1f}%", help=f"Preço mediano: {formatar_brl(preço_mediano)}")
    with exc4:
        meses_recuperacao = (total_oportunidade * volume / max(df['lucro_unitario'].sum() * volume, 1)) if total_oportunidade > 0 else 0
        st.metric("⏱️ Crescimento Potencial", f"+{min(meses_recuperacao * 100, 999):.0f}%", help="Aumento de lucro se implementar")
    
    # ========== SEÇÃO ALERTAS AUTOMÁTICOS ==========
    st.markdown("---")
    st.markdown("### 🚨 Alertas & Monitoramento")
    
    # Produtos críticos
    criticos = df[df['margem_pct'] < 10]
    alertas = df[(df['margem_pct'] >= 10) & (df['margem_pct'] < 20)]
    
    if not criticos.empty or not alertas.empty:
        col_alert1, col_alert2, col_alert3 = st.columns(3)
        
        # Card Críticos
        with col_alert1:
            num_criticos = len(criticos)
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, rgba(239, 68, 68, 0.15) 0%, rgba(220, 38, 38, 0.15) 100%); 
                        border: 1px solid rgba(239, 68, 68, 0.4);
                        border-radius: 10px; padding: 15px; text-align: center;">
                <h4 style="margin: 0; color: #EF4444; font-size: 1.1em;">🔴 CRÍTICO</h4>
                <p style="font-size: 24px; font-weight: 700; margin: 8px 0; color: #F1F5F9;">{num_criticos}</p>
                <p style="margin: 5px 0; font-size: 12px; color: #94A3B8;">Margem < 10%</p>
            </div>
            """, unsafe_allow_html=True)
        
        # Card Alerta
        with col_alert2:
            num_alertas = len(alertas)
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, rgba(245, 158, 11, 0.15) 0%, rgba(217, 119, 6, 0.15) 100%); 
                        border: 1px solid rgba(245, 158, 11, 0.4);
                        border-radius: 10px; padding: 15px; text-align: center;">
                <h4 style="margin: 0; color: #F59E0B; font-size: 1.1em;">🟡 ATENÇÃO</h4>
                <p style="font-size: 24px; font-weight: 700; margin: 8px 0; color: #F1F5F9;">{num_alertas}</p>
                <p style="margin: 5px 0; font-size: 12px; color: #94A3B8;">Margem 10-20%</p>
            </div>
            """, unsafe_allow_html=True)
        
        # Card Saudável
        with col_alert3:
            num_saudaveis = len(df[df['margem_pct'] >= 20])
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, rgba(16, 185, 129, 0.15) 0%, rgba(5, 150, 105, 0.15) 100%); 
                        border: 1px solid rgba(16, 185, 129, 0.4);
                        border-radius: 10px; padding: 15px; text-align: center;">
                <h4 style="margin: 0; color: #10B981; font-size: 1.1em;">🟢 SAUDÁVEL</h4>
                <p style="font-size: 24px; font-weight: 700; margin: 8px 0; color: #F1F5F9;">{num_saudaveis}</p>
                <p style="margin: 5px 0; font-size: 12px; color: #94A3B8;">Margem ≥ 20%</p>
            </div>
            """, unsafe_allow_html=True)
        
        # Produtos críticos em cards compactos com seleção em batch
        if not criticos.empty:
            with st.expander(f"🔴 {len(criticos)} produto(s) crítico(s) - Ação necessária", expanded=len(criticos) <= 2):
                st.markdown("**📋 Recomendação: Aumentar preço para atingir 20% de margem mínima**")
                st.markdown("**✅ Marque os produtos que deseja ajustar:**")
                st.markdown("---")
                
                # Preparar dados das alterações
                alteracoes_batch = []
                
                for idx, row in criticos.iterrows():
                    # Garante que nunca recomendamos diminuir preço
                    preco_novo = max(row['preco_ideal'], row['preco_venda'] * 1.15)
                    aumento_pct = ((preco_novo - row['preco_venda']) / row['preco_venda'] * 100)
                    margem_atual = max(-999, min(999, row['margem_pct']))
                    lucro_novo = preco_novo - row['custo_unitario'] - (preco_novo * row['imposto_pct']) - (preco_novo * row['taxa_cartao_pct']) - row['custo_logistico']
                    impacto_mensal = (lucro_novo - row['lucro_unitario']) * volume
                    
                    col_check, col_card = st.columns([0.5, 5])
                    
                    with col_check:
                        st.write("")
                        st.write("")
                        st.write("")
                        st.write("")
                        selecionar = st.checkbox(
                            "Aplicar",
                            key=f"check_{row['id']}",
                            label_visibility="collapsed"
                        )
                        
                        if selecionar:
                            alteracoes_batch.append({
                                'produto_id': row['id'],
                                'produto_nome': row[nome_col],
                                'preco_atual': float(row['preco_venda']),
                                'preco_novo': float(preco_novo),
                                'custo_atual': float(row['custo_unitario']),
                                'impacto_mensal': impacto_mensal
                            })
                    
                    with col_card:
                        # Card visual
                        html_card = f"""
<div style="background: rgba(239, 68, 68, 0.08); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 10px; padding: 14px; margin-bottom: 12px;">
<div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
<div><b style="color: #F1F5F9; font-size: 16px; display: block; margin-bottom: 4px;">{row[nome_col]}</b><span style="color: #94A3B8; font-size: 12px;">Custo: {formatar_brl(row['custo_unitario'])}</span></div>
<div style="text-align: right;"><span style="color: #EF4444; font-size: 12px; font-weight: 700; display: block;">— CRÍTICO —</span><span style="color: #EF4444; font-size: 14px; font-weight: 700;">{margem_atual:.1f}%</span></div>
</div>
<div style="background: rgba(0, 0, 0, 0.2); border-radius: 6px; padding: 10px; margin-bottom: 10px;">
<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;"><span style="color: #94A3B8; font-size: 12px;">Preço Atual</span><span style="color: #0EA5E9; font-size: 14px; font-weight: 700;">{formatar_brl(row['preco_venda'])}</span></div>
<div style="display: flex; justify-content: center; margin-bottom: 8px;"><span style="color: #10B981; font-size: 18px; font-weight: 700;">↓</span></div>
<div style="display: flex; justify-content: space-between; align-items: center;"><span style="color: #94A3B8; font-size: 12px;">Novo Preço</span><span style="color: #10B981; font-size: 14px; font-weight: 700;">{formatar_brl(preco_novo)}</span></div>
</div>
<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 12px;">
<div style="background: rgba(16, 185, 129, 0.15); border-radius: 6px; padding: 8px; text-align: center;"><span style="color: #94A3B8; display: block; font-size: 11px; margin-bottom: 2px;">Aumento</span><span style="color: #10B981; font-weight: 700; font-size: 13px;">+{aumento_pct:.1f}%</span></div>
<div style="background: rgba(14, 165, 233, 0.15); border-radius: 6px; padding: 8px; text-align: center;"><span style="color: #94A3B8; display: block; font-size: 11px; margin-bottom: 2px;">Nova Margem</span><span style="color: #0EA5E9; font-weight: 700; font-size: 13px;">~20.0%</span></div>
</div>
<div style="background: rgba(245, 158, 11, 0.15); border-left: 3px solid #F59E0B; border-radius: 6px; padding: 8px; margin-top: 10px; font-size: 12px; color: #94A3B8;"><span style="font-weight: 600; color: #F59E0B;">💡 ROI Mensal:</span> <span style="color: #10B981; font-weight: 700;">{formatar_brl(impacto_mensal)}</span> de lucro extra</div>
</div>
"""
                        st.write(html_card, unsafe_allow_html=True)
                
                # Botão de aplicar todas as alterações selecionadas
                if alteracoes_batch:
                    st.markdown("---")
                    impacto_total = sum([alt['impacto_mensal'] for alt in alteracoes_batch])
                    
                    col_confirm1, col_confirm2 = st.columns([3, 1])
                    with col_confirm1:
                        st.markdown(f"""
                        <div style="background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.4); 
                                    border-radius: 10px; padding: 15px; text-align: center;">
                            <span style="color: #94A3B8; font-size: 14px;">💰 Impacto Total Estimado:</span><br>
                            <span style="color: #10B981; font-size: 24px; font-weight: 700;">{formatar_brl(impacto_total)}/mês</span><br>
                            <span style="color: #94A3B8; font-size: 12px;">{len(alteracoes_batch)} produto(s) selecionado(s)</span>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    # Confirmação e botão
                    confirmar_batch = st.checkbox(
                        f"✅ Confirmo que desejo aplicar as alterações em {len(alteracoes_batch)} produto(s)",
                        key="confirmar_batch_criticos"
                    )
                    
                    if st.button("💾 Aplicar Todas as Alterações Selecionadas", 
                                type="primary", 
                                use_container_width=True, 
                                disabled=not confirmar_batch):
                        sucesso_count = 0
                        erro_count = 0
                        
                        for alt in alteracoes_batch:
                            if salvar_alteracao_supabase(
                                alt['produto_id'], 
                                alt['preco_novo'], 
                                alt['custo_atual'],
                                alt['produto_nome'],
                                alt['preco_atual'],
                                alt['custo_atual']
                            ):
                                registro = (
                                    f"{datetime.now().strftime('%d/%m %H:%M')} | {alt['produto_nome']} | "
                                    f"Preço: {formatar_brl(alt['preco_atual'])} → {formatar_brl(alt['preco_novo'])}"
                                )
                                st.session_state.log_mudancas.append(registro)
                                sucesso_count += 1
                            else:
                                erro_count += 1
                        
                        if sucesso_count > 0:
                            st.success(f"✅ {sucesso_count} produto(s) atualizado(s) com sucesso!")
                        if erro_count > 0:
                            st.error(f"❌ Erro ao atualizar {erro_count} produto(s)")
                        
                        st.cache_data.clear()
                        st.rerun()
                else:
                    st.info("👆 Marque pelo menos um checkbox para habilitar o botão de aplicar")
    else:
        st.success("✅ **Portfolio saudável!** Todos os produtos com margem acima de 10%")

    # Abas de Gráficos
    st.markdown("---")
    st.markdown("### 📊 Análises Detalhadas")
    t1, t2, t3, t4 = st.tabs(["🏆 TOP 10 Produtos", "🥧 Decomposição de Custos", "📈 Margem vs Custo", "🤖 IA Consultora"])

    with t1:
        st.caption("Este gráfico mostra o TOP 10 produtos com maior lucro mensal projetado, ajudando a identificar os campeões do portfólio.")
        top_df = df.nlargest(10, 'lucro_total_mensal')
        fig = px.bar(
            top_df, 
            x=nome_col, 
            y='lucro_total_mensal',
            color='status',
            color_discrete_map={'🟢 SAUDÁVEL': '#10B981', '🟡 ALERTA': '#F59E0B', '🔴 CRÍTICO': '#EF4444'},
            title="🏆 TOP 10 - Produtos Mais Lucrativos",
            labels={'lucro_total_mensal': 'Lucro Mensal (R$)', nome_col: 'Produto'},
            template='plotly_dark',
            height=450
        )
        fig.update_traces(
            marker_line=dict(width=0),
            text=top_df['lucro_total_mensal'].apply(lambda value: formatar_brl(value)),
            textposition='outside',
            hovertemplate='<b>%{x}</b><br>Lucro Mensal: %{text}<extra></extra>'
        )
        fig.update_layout(
            hovermode='x unified',
            font=dict(family="Arial, sans-serif", size=12, color="#F1F5F9"),
            plot_bgcolor='rgba(30, 41, 59, 0.5)',
            paper_bgcolor='rgba(15, 23, 42, 0)',
            margin=dict(l=0, r=0, t=40, b=0)
        )
        st.plotly_chart(fig, use_container_width=True)

    with t2:
        st.caption("Esta decomposição detalha como o preço de venda é distribuído entre custo, impostos, taxas, logística e lucro por unidade.")
        decomp = {
            'Custo Produto': p_data['custo_unitario'],
            'Impostos': p_data['imposto_valor'],
            'Taxa Cartão': p_data['cartao_valor'],
            'Logística': p_data['custo_logistico'],
            'Lucro ✓': max(0, p_data['lucro_unitario'])
        }
        decomp_df = pd.DataFrame(
            {
                'componente': list(decomp.keys()),
                'valor': list(decomp.values())
            }
        )
        base_total = max(float(p_data['preco_venda']), 0.01)
        decomp_df['pct'] = (decomp_df['valor'] / base_total * 100).round(1)

        fig = px.bar(
            decomp_df,
            x='valor',
            y='componente',
            orientation='h',
            title="📊 Decomposição do Preço de Venda (por componente)",
            template='plotly_dark',
            color='componente',
            color_discrete_map={
                'Custo Produto': '#0EA5E9',
                'Impostos': '#F59E0B',
                'Taxa Cartão': '#EF4444',
                'Logística': '#EC4899',
                'Lucro ✓': '#10B981'
            },
            height=450
        )
        fig.update_traces(
            text=decomp_df.apply(lambda row: f"{formatar_brl(row['valor'])} ({row['pct']:.1f}%)", axis=1),
            textposition='outside',
            hovertemplate='<b>%{y}</b><br>Valor: %{x:,.2f}<extra></extra>'
        )
        fig.update_layout(
            font=dict(family="Arial, sans-serif", size=12, color="#F1F5F9"),
            showlegend=False,
            paper_bgcolor='rgba(15, 23, 42, 0)',
            plot_bgcolor='rgba(30, 41, 59, 0.5)',
            margin=dict(l=0, r=0, t=40, b=0)
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Legenda detalhada
        st.markdown("**Detalhamento:**")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("💰 Custo Produto", formatar_brl(p_data['custo_unitario']))
        with col2:
            st.metric("💸 Total de Deduções", formatar_brl(p_data['imposto_valor'] + p_data['cartao_valor'] + p_data['custo_logistico']))
        with col3:
            st.metric("📈 Margem Bruta", formatar_brl(max(0, p_data['lucro_unitario'])))

    with t3:
        st.caption("Aqui você compara custo unitário versus margem de todos os produtos; o tamanho da bolha representa o preço de venda.")
        fig = px.scatter(
            df,
            x='custo_unitario',
            y='margem_pct',
            color='status',
            size='preco_venda',
            hover_name=nome_col,
            color_discrete_map={'🟢 SAUDÁVEL': '#10B981', '🟡 ALERTA': '#F59E0B', '🔴 CRÍTICO': '#EF4444'},
            title="📈 Análise: Margem vs Custo de Todos Produtos",
            labels={'custo_unitario': 'Custo Unitário (R$)', 'margem_pct': 'Margem (%)'},
            template='plotly_dark',
            height=450
        )
        fig.update_traces(marker=dict(line=dict(width=1, color='rgba(255,255,255,0.25)')))
        fig.add_hline(y=20, line_dash="dash", line_color="#10B981", annotation_text="Margem Ideal (20%)", annotation_position="right")
        fig.add_hline(y=10, line_dash="dash", line_color="#F59E0B", annotation_text="Margem Mínima (10%)", annotation_position="right")
        fig.update_layout(
            hovermode='closest',
            font=dict(family="Arial, sans-serif", size=12, color="#F1F5F9"),
            plot_bgcolor='rgba(30, 41, 59, 0.5)',
            paper_bgcolor='rgba(15, 23, 42, 0)',
            margin=dict(l=0, r=0, t=40, b=0)
        )
        st.plotly_chart(fig, use_container_width=True)

    with t4:
        st.caption("Assistente IA para recomendar ações práticas com base nos dados do produto selecionado e do portfólio.")
        st.markdown("### 🤖 Consultor Financeiro com IA")
        st.markdown("*Análise inteligente do seu portfólio*")
        st.markdown("---")
        
        for msg in st.session_state.historico_chat:
            with st.chat_message(msg['role']):
                st.write(msg['content'])
        
        if user_in := st.chat_input("💬 Pergunte sobre sua estratégia..."):
            st.session_state.historico_chat.append({'role': 'user', 'content': user_in})
            ctx = f"""Você é um CFO especializado em e-commerce. Analise:
Produto Selecionado: {selected_produto}
Margem: {p_data['margem_pct']:.1f}%
Custo: R$ {p_data['custo_unitario']:.2f}
Preço: R$ {p_data['preco_venda']:.2f}
Lucro Mensal: {formatar_brl(p_data['lucro_total_mensal'])}
Portfolio: {len(df)} produtos

Dê 2-3 recomendações práticas em português."""
            try:
                resp = model.generate_content(ctx + "\n\nPergunta: " + user_in)
                st.session_state.historico_chat.append({'role': 'assistant', 'content': resp.text})
                st.rerun()
            except Exception as e:
                st.error(f"❌ Erro: {e}")

    # ========== SMART RECOMMENDATIONS ==========
    st.markdown("---")
    st.markdown("### 🎯 Recomendações Inteligentes")
    
    # Análise automática
    rec_col1, rec_col2 = st.columns(2)
    
    with rec_col1:
        # Produtos com mais potencial de aumento
        top_oportunidade = df[df['oportunidade'] > 0].nlargest(3, 'oportunidade')
        if not top_oportunidade.empty:
            st.markdown("**📊 Top 3 Oportunidades de Preço:**")
            for idx, row in top_oportunidade.iterrows():
                aumento_pct = ((row['preco_ideal'] - row['preco_venda']) / row['preco_venda'] * 100)
                st.caption(f"• **{row[nome_col]}**: +{aumento_pct:.1f}% ({formatar_brl(row['oportunidade'])})")
    
    with rec_col2:
        # Produtos com melhor ROI de ajuste
        df_temp = df.copy()
        df_temp['roi_ajuste'] = (df_temp['oportunidade'] * volume) / (df_temp['preco_venda'] * 0.1)
        top_roi = df_temp[df_temp['roi_ajuste'] > 0].nlargest(3, 'roi_ajuste')
        if not top_roi.empty:
            st.markdown("**⚡ Maior Impacto Imediato:**")
            for idx, row in top_roi.iterrows():
                impacto_mensal = row['oportunidade'] * volume
                st.caption(f"• **{row[nome_col]}**: +{formatar_brl(impacto_mensal)}/mês")

    # ========== INSIGHTS VISUAIS ==========
    st.markdown("---")
    st.markdown("### 💡 Insights & Recomendações")
    
    col_i1, col_i2, col_i3 = st.columns(3)
    
    # Produto Estrela
    star = df.loc[df['lucro_total_mensal'].idxmax()]
    with col_i1:
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #10B981 0%, #059669 100%); 
                    border-radius: 12px; padding: 20px; color: white; text-align: center;">
            <h3 style="margin: 0; color: white; font-size: 1.3em;">⭐ ESTRELA</h3>
            <p style="font-size: 16px; font-weight: 700; margin: 10px 0;">{star[nome_col]}</p>
            <p style="margin: 5px 0; font-size: 14px;">💰 {formatar_brl(star['lucro_total_mensal'])}/mês</p>
            <p style="margin: 5px 0; font-size: 14px;">📊 Margem: {star['margem_pct']:.1f}%</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Atenção Necessária
    at_risk = df[df['margem_pct'] < 10]
    if not at_risk.empty:
        risk_prod = at_risk.nlargest(1, 'preco_venda').iloc[0]
        with col_i2:
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #EF4444 0%, #DC2626 100%); 
                        border-radius: 12px; padding: 20px; color: white; text-align: center;">
                <h3 style="margin: 0; color: white; font-size: 1.3em;">⚠️ ATENÇÃO</h3>
                <p style="font-size: 16px; font-weight: 700; margin: 10px 0;">{risk_prod[nome_col]}</p>
                <p style="margin: 5px 0; font-size: 14px;">📉 Margem: {risk_prod['margem_pct']:.1f}%</p>
                <p style="margin: 5px 0; font-size: 14px;">📈 Aumentar: +{risk_prod['oportunidade']:.0f}%</p>
            </div>
            """, unsafe_allow_html=True)
    else:
        with col_i2:
            st.markdown("""
            <div style="background: linear-gradient(135deg, #10B981 0%, #059669 100%); 
                        border-radius: 12px; padding: 20px; color: white; text-align: center;">
                <h3 style="margin: 0; color: white; font-size: 1.3em;">✅ SAUDÁVEL</h3>
                <p style="font-size: 14px; margin: 10px 0;">Todos os produtos com margem ideal</p>
                <p style="margin: 5px 0; font-size: 14px;"><b>0 alertas</b></p>
            </div>
            """, unsafe_allow_html=True)
    
    # Portfolio Total com insights extras
    total = df['lucro_total_mensal'].sum()
    media = df['margem_pct'].mean()
    
    # Insights extras
    top_produto = df.loc[df['lucro_total_mensal'].idxmax()]
    variacao_margem = df['margem_pct'].max() - df['margem_pct'].min()
    
    with col_i3:
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #0EA5E9 0%, #0284C7 100%); 
                    border-radius: 12px; padding: 20px; color: white; text-align: center;">
            <h3 style="margin: 0; color: white; font-size: 1.3em;">💼 PORTFOLIO</h3>
            <p style="font-size: 16px; font-weight: 700; margin: 10px 0;">{formatar_brl(total)}/mês</p>
            <p style="margin: 5px 0; font-size: 14px;">📊 Margem Média: {media:.1f}%</p>
            <p style="margin: 5px 0; font-size: 14px;">📈 Variação: 0% a {df['margem_pct'].max():.1f}%</p>
            <p style="margin: 5px 0; font-size: 14px;">{len(df)} produtos | {len(df[df['margem_pct'] >= 20])} saudáveis</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 📋 Análise Completa de Produtos")
    
    # Exportação
    col_export1, col_export2 = st.columns([3, 1])
    with col_export2:
        csv_data = gerar_csv_produtos(df, nome_col)
        st.download_button(
            label="📥 Exportar CSV",
            data=csv_data,
            file_name=f"produtos_analise_{datetime.now().strftime('%d%m%Y_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    df_tabela = df[[nome_col, 'preco_venda', 'custo_unitario', 'margem_pct', 'score_saude', 'status', 'lucro_total_mensal']].copy()
    
    # Formatar margem como texto com %
    df_tabela['margem_formatada'] = df_tabela['margem_pct'].apply(lambda x: f"{x:.1f}%")
    
    # Adicionar coluna de potencial
    df['potencial_badge'] = df['oportunidade'].apply(
        lambda x: "🔥 Crítico" if x > df['oportunidade'].quantile(0.75) else (
            "⚡ Alto" if x > df['oportunidade'].quantile(0.5) else (
                "✅ Ótimo" if x <= 0 else "•"
            )
        )
    )
    df_tabela['potencial'] = df['potencial_badge']
    
    # Remover margem_pct original e reordenar
    df_tabela = df_tabela.drop('margem_pct', axis=1)
    df_tabela = df_tabela[[nome_col, 'preco_venda', 'custo_unitario', 'margem_formatada', 'score_saude', 'status', 'lucro_total_mensal', 'potencial']]
    
    st.dataframe(
        df_tabela,
        column_config={
            nome_col: st.column_config.TextColumn("Produto", width="large", help="Nome do produto"),
            'preco_venda': st.column_config.NumberColumn("Preço", help="Preço de venda atual", format="R$ %.2f"),
            'custo_unitario': st.column_config.NumberColumn("Custo", help="Custo unitário", format="R$ %.2f"),
            'margem_formatada': st.column_config.TextColumn("Margem", help="Margem de lucro percentual"),
            'score_saude': st.column_config.ProgressColumn("Score Saúde", min_value=0, max_value=100, help="Score de saúde 0-100", format="%.0f"),
            'status': st.column_config.TextColumn("Status", help="🟢 Saudável | 🟡 Alerta | 🔴 Crítico"),
            'lucro_total_mensal': st.column_config.NumberColumn("Lucro/Mês", format="R$ %.2f"),
            'potencial': st.column_config.TextColumn("⚡ Impacto", help="Potencial de aumento de preço")
        },
        use_container_width=True,
        hide_index=True
    )

else:
    st.error("Banco vazio. Verifique o Supabase.")